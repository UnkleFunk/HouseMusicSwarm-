"""Audio feature extraction using only scipy + numpy + soundfile + pyloudnorm.

No librosa, no numba, no llvmlite — all pre-built wheel installs.
Feature vector is identical in structure to the librosa version.
"""

from __future__ import annotations

import json
import math

import numpy as np
import soundfile as sf
from scipy.fft import dct
from scipy.signal import resample_poly


# ── Weights (identical to the original) ──────────────────────────────────────
_WEIGHTS = {
    "sub_bass": 3.0,
    "bass": 3.0,
    "spectral_contrast": 2.5,
    "mfcc": 2.0,
    "lufs": 1.5,
    "rms": 1.5,
    "dynamic_range": 1.5,
    "centroid": 1.5,
    "rolloff": 1.2,
    "low_mid": 1.0,
    "zcr": 1.0,
    "chroma": 0.5,
    "bpm": 0.3,
}

_TARGET_SR = 44100
_HOP = 512
_N_FFT = 2048
_N_MELS = 40
_N_MFCC = 13


# ── Public API ────────────────────────────────────────────────────────────────

def extract_features(audio_path: str) -> dict:
    """Return feature vector + metadata for similarity search.

    Keys:
      vector   - L2-normalised list[float] (~46 dims) for ChromaDB
      metadata - human-readable stats for display
      spectrum - {freqs, power_db} for frequency overlay chart
    """
    y, sr = _load_audio(audio_path)

    # ── Global power spectrum (for band-energy ratios + spectrum export) ──
    fft_mag = np.abs(np.fft.rfft(y))
    freqs   = np.fft.rfftfreq(len(y), 1.0 / sr)
    power   = fft_mag ** 2
    total_power = power.sum() + 1e-10

    # ── Low-end profile ────────────────────────────────────────────────────
    sub_bass_ratio = float(power[(freqs >= 20) & (freqs <  60)].sum() / total_power)
    bass_ratio     = float(power[(freqs >= 60) & (freqs < 200)].sum() / total_power)
    low_mid_ratio  = float(power[(freqs >= 200) & (freqs < 500)].sum() / total_power)

    # ── Frame-level features ───────────────────────────────────────────────
    frames    = _frame_audio(y, _N_FFT, _HOP)         # (F, N_FFT)
    win       = np.hanning(_N_FFT)
    windowed  = frames * win
    mag_f     = np.abs(np.fft.rfft(windowed, axis=1))  # (F, N_FFT//2+1)
    power_f   = mag_f ** 2

    frame_freqs = np.fft.rfftfreq(_N_FFT, 1.0 / sr)

    # MFCC (13 coefficients)
    mfcc = _compute_mfcc(power_f, sr).mean(axis=0)          # (13,)

    # Spectral contrast (7 bands)
    sc_mean = _spectral_contrast(power_f, frame_freqs).mean(axis=0)   # (7,)

    # Chroma (12 bins)
    chroma = _chroma(power_f, frame_freqs).mean(axis=0)      # (12,)

    # Spectral centroid (Hz)
    with np.errstate(divide="ignore", invalid="ignore"):
        centroid_frames = np.where(
            power_f.sum(axis=1, keepdims=True) > 0,
            (frame_freqs * power_f).sum(axis=1) / power_f.sum(axis=1),
            0.0,
        )
    centroid = float(centroid_frames.mean())

    # Spectral rolloff (85% energy threshold)
    cum_power = np.cumsum(power_f, axis=1)
    threshold = 0.85 * cum_power[:, -1:]
    rolloff_idx = (cum_power < threshold).sum(axis=1)
    rolloff_idx = np.clip(rolloff_idx, 0, len(frame_freqs) - 1)
    rolloff = float(frame_freqs[rolloff_idx].mean())

    # Spectral flatness
    with np.errstate(divide="ignore", invalid="ignore"):
        geo_mean   = np.exp(np.log(np.maximum(power_f, 1e-10)).mean(axis=1))
        arith_mean = power_f.mean(axis=1) + 1e-10
        flatness_f = geo_mean / arith_mean
    flatness = float(np.nan_to_num(flatness_f).mean())

    # Zero crossing rate
    zcr = float(np.mean(np.diff(np.sign(frames), axis=1) != 0))

    # RMS & dynamic range
    rms_frames    = np.sqrt((frames ** 2).mean(axis=1))
    rms           = float(rms_frames.mean())
    dynamic_range = float(rms_frames.max() - rms_frames.min())

    # ── LUFS (integrated loudness) ─────────────────────────────────────────
    lufs = _compute_lufs(y, sr)

    # ── Tempo via autocorrelation ──────────────────────────────────────────
    bpm = _estimate_bpm(y, sr)

    # ── Onset strength proxy ───────────────────────────────────────────────
    onset_strength = float(np.maximum(np.diff(rms_frames), 0).mean())

    # ── Weighted vector ────────────────────────────────────────────────────
    nyq = sr / 2.0
    raw = np.concatenate([
        mfcc    * _WEIGHTS["mfcc"],
        sc_mean * _WEIGHTS["spectral_contrast"],
        chroma  * _WEIGHTS["chroma"],
        [sub_bass_ratio  * _WEIGHTS["sub_bass"]],
        [bass_ratio      * _WEIGHTS["bass"]],
        [low_mid_ratio   * _WEIGHTS["low_mid"]],
        [centroid / nyq  * _WEIGHTS["centroid"]],
        [rolloff / nyq   * _WEIGHTS["rolloff"]],
        [rms             * _WEIGHTS["rms"]],
        [zcr             * _WEIGHTS["zcr"]],
        [(lufs + 70.0) / 70.0 * _WEIGHTS["lufs"]],
        [dynamic_range   * _WEIGHTS["dynamic_range"]],
        [flatness],
        [onset_strength / 10.0],
        [bpm / 200.0     * _WEIGHTS["bpm"]],
    ])

    norm   = np.linalg.norm(raw)
    vector = (raw / norm).tolist() if norm > 0 else raw.tolist()

    # ── Spectrum export (first 512 FFT bins) ───────────────────────────────
    n = min(512, len(freqs))
    spectrum = {
        "freqs":    freqs[:n].tolist(),
        "power_db": (10.0 * np.log10(power[:n] + 1e-10)).tolist(),
    }

    metadata = {
        "bpm":                  round(bpm, 1),
        "lufs":                 round(lufs, 1),
        "sub_bass_ratio":       round(sub_bass_ratio, 4),
        "bass_ratio":           round(bass_ratio, 4),
        "low_mid_ratio":        round(low_mid_ratio, 4),
        "spectral_centroid_hz": round(centroid, 1),
        "rms_energy":           round(rms, 4),
        "dynamic_range":        round(dynamic_range, 4),
        "onset_strength":       round(onset_strength, 4),
    }

    return {"vector": vector, "metadata": metadata, "spectrum": spectrum}


# ── Audio loading ─────────────────────────────────────────────────────────────

def _load_audio(path: str, target_sr: int = _TARGET_SR) -> tuple[np.ndarray, int]:
    y, sr = sf.read(path, always_2d=True)
    # Mono
    y = y.mean(axis=1) if y.shape[1] > 1 else y[:, 0]
    y = y.astype(np.float32)
    # Resample if needed
    if sr != target_sr:
        g = math.gcd(sr, target_sr)
        y = resample_poly(y, target_sr // g, sr // g).astype(np.float32)
        sr = target_sr
    return y, sr


# ── Framing ───────────────────────────────────────────────────────────────────

def _frame_audio(y: np.ndarray, frame_size: int, hop: int) -> np.ndarray:
    """Return overlapping frames using stride tricks (no copy)."""
    if len(y) < frame_size:
        return np.zeros((1, frame_size), dtype=y.dtype)
    n_frames = 1 + (len(y) - frame_size) // hop
    shape   = (n_frames, frame_size)
    strides = (y.strides[0] * hop, y.strides[0])
    return np.lib.stride_tricks.as_strided(y, shape=shape, strides=strides)


# ── MFCC ──────────────────────────────────────────────────────────────────────

def _compute_mfcc(
    power_frames: np.ndarray,   # (F, N_FFT//2+1)
    sr: int,
    n_mels: int = _N_MELS,
    n_mfcc: int = _N_MFCC,
) -> np.ndarray:
    """Mel-filterbank → log → DCT → MFCC.  Returns (F, n_mfcc)."""
    fb    = _mel_filterbank(sr, (power_frames.shape[1] - 1) * 2, n_mels)
    mel   = np.dot(power_frames, fb.T)                        # (F, n_mels)
    log_m = np.log(np.maximum(mel, 1e-10))
    return dct(log_m, type=2, norm="ortho", axis=1)[:, :n_mfcc]


def _mel_filterbank(sr: int, n_fft: int, n_mels: int = _N_MELS) -> np.ndarray:
    """Triangular Mel filterbank matrix, shape (n_mels, n_fft//2+1)."""
    def hz2mel(h): return 2595.0 * np.log10(1.0 + h / 700.0)
    def mel2hz(m): return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    fmax = sr / 2.0
    mel_pts = np.linspace(hz2mel(0), hz2mel(fmax), n_mels + 2)
    hz_pts  = mel2hz(mel_pts)
    bins    = np.floor((n_fft + 1) * hz_pts / sr).astype(int)
    n_bins  = n_fft // 2 + 1
    fb      = np.zeros((n_mels, n_bins))

    for m in range(1, n_mels + 1):
        lo, mid, hi = bins[m-1], bins[m], bins[m+1]
        if mid > lo:
            fb[m-1, lo:mid] = (np.arange(lo, mid) - lo) / (mid - lo)
        if hi > mid:
            fb[m-1, mid:hi] = (hi - np.arange(mid, hi)) / (hi - mid)
    return fb


# ── Spectral contrast ─────────────────────────────────────────────────────────

def _spectral_contrast(
    power_frames: np.ndarray,  # (F, N_FFT//2+1)
    freqs: np.ndarray,
    n_bands: int = 6,
    fmin: float = 200.0,
) -> np.ndarray:
    """Returns per-frame contrast for n_bands+1 octave bands, shape (F, 7)."""
    fmax = freqs[-1]
    edges = [fmin * (2 ** i) for i in range(n_bands)]
    edges.append(fmax)
    edges.insert(0, 0.0)     # band 0: below fmin

    contrasts = np.zeros((power_frames.shape[0], n_bands + 1))
    q_lo, q_hi = 0.1, 0.9   # valley / peak percentile fractions

    for i in range(n_bands + 1):
        lo, hi = edges[i], edges[i + 1]
        mask = (freqs >= lo) & (freqs < hi)
        if mask.sum() < 2:
            continue
        band = power_frames[:, mask]
        n    = band.shape[1]
        k_lo = max(1, int(n * q_lo))
        k_hi = max(1, n - int(n * q_hi))
        sorted_b = np.sort(band, axis=1)
        valley = sorted_b[:, :k_lo].mean(axis=1)
        peak   = sorted_b[:, -k_hi:].mean(axis=1)
        contrasts[:, i] = np.log1p(peak) - np.log1p(np.maximum(valley, 1e-10))

    return contrasts   # (F, 7)


# ── Chroma ────────────────────────────────────────────────────────────────────

def _chroma(
    power_frames: np.ndarray,  # (F, N_FFT//2+1)
    freqs: np.ndarray,
    n_chroma: int = 12,
) -> np.ndarray:
    """Map spectral power to 12 chroma bins.  Returns (F, 12)."""
    mask = (freqs > 80) & (freqs < 2000)
    fq   = freqs[mask]
    pw   = power_frames[:, mask]

    if len(fq) == 0:
        return np.zeros((power_frames.shape[0], n_chroma))

    # Semitone distance from A4=440 Hz → pitch class 0..11
    with np.errstate(divide="ignore", invalid="ignore"):
        semitones  = 12.0 * np.log2(np.maximum(fq, 1e-10) / 440.0)
    chroma_idx = (np.round(semitones).astype(int) % n_chroma)

    chroma = np.zeros((power_frames.shape[0], n_chroma))
    for k in range(n_chroma):
        col_mask = chroma_idx == k
        if col_mask.any():
            chroma[:, k] = pw[:, col_mask].sum(axis=1)

    row_sum = chroma.sum(axis=1, keepdims=True) + 1e-10
    return chroma / row_sum   # (F, 12)


# ── BPM estimation ────────────────────────────────────────────────────────────

def _estimate_bpm(
    y: np.ndarray,
    sr: int,
    hop: int = _HOP,
    min_bpm: float = 80.0,
    max_bpm: float = 200.0,
) -> float:
    """Estimate tempo via autocorrelation of the onset envelope."""
    frame_size = hop
    n_frames   = len(y) // frame_size
    if n_frames < 8:
        return 0.0

    energy = np.array([
        np.sqrt(np.mean(y[i * frame_size:(i + 1) * frame_size] ** 2))
        for i in range(n_frames)
    ])

    # Onset envelope: positive half of first-order difference
    onset = np.maximum(np.diff(energy), 0)
    onset -= onset.mean()

    # Autocorrelation
    ac = np.correlate(onset, onset, mode="full")
    ac = ac[len(ac) // 2:]

    fps     = sr / frame_size
    lag_min = max(1, int(fps * 60.0 / max_bpm))
    lag_max = min(int(fps * 60.0 / min_bpm), len(ac) - 1)

    if lag_min >= lag_max:
        return 0.0

    lag = np.argmax(ac[lag_min:lag_max + 1]) + lag_min
    return float(fps * 60.0 / lag)


# ── LUFS ──────────────────────────────────────────────────────────────────────

def _compute_lufs(y: np.ndarray, sr: int) -> float:
    """ITU-R BS.1770 integrated loudness via pyloudnorm (numpy-only dep)."""
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        lufs  = float(meter.integrated_loudness(y))
        return lufs if np.isfinite(lufs) else -70.0
    except Exception:
        # Fallback: RMS-to-LUFS approximation
        rms = np.sqrt(np.mean(y ** 2)) + 1e-10
        return float(20.0 * np.log10(rms) - 3.0)
