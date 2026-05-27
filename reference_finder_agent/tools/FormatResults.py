"""Generate a frequency spectrum overlay PNG comparing the user's audio vs top reference tracks."""

from __future__ import annotations

import base64
import io
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import savgol_filter

from agency_swarm.tools import BaseTool
from pydantic import Field

_QUERY_COLOR = "#00d4ff"
_REF_COLORS = ["#ff4757", "#ffa502", "#2ed573"]
_BG = "#0a0c10"
_SURFACE = "#13161d"
_BORDER = "#2d3748"
_TEXT = "#94a3b8"


class FormatResults(BaseTool):
    """Render a frequency spectrum overlay comparing the captured audio against up to 3 reference tracks.

    Returns a base64-encoded PNG suitable for embedding directly in the UI.
    """

    query_spectrum: dict = Field(
        ..., description="Spectrum dict from ExtractFeatures with 'freqs' and 'power_db' lists"
    )
    reference_spectra: list[dict] = Field(
        default=[],
        description="Up to 3 spectrum dicts from reference tracks",
    )
    reference_labels: list[str] = Field(
        default=[],
        description="Display labels for each reference track (e.g. 'Artist – Title')",
    )

    def run(self) -> str:
        fig, ax = plt.subplots(figsize=(12, 3.5), facecolor=_BG)
        ax.set_facecolor(_SURFACE)

        q_freqs = np.array(self.query_spectrum["freqs"])
        q_db = np.array(self.query_spectrum["power_db"])
        q_smooth = _smooth(q_db)

        ax.plot(q_freqs, q_smooth, color=_QUERY_COLOR, linewidth=2.0, label="Your track", zorder=4)
        ax.fill_between(q_freqs, q_smooth, q_smooth.min(), alpha=0.08, color=_QUERY_COLOR, zorder=3)

        for i, (ref_spec, label) in enumerate(
            zip(self.reference_spectra[:3], self.reference_labels[:3])
        ):
            r_freqs = np.array(ref_spec["freqs"])
            r_db = np.array(ref_spec["power_db"])
            r_smooth = _smooth(r_db)
            color = _REF_COLORS[i]
            ax.plot(r_freqs, r_smooth, color=color, linewidth=1.5, alpha=0.75, label=label, zorder=2)

        ax.set_xlim(20, min(q_freqs.max(), 20000))
        ax.set_xscale("log")
        ax.set_xlabel("Frequency (Hz)", color=_TEXT, fontsize=8)
        ax.set_ylabel("Power (dB)", color=_TEXT, fontsize=8)
        ax.set_title("Spectrum Overlay — Your Track vs References", color="#e2e8f0", fontsize=10, pad=8)

        ax.tick_params(colors=_TEXT, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color(_BORDER)
        ax.grid(True, color=_BORDER, linewidth=0.4, alpha=0.6, which="both")

        # Frequency band labels
        for freq, label in [(60, "60Hz"), (200, "200Hz"), (1000, "1k"), (5000, "5k"), (10000, "10k")]:
            if freq <= q_freqs.max():
                ax.axvline(freq, color=_BORDER, linewidth=0.5, alpha=0.4, zorder=1)

        ax.legend(
            loc="upper right",
            facecolor="#161b22",
            edgecolor=_BORDER,
            labelcolor="#e2e8f0",
            fontsize=7.5,
            framealpha=0.9,
        )

        plt.tight_layout(pad=0.8)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=_BG)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)

        return json.dumps({"spectrum_png_b64": img_b64})


def _smooth(arr: np.ndarray) -> np.ndarray:
    if len(arr) < 25:
        return arr
    window = min(21, len(arr) - 1 if len(arr) % 2 == 0 else len(arr))
    if window < 5:
        return arr
    window = window if window % 2 == 1 else window - 1
    try:
        return savgol_filter(arr, window_length=window, polyorder=3)
    except Exception:
        return arr
