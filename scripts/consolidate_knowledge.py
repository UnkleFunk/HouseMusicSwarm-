#!/usr/bin/env python3
"""
Nightly knowledge consolidation script.

Reads tagged entries from knowledge/daily_logs/*.md files,
appends new insights to the structured knowledge files,
archives processed logs, and optionally commits to git.

Run manually:   python scripts/consolidate_knowledge.py
Dry run:        python scripts/consolidate_knowledge.py --dry-run
Cron (5am):     0 5 * * * cd /path/to/repo && python scripts/consolidate_knowledge.py --commit
"""

import argparse
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
LOGS_DIR = REPO_ROOT / "knowledge" / "daily_logs"
ARCHIVE_DIR = REPO_ROOT / "knowledge" / "archive"
KNOWLEDGE_FILES = {
    "PROFILE": REPO_ROOT / "knowledge" / "profile.md",
    "PROJECT": REPO_ROOT / "knowledge" / "projects.md",
    "RESOURCE": REPO_ROOT / "knowledge" / "resources.md",
    "SKILL": REPO_ROOT / "knowledge" / "skills.md",
    "LESSON": REPO_ROOT / "knowledge" / "agent_lessons.md",
}

HEADER_PATTERN = re.compile(r"^## \[([A-Z]+)\] (.+)$")


def parse_log_file(log_path: Path) -> list[dict]:
    """Extract tagged sections from a daily log file."""
    entries = []
    current_category = None
    current_title = None
    body_lines: list[str] = []

    for line in log_path.read_text(encoding="utf-8").splitlines():
        match = HEADER_PATTERN.match(line)
        if match:
            if current_category and current_title:
                body = "\n".join(body_lines).strip()
                if body and current_category in KNOWLEDGE_FILES:
                    entries.append({"category": current_category, "title": current_title, "body": body})
            current_category = match.group(1).strip().upper()
            current_title = match.group(2).strip()
            body_lines = []
        elif current_category is not None:
            body_lines.append(line)

    if current_category and current_title:
        body = "\n".join(body_lines).strip()
        if body and current_category in KNOWLEDGE_FILES:
            entries.append({"category": current_category, "title": current_title, "body": body})

    return entries


def entry_exists(knowledge_file: Path, title: str) -> bool:
    """Check if an entry with this title already exists in the knowledge file."""
    if not knowledge_file.exists():
        return False
    content = knowledge_file.read_text(encoding="utf-8")
    return f"## {title}" in content


def append_entry(knowledge_file: Path, title: str, body: str, date_str: str, dry_run: bool):
    """Append a new entry to the appropriate knowledge file."""
    entry = f"\n---\n\n## {title}\n\n*Added: {date_str}*\n\n{body}\n"
    if dry_run:
        print(f"  [DRY RUN] Would append to {knowledge_file.name}:")
        print(f"    Title: {title}")
        print(f"    Body preview: {body[:80]}...")
        return
    with open(knowledge_file, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"  + Appended '{title}' to {knowledge_file.name}")


def archive_log(log_path: Path, dry_run: bool):
    """Move a processed log to the archive directory."""
    archive_path = ARCHIVE_DIR / log_path.name
    if dry_run:
        print(f"  [DRY RUN] Would archive {log_path.name} -> archive/")
        return
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    log_path.rename(archive_path)
    print(f"  Archived {log_path.name}")


def git_commit(message: str):
    """Commit all changes in the knowledge directory."""
    try:
        subprocess.run(
            ["git", "add", "knowledge/"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        if result.returncode == 0:
            print("No changes to commit.")
            return
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_ROOT,
            check=True,
        )
        print(f"Committed: {message}")
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")


def get_unprocessed_logs() -> list[Path]:
    """Return log files that haven't been archived yet."""
    if not LOGS_DIR.exists():
        return []
    return sorted(LOGS_DIR.glob("*.md"))


def consolidate(dry_run: bool = False, commit: bool = False, days: int = 0):
    """Main consolidation routine."""
    cutoff = datetime.now() - timedelta(days=days) if days > 0 else None
    logs = get_unprocessed_logs()

    if cutoff:
        logs = [
            p for p in logs
            if datetime.fromtimestamp(p.stat().st_mtime) >= cutoff
        ]

    if not logs:
        print("No unprocessed logs found.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    total_new = 0
    total_skipped = 0

    for log_path in logs:
        print(f"\nProcessing {log_path.name}...")
        entries = parse_log_file(log_path)

        if not entries:
            print("  No tagged entries found — archiving empty/untagged log.")
            archive_log(log_path, dry_run)
            continue

        for entry in entries:
            knowledge_file = KNOWLEDGE_FILES[entry["category"]]
            if entry_exists(knowledge_file, entry["title"]):
                print(f"  = Skipping duplicate: '{entry['title']}'")
                total_skipped += 1
            else:
                append_entry(knowledge_file, entry["title"], entry["body"], date_str, dry_run)
                total_new += 1

        archive_log(log_path, dry_run)

    print(f"\nDone. {total_new} new entries added, {total_skipped} duplicates skipped.")

    if commit and not dry_run and total_new > 0:
        commit_msg = f"knowledge: nightly consolidation {date_str} ({total_new} new entries)"
        git_commit(commit_msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consolidate knowledge logs")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--commit", action="store_true", help="Auto-commit after consolidation")
    parser.add_argument("--days", type=int, default=0, help="Only process logs from last N days (0 = all)")
    args = parser.parse_args()

    consolidate(dry_run=args.dry_run, commit=args.commit, days=args.days)
