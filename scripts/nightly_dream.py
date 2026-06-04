#!/usr/bin/env python3
"""
Nightly Dream Engine — runs at 5am to generate tonight's Unkle Funk song sketch.

Usage:
    python scripts/nightly_dream.py

The script:
1. Reads recent feedback from ableton_extensions/feedback/
2. Reads Glenn's taste profile from knowledge/profile.md
3. Reads the Extensions SDK context from ableton_extensions/sdk_context.md
4. Calls the AI to generate a new sketch (TypeScript + idea markdown)
5. Commits the new files to git
6. Emails Glenn at glennfgiles@gmail.com with the sketch details
"""

import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

# Ensure repo root is on path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv()


def load_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def load_recent_feedback(days: int = 7) -> str:
    feedback_dir = REPO_ROOT / "ableton_extensions" / "feedback"
    if not feedback_dir.exists():
        return "No feedback yet."
    files = sorted(feedback_dir.glob("*.json"), reverse=True)[:days]
    if not files:
        return "No feedback yet."
    entries = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            entries.append(
                f"- {data.get('date')}: \"{data.get('sketch_name')}\" "
                f"rated {data.get('rating')}/5 — {data.get('notes', '')}"
            )
        except Exception:
            pass
    return "\n".join(entries) if entries else "No readable feedback."


def load_existing_sketch_names() -> list[str]:
    ideas_dir = REPO_ROOT / "ableton_extensions" / "ideas"
    import re
    names = []
    for f in ideas_dir.glob("*.md"):
        match = re.search(r"^# Sketch: (.+)$", f.read_text(), re.MULTILINE)
        if match:
            names.append(match.group(1).strip())
    return names


def build_prompt(today: str) -> str:
    profile = load_text(REPO_ROOT / "knowledge" / "profile.md")
    sdk_context = load_text(REPO_ROOT / "ableton_extensions" / "sdk_context.md")
    feedback = load_recent_feedback()
    existing_names = load_existing_sketch_names()

    existing_str = (
        "None yet — this is the first sketch!"
        if not existing_names
        else "\n".join(f"- {n}" for n in existing_names[-14:])
    )

    return f"""You are the Unkle Funk Dream Engine. Tonight ({today}) you must generate one new Ableton Live Extension song sketch template.

## User Profile
{profile}

## Recent Feedback (last 7 days)
{feedback}

## Already Generated Sketches (don't repeat these patterns)
{existing_str}

## Extensions SDK Reference
{sdk_context}

## Your Task

Generate a complete new song sketch. Return a JSON object with EXACTLY these fields:

{{
  "sketch_name": "Evocative 3-6 word name, Chicago-rooted",
  "bpm": 120-126 (integer),
  "key": "X Minor",
  "bars": 8 or 16,
  "humanize_intensity": "tight" or "loose",
  "vibe_story": "3-5 sentence atmospheric description",
  "kick_description": "Which variation and why",
  "hat_description": "Which variation and why",
  "snare_description": "Which variation and why",
  "perc_description": "Which variation and why (or 'none')",
  "bass_description": "Bass pattern description",
  "chord_description": "Chord stab description",
  "typescript_code": "COMPLETE TypeScript source for the sketch file"
}}

The TypeScript code must:
1. Import NoteDescription from '@ableton-extensions/sdk'
2. Import humanize from '../humanizer.js'
3. Export: SKETCH_NAME (string), BPM (number), BARS (number), KEY (string)
4. Export: kickNotes(), snareNotes(), hatNotes(), percNotes(), bassNotes(), chordNotes() — each returns NoteDescription[]
5. All arrays MUST be humanized via humanize(notes, BPM, intensity) before return
6. Include a multiline comment at the top describing the vibe

Weighted by feedback: {feedback}

Return ONLY valid JSON. No explanation outside the JSON.
"""


def call_ai(prompt: str) -> dict:
    """Call the Claude API to generate the sketch."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def git_commit_and_push(today: str, sketch_name: str) -> None:
    """Commit new sketch files and push to origin."""
    files = [
        f"ableton_extensions/ideas/{today}.md",
        f"ableton_extensions/built/unkle-funk-song-sketch/src/sketches/{today}.ts",
        "ableton_extensions/built/unkle-funk-song-sketch/src/index.ts",
    ]
    existing_files = [f for f in files if (REPO_ROOT / f).exists()]

    if not existing_files:
        print("No files to commit.")
        return

    try:
        subprocess.run(["git", "add"] + existing_files, cwd=REPO_ROOT, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"dream: '{sketch_name}' — {today}"],
            cwd=REPO_ROOT,
            check=True,
        )
        subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
        )
        print(f"Committed and pushed: {sketch_name}")
    except subprocess.CalledProcessError as e:
        print(f"Git error (continuing): {e}")


def send_email(sketch_data: dict, today: str) -> None:
    """Send morning email to Glenn via the Virtual Assistant / Composio."""
    # This is called via the agency when the Virtual Assistant is available.
    # For standalone script use, we write an email-pending file that the VA picks up.
    email_pending = REPO_ROOT / "ableton_extensions" / f"email_pending_{today}.json"
    email_pending.write_text(json.dumps({
        "to": "glennfgiles@gmail.com",
        "subject": f"Tonight's Sketch: {sketch_data['sketch_name']} — {sketch_data['bpm']} BPM, {sketch_data['key']}",
        "body": (
            f"Good morning Glenn,\n\n"
            f"Tonight's sketch is ready: **{sketch_data['sketch_name']}**\n\n"
            f"BPM: {sketch_data['bpm']} | Key: {sketch_data['key']} | {sketch_data['bars']} bars\n\n"
            f"The vibe:\n{sketch_data['vibe_story']}\n\n"
            f"What's in it:\n"
            f"- Kick: {sketch_data['kick_description']}\n"
            f"- Hats: {sketch_data['hat_description']}\n"
            f"- Snare: {sketch_data['snare_description']}\n"
            f"- Percs: {sketch_data['perc_description']}\n"
            f"- Bass: {sketch_data['bass_description']}\n"
            f"- Chords: {sketch_data['chord_description']}\n\n"
            f"To load it in Ableton: right-click any MIDI track → "
            f"'Load Sketch: {sketch_data['sketch_name']} ({sketch_data['bpm']} BPM, {sketch_data['key']})'\n\n"
            f"Rate it by telling HouseMusicSwarm: "
            f"\"Rate '{sketch_data['sketch_name']}' [1-5] — [your notes]\"\n\n"
            f"— Dream Engine"
        ),
    }, indent=2))
    print(f"Email queued: {email_pending.name}")


def main() -> None:
    today = date.today().isoformat()
    sketch_ts = REPO_ROOT / "ableton_extensions" / "built" / "unkle-funk-song-sketch" / "src" / "sketches" / f"{today}.ts"

    if sketch_ts.exists():
        print(f"Sketch for {today} already exists. Skipping generation.")
        return

    print(f"Generating tonight's sketch ({today})...")

    prompt = build_prompt(today)
    sketch_data = call_ai(prompt)

    print(f"Generated: '{sketch_data['sketch_name']}' @ {sketch_data['bpm']} BPM, {sketch_data['key']}")

    # Write the TypeScript file
    sketch_ts.write_text(sketch_data["typescript_code"])

    # Write the idea file
    idea_file = REPO_ROOT / "ableton_extensions" / "ideas" / f"{today}.md"
    idea_file.write_text(
        f"# Sketch: {sketch_data['sketch_name']}\n\n"
        f"**Date:** {today}\n"
        f"**Generated by:** Unkle Funk Dream Engine (nightly run)\n"
        f"**BPM:** {sketch_data['bpm']}\n"
        f"**Key:** {sketch_data['key']}\n"
        f"**Length:** {sketch_data['bars']} bars\n"
        f"**Humanize:** {sketch_data['humanize_intensity']}\n\n"
        f"---\n\n"
        f"## The Vibe\n\n{sketch_data['vibe_story']}\n\n"
        f"---\n\n"
        f"## Musical DNA\n\n"
        f"- **Kick:** {sketch_data['kick_description']}\n"
        f"- **Hi-Hats:** {sketch_data['hat_description']}\n"
        f"- **Snare:** {sketch_data['snare_description']}\n"
        f"- **Percs:** {sketch_data['perc_description']}\n"
        f"- **Bass:** {sketch_data['bass_description']}\n"
        f"- **Chords:** {sketch_data['chord_description']}\n\n"
        f"---\n\n"
        f"## Rate This Sketch\n\n"
        f"Tell HouseMusicSwarm: \"Rate '{sketch_data['sketch_name']}' [1-5] — [your notes]\"\n\n"
        f"---\n\n"
        f"## Extension File\n\n"
        f"`ableton_extensions/built/unkle-funk-song-sketch/src/sketches/{today}.ts`\n"
    )

    # Register in index.ts
    _register_in_index(today, sketch_data["sketch_name"])

    # Git commit and push
    git_commit_and_push(today, sketch_data["sketch_name"])

    # Queue email
    send_email(sketch_data, today)

    print(f"\nDone. Tonight's sketch: '{sketch_data['sketch_name']}'")


def _register_in_index(today: str, sketch_name: str) -> None:
    """Add the new sketch import to index.ts."""
    index_file = (
        REPO_ROOT
        / "ableton_extensions"
        / "built"
        / "unkle-funk-song-sketch"
        / "src"
        / "index.ts"
    )
    if not index_file.exists():
        return

    content = index_file.read_text()
    safe_id = today.replace("-", "")
    import_line = f'import * as sketch_{safe_id} from "./sketches/{today}.js";'
    entry_line = f"  sketch_{safe_id},"

    if import_line not in content:
        content = content.replace(
            "// NEW SKETCHES ARE ADDED HERE AUTOMATICALLY BY THE DREAM ENGINE",
            f"{import_line}\n// NEW SKETCHES ARE ADDED HERE AUTOMATICALLY BY THE DREAM ENGINE",
        )
    if entry_line not in content:
        content = content.replace(
            "  // additional sketch imports appended here nightly",
            f"{entry_line}\n  // additional sketch imports appended here nightly",
        )
    index_file.write_text(content)


if __name__ == "__main__":
    main()
