import json
from agency_swarm.tools import BaseTool
from pydantic import Field

from reference_finder_agent.audio_utils import extract_features


class ExtractFeatures(BaseTool):
    """Extract tonal, spectral, low-end, and dynamic audio features from a WAV file.

    Returns a weighted L2-normalized feature vector for similarity search,
    alongside human-readable stats and a frequency spectrum for visualization.
    """

    audio_path: str = Field(..., description="Absolute path to a WAV audio file")

    def run(self) -> str:
        result = extract_features(self.audio_path)
        return json.dumps(result)
