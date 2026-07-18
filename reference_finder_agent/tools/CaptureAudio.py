import json
import os
import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf
from agency_swarm.tools import BaseTool
from pydantic import Field

CAPTURE_PATH = os.path.join(tempfile.gettempdir(), "ref_capture.wav")


class CaptureAudio(BaseTool):
    """Capture system audio from a virtual loopback device for reference analysis."""

    device_index: int = Field(..., description="Audio input device index from ListAudioDevices")
    duration_seconds: int = Field(default=30, ge=5, le=120, description="Capture duration in seconds (5–120)")

    def run(self) -> str:
        device_info = sd.query_devices(self.device_index)
        sample_rate = int(device_info["default_samplerate"])
        channels = min(int(device_info["max_input_channels"]), 2)

        frames = sd.rec(
            int(sample_rate * self.duration_seconds),
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            device=self.device_index,
        )
        sd.wait()

        # Collapse to mono for analysis
        mono = frames.mean(axis=1) if channels > 1 else frames.flatten()

        sf.write(CAPTURE_PATH, mono, sample_rate)

        return json.dumps({
            "path": CAPTURE_PATH,
            "duration_seconds": self.duration_seconds,
            "sample_rate": sample_rate,
        })
