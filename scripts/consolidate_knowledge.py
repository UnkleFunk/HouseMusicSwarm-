#!/usr/bin/env python3
"""
Consolidates tagged insights from daily_logs/ into structured knowledge files.
Run nightly via cron, or manually anytime.

Tag format in daily logs:
  [PROFILE] Some preference or personal detail
  [PROJECT] Something about an active project
  [RESOURCE] An API, tool, or service detail
  [LESSON] An agent or deployment lesson learned
"""

from __future__ import annotations

import os
import re
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
LOGS_DIR = REPO_ROOT / "knowledge" / "daily_logs"
ARCHIVE_DIR = REPO_ROOT / "knowledge" / "archive"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"

CATEGORY_MAP = {
    "PROFILE": "profile.md",
    "PROJECT": "projects.md",
    "RESOURCE": "resources.md",
    "LESSON": "agent_lessons.md",
}

TAG_PATTERN = re.compile(r"^\s*\[(" + "|".join(CATEGORY_MAP.keys()) + r")\]\s+(.+)$", re.MULTILINE)


def parse_log(log_path: Path) -> dict[str, list[str]]:
    text = log_path.read_text()
    findings: dict[str, list[str]] = {k: [] for k in CATEGORY_MAP}
    for match in TAG_PATTERN.finditer(text):
        category, content = match.group(1), match.group(2).strip()
        findings[category].append(content)
    return findings


def load_existing(knowledge_file: Path) -> set[str]:
    if not knowledge_file.exists():
        return set()
    return set(knowledge_file.read_text().splitlines())


def append_entries(knowledge_file: Path, entries: list[str], dry_run: bool) -> int:
    existing_lines = load_existing(knowledge_file)
    new_entries = [e for e in entries if e not in existing_lines]
    if not new_entries:
        return 0
    if dry_run:
        print(f"  Would add {len(new_entries)} entries to {knowledge_file.name}:")
        for e in new_entries:
            print(f"    + {e}")
    else:
        with open(knowledge_file, "a") as f:
            f.write("\n")
            for entry in new_entries:
                f.write(f"- {entry}\n")
    return len(new_entries)


def archive_log(log_path: Path, dry_run: bool):
    dest = ARCHIVE_DIR / log_path.name
    if dry_run:
        print(f"  Would archive {log_path.name} → archive/")
    else:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(log_path), str(dest))


def git_commit(message: str):
    os.system(f'cd "{REPO_ROOT}" && git add knowledge/ && git commit -m "{message}"')


def main():
    parser = argparse.ArgumentParser(description="Consolidate knowledge from daily logs")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--commit", action="store_true", help="Git commit after consolidation")
    args = parser.parse_args()

    logs = sorted(LOGS_DIR.glob("*.md"))
    if not logs:
        print("No daily logs to process.")
        return

    total_added = 0
    processed = []

    for log in logs:
        print(f"\nProcessing {log.name}...")
        findings = parse_log(log)
        any_found = any(findings.values())

        if not any_found:
            print("  No tagged entries found.")
        else:
            for category, entries in findings.items():
                if not entries:
                    continue
                dest_file = KNOWLEDGE_DIR / CATEGORY_MAP[category]
                added = append_entries(dest_file, entries, args.dry_run)
                total_added += added
                if added == 0:
                    print(f"  [{category}] All {len(entries)} entries already exist.")

        if not args.dry_run:
            archive_log(log, dry_run=False)
            processed.append(log.name)
        else:
            archive_log(log, dry_run=True)

    print(f"\nDone. {total_added} new entries added from {len(logs)} log(s).")

    if args.commit and not args.dry_run and total_added > 0:
        date_str = datetime.now().strftime("%Y-%m-%d")
        git_commit(f"chore: knowledge consolidation {date_str}")
        print("Committed to git.")


if __name__ == "__main__":
    main()
