import json
from datetime import date
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

REPO_ROOT = Path(__file__).parent.parent.parent
FEEDBACK_DIR = REPO_ROOT / "ableton_extensions" / "feedback"
IDEAS_DIR = REPO_ROOT / "ableton_extensions" / "ideas"


def _find_sketch_date(sketch_name: str) -> str | None:
    """Try to find the date of a sketch by searching idea files."""
    for idea_file in sorted(IDEAS_DIR.glob("*.md"), reverse=True):
        content = idea_file.read_text()
        if sketch_name.lower() in content.lower():
            return idea_file.stem  # filename is the date
    return None


class SaveFeedback(BaseTool):
    """
    Saves Glenn's rating and notes for a specific sketch to the feedback directory.
    This feedback is read by the dream engine to inform future sketch generation.
    """

    sketch_name: str = Field(
        ...,
        description="Name of the sketch being rated (e.g. 'Slow Burn on State Street').",
    )
    rating: int = Field(
        ...,
        description="Rating from 1 (bad) to 5 (fire).",
        ge=1,
        le=5,
    )
    notes: str = Field(
        ...,
        description="Glenn's specific notes — what worked, what didn't, what to do more of.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional tags for categorizing what worked: e.g. ['afro-house', 'congas', 'keeper', 'too-busy'].",
    )

    def run(self) -> str:
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        sketch_date = _find_sketch_date(self.sketch_name) or today
        feedback_file = FEEDBACK_DIR / f"{sketch_date}.json"

        data = {
            "date": sketch_date,
            "feedback_recorded": today,
            "sketch_name": self.sketch_name,
            "rating": self.rating,
            "notes": self.notes,
            "tags": self.tags,
        }

        feedback_file.write_text(json.dumps(data, indent=2))

        emoji = {1: "❌", 2: "😐", 3: "👍", 4: "🔥", 5: "🔥🔥"}.get(self.rating, "")
        return (
            f"Feedback saved {emoji}\n"
            f"Sketch: '{self.sketch_name}' — {self.rating}/5\n"
            f"Notes: {self.notes}\n"
            f"Saved to: {feedback_file.relative_to(REPO_ROOT)}\n\n"
            f"The dream engine will weight tomorrow's sketch accordingly."
        )
