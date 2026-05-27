"""Shared audio feature extraction logic used by both ExtractFeatures tool and BuildDatabase scraper."""

from __future__ import annotations

import json
import numpy as np


# Weights applied to each feature group before L2 normalization.
# Higher = more influence on similarity score.
_WEIGHTS = {
    "sub_bass": 3.0,   # 20–60 Hz (kick/808 depth)
    "bass": 3.0,       # 60–200 Hz (kick-bass relationship)
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


def extract_features(audio_path: str) -> dict:
    """Return feature vector + rich metadata for similarity search and display.

    Returns a dict with keys:
      vector   - L2-normalized list[float] (~46 dims) ready for ChromaDB
      metadata - human-readable stats for display
      spectrum - {freqs, power_db} lists for frequency overlay chart
    """
    import librosa
    import pyloudnorm as pyln
    import soundfile as sf

    y, sr = librosa.load(audio_path, sr=None, mono=True)

    # ── Spectral features ──────────────────────────────────────────────────
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13).mean(axis=1)
    spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr, n_bands=6).mean(axis=1)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    centroid = float(librosa.feature.spectral_centroid(y=y, sr=sr).mean())
    rolloff = float(librosa.feature.spectral_rolloff(y=y, sr=sr).mean())
    flatness = float(librosa.feature.spectral_flatness(y=y).mean())
    zcr = float(librosa.feature.zero_crossing_rate(y).mean())

    # ── Low-end profile ────────────────────────────────────────────────────
    fft = np.fft.rfft(y)
    freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
    power = np.abs(fft) ** 2
    total_power = power.sum() + 1e-10
    sub_bass_ratio = float(power[(freqs >= 20) & (freqs < 60)].sum() / total_power)
    bass_ratio = float(power[(freqs >= 60) & (freqs < 200)].sum() / total_power)
    low_mid_ratio = float(power[(freqs >= 200) & (freqs < 500)].sum() / total_power)

    # ── Dynamics / loudness ────────────────────────────────────────────────
    rms_frames = librosa.feature.rms(y=y)[0]
    rms = float(rms_frames.mean())
    dynamic_range = float(rms_frames.max() - rms_frames.min())

    meter = pyln.Meter(sr)
    try:
        lufs = float(meter.integrated_loudness(y))
        lufs = lufs if np.isfinite(lufs) else -70.0
    except Exception:
        lufs = -70.0

    # ── Tempo ──────────────────────────────────────────────────────────────
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo)

    # ── Onset strength (groove density) ───────────────────────────────────
    onset_strength = float(librosa.onset.onset_strength(y=y, sr=sr).mean())

    # ── Weighted feature vector ────────────────────────────────────────────
    nyq = sr / 2.0
    raw = np.concatenate([
        mfcc * _WEIGHTS["mfcc"],
        spectral_contrast * _WEIGHTS["spectral_contrast"],
        chroma * _WEIGHTS["chroma"],
        [sub_bass_ratio * _WEIGHTS["sub_bass"]],
        [bass_ratio * _WEIGHTS["bass"]],
        [low_mid_ratio * _WEIGHTS["low_mid"]],
        [centroid / nyq * _WEIGHTS["centroid"]],
        [rolloff / nyq * _WEIGHTS["rolloff"]],
        [rms * _WEIGHTS["rms"]],
        [zcr * _WEIGHTS["zcr"]],
        [(lufs + 70.0) / 70.0 * _WEIGHTS["lufs"]],
        [dynamic_range * _WEIGHTS["dynamic_range"]],
        [flatness],
        [onset_strength / 10.0],
        [bpm / 200.0 * _WEIGHTS["bpm"]],
    ])

    norm = np.linalg.norm(raw)
    vector = (raw / norm).tolist() if norm > 0 else raw.tolist()

    # Spectrum: first 512 FFT bins only (enough for 0–~5 kHz at 44.1 kHz)
    n = min(512, len(freqs))
    spectrum = {
        "freqs": freqs[:n].tolist(),
        "power_db": (10.0 * np.log10(power[:n] + 1e-10)).tolist(),
    }

    metadata = {
        "bpm": round(bpm, 1),
        "lufs": round(lufs, 1),
        "sub_bass_ratio": round(sub_bass_ratio, 4),
        "bass_ratio": round(bass_ratio, 4),
        "low_mid_ratio": round(low_mid_ratio, 4),
        "spectral_centroid_hz": round(centroid, 1),
        "rms_energy": round(rms, 4),
        "dynamic_range": round(dynamic_range, 4),
        "onset_strength": round(onset_strength, 3),
    }

    return {"vector": vector, "metadata": metadata, "spectrum": spectrum}
