import json
import sounddevice as sd
from agency_swarm.tools import BaseTool


class ListAudioDevices(BaseTool):
    """List all audio input devices available on the system, flagging virtual loopback devices."""

    def run(self) -> str:
        devices = sd.query_devices()
        try:
            hostapis = sd.query_hostapis()
        except Exception:
            hostapis = []

        # Keywords that identify virtual / loopback / system-capture devices.
        # These route playback (DAW, browser, player) back as a capture input.
        _loopback_keywords = {
            "loopback", "blackhole", "soundflower", "virtual", "aggregate",
            "multi-output", "system audio", "recorder", "serato", "rekordbox",
            "appvolume", "vb-audio", "vb-cable", "cable", "voicemeeter",
        }

        results = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] < 1:
                continue
            host_name = (
                hostapis[d["hostapi"]]["name"]
                if d["hostapi"] < len(hostapis)
                else "Unknown"
            )
            name_lower = d["name"].lower()
            is_loopback = any(kw in name_lower for kw in _loopback_keywords)
            results.append({
                "index": i,
                "name": d["name"],
                "host_api": host_name,
                "channels": d["max_input_channels"],
                "default_sample_rate": int(d["default_samplerate"]),
                "is_loopback": is_loopback,
            })

        return json.dumps(results)
