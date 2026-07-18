import json
import re
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

REPO_ROOT = Path(__file__).parent.parent.parent
IDEAS_DIR = REPO_ROOT / "ableton_extensions" / "ideas"
FEEDBACK_DIR = REPO_ROOT / "ableton_extensions" / "feedback"


def _load_feedback(date_str: str) -> dict | None:
    f = FEEDBACK_DIR / f"{date_str}.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            return None
    return None


class ListSketches(BaseTool):
    """
    Lists all generated song sketches with their metadata and feedback ratings.
    Use this before generating a new sketch to see what has been done recently.
    """

    limit: int = Field(
        default=14,
        description="Max number of recent sketches to show.",
    )
    rated_only: bool = Field(
        default=False,
        description="If True, only show sketches that have been rated.",
    )

    def run(self) -> str:
        idea_files = sorted(IDEAS_DIR.glob("*.md"), reverse=True)[: self.limit]

        if not idea_files:
            return "No sketches generated yet. Run DreamSongSketch to create the first one."

        rows = []
        for f in idea_files:
            date_str = f.stem
            content = f.read_text()

            name_match = re.search(r"^# Sketch: (.+)$", content, re.MULTILINE)
            bpm_match = re.search(r"\*\*BPM:\*\* (\d+)", content)
            key_match = re.search(r"\*\*Key:\*\* (.+)$", content, re.MULTILINE)
            bars_match = re.search(r"\*\*Length:\*\* (\d+ bars)", content)

            name = name_match.group(1) if name_match else "Unknown"
            bpm = bpm_match.group(1) if bpm_match else "?"
            key = key_match.group(1).strip() if key_match else "?"
            bars = bars_match.group(1) if bars_match else "?"

            feedback = _load_feedback(date_str)
            if self.rated_only and not feedback:
                continue

            rating_str = f"{feedback['rating']}/5" if feedback else "not rated"
            notes_str = f" — {feedback['notes'][:60]}..." if feedback and feedback.get("notes") else ""

            rows.append(
                f"**{date_str}** | {name} | {bpm} BPM, {key}, {bars} | {rating_str}{notes_str}"
            )

        if not rows:
            return "No sketches found matching the filter."

        header = f"## Unkle Funk Sketch Library ({len(rows)} shown)\n\n"
        return header + "\n".join(rows)
