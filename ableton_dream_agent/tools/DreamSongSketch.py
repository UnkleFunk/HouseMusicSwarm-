import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

from agency_swarm.tools import BaseTool
from pydantic import Field

REPO_ROOT = Path(__file__).parent.parent.parent
SKETCHES_DIR = REPO_ROOT / "ableton_extensions" / "built" / "unkle-funk-song-sketch" / "src" / "sketches"
IDEAS_DIR = REPO_ROOT / "ableton_extensions" / "ideas"
INDEX_FILE = REPO_ROOT / "ableton_extensions" / "built" / "unkle-funk-song-sketch" / "src" / "index.ts"
FEEDBACK_DIR = REPO_ROOT / "ableton_extensions" / "feedback"
SDK_CONTEXT = REPO_ROOT / "ableton_extensions" / "sdk_context.md"
PROFILE = REPO_ROOT / "knowledge" / "profile.md"


def _load_recent_feedback(days: int = 7) -> str:
    """Read the last N days of feedback files for context."""
    if not FEEDBACK_DIR.exists():
        return "No feedback yet — first sketch ever."
    files = sorted(FEEDBACK_DIR.glob("*.json"), reverse=True)[:days]
    if not files:
        return "No feedback yet."
    entries = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            entries.append(
                f"- {data.get('date', f.stem)}: \"{data.get('sketch_name', '?')}\" "
                f"rated {data.get('rating', '?')}/5 — {data.get('notes', '')}"
            )
        except Exception:
            pass
    return "\n".join(entries) if entries else "No readable feedback."


def _existing_sketch_names() -> list[str]:
    """Return names of sketches already generated (to avoid repeats)."""
    names = []
    for f in IDEAS_DIR.glob("*.md"):
        content = f.read_text()
        match = re.search(r"^# Sketch: (.+)$", content, re.MULTILINE)
        if match:
            names.append(match.group(1).strip())
    return names


def _register_sketch_in_index(date_str: str, sketch_name: str) -> None:
    """Add import and entry for the new sketch in src/index.ts."""
    if not INDEX_FILE.exists():
        return

    content = INDEX_FILE.read_text()
    safe_id = date_str.replace("-", "")
    import_line = f'import * as sketch_{safe_id} from "./sketches/{date_str}.js";'
    entry_line = f"  sketch_{safe_id},"

    # Add import after the last existing sketch import
    if import_line not in content:
        content = content.replace(
            "// NEW SKETCHES ARE ADDED HERE AUTOMATICALLY BY THE DREAM ENGINE",
            f"{import_line}\n// NEW SKETCHES ARE ADDED HERE AUTOMATICALLY BY THE DREAM ENGINE",
        )

    # Add to SKETCHES array
    if entry_line not in content:
        content = content.replace(
            "  // additional sketch imports appended here nightly",
            f"{entry_line}\n  // additional sketch imports appended here nightly",
        )

    INDEX_FILE.write_text(content)


class DreamSongSketch(BaseTool):
    """
    Generates tonight's Unkle Funk song sketch: writes the TypeScript .ts file,
    creates the idea .md file, and registers the sketch in the extension's index.ts.
    Reads recent feedback to inform stylistic choices.
    """

    sketch_name: str = Field(
        ...,
        description="Evocative name for tonight's sketch (e.g. '4am at the Music Box'). 3-6 words, Chicago-rooted.",
    )
    bpm: int = Field(
        ...,
        description="BPM for this sketch. Must be 120–126.",
        ge=120,
        le=126,
    )
    key: str = Field(
        ...,
        description="Musical key (e.g. 'C Minor', 'D Minor', 'F Minor').",
    )
    bars: int = Field(
        default=8,
        description="Number of bars (8 or 16).",
    )
    vibe_story: str = Field(
        ...,
        description=(
            "3-5 sentences describing the vibe/story of this sketch. "
            "This goes in the idea markdown file. Make it evocative and Chicago-rooted."
        ),
    )
    kick_description: str = Field(
        ...,
        description="Which kick variation is used and why.",
    )
    hat_description: str = Field(
        ...,
        description="Which hat variation is used and why.",
    )
    snare_description: str = Field(
        ...,
        description="Which snare/clap variation is used and why.",
    )
    perc_description: str = Field(
        ...,
        description="Which percussion variation is used and why (or 'none — minimal').",
    )
    bass_description: str = Field(
        ...,
        description="Bass pattern description (key, movement, style).",
    )
    chord_description: str = Field(
        ...,
        description="Chord stab description (placement, voicing, density).",
    )
    typescript_code: str = Field(
        ...,
        description=(
            "Complete TypeScript source code for the sketch file. "
            "Must export: SKETCH_NAME, BPM, BARS, KEY, kickNotes(), snareNotes(), "
            "hatNotes(), percNotes(), bassNotes(), chordNotes(). "
            "Import NoteDescription from '@ableton-extensions/sdk' and humanize from '../humanizer.js'. "
            "All note arrays must be humanized before return."
        ),
    )
    humanize_intensity: str = Field(
        default="tight",
        description="'tight' (club-ready, ±8ms) or 'loose' (organic, ±16ms).",
    )

    def run(self) -> str:
        today = date.today().isoformat()  # YYYY-MM-DD
        sketch_file = SKETCHES_DIR / f"{today}.ts"
        idea_file = IDEAS_DIR / f"{today}.md"

        # Write TypeScript sketch file
        sketch_file.write_text(self.typescript_code)

        # Register in index.ts
        _register_sketch_in_index(today, self.sketch_name)

        # Write idea markdown file
        idea_content = f"""# Sketch: {self.sketch_name}

**Date:** {today}
**Generated by:** Unkle Funk Dream Engine
**BPM:** {self.bpm}
**Key:** {self.key}
**Length:** {self.bars} bars
**Humanize:** {self.humanize_intensity}

---

## The Vibe

{self.vibe_story}

---

## Musical DNA

- **Kick:** {self.kick_description}
- **Hi-Hats:** {self.hat_description}
- **Snare:** {self.snare_description}
- **Percs:** {self.perc_description}
- **Bass:** {self.bass_description}
- **Chords:** {self.chord_description}

---

## How to Use This Sketch

1. Right-click any MIDI track in Ableton → "Load Sketch: {self.sketch_name} ({self.bpm} BPM, {self.key})"
2. 6 MIDI tracks load with {self.bars} bars of humanized patterns
3. Load your samples on each track
4. Loop and start layering

---

## Rate This Sketch

Tell the HouseMusicSwarm agent: "Rate '{self.sketch_name}' [1-5] — [your notes]"

---

## Extension File

`ableton_extensions/built/unkle-funk-song-sketch/src/sketches/{today}.ts`
"""
        idea_file.write_text(idea_content)

        return (
            f"Sketch '{self.sketch_name}' written successfully.\n"
            f"- TypeScript: {sketch_file.relative_to(REPO_ROOT)}\n"
            f"- Idea: {idea_file.relative_to(REPO_ROOT)}\n"
            f"- index.ts updated: {INDEX_FILE.relative_to(REPO_ROOT)}\n\n"
            f"BPM: {self.bpm} | Key: {self.key} | Bars: {self.bars}"
        )
