#!/usr/bin/env bash
# Installs a 5am daily cron job to consolidate knowledge logs.
# Safe to run multiple times — removes any existing entry first.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/consolidate_knowledge.py"
LOG="$REPO_ROOT/knowledge/cron.log"
CRON_MARKER="# unkle-funk-knowledge-consolidation"

# Remove existing entry if present
crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab - 2>/dev/null || true

# Add new entry
(crontab -l 2>/dev/null; echo "0 5 * * * /usr/bin/python3 $SCRIPT --commit >> $LOG 2>&1 $CRON_MARKER") | crontab -

echo "Cron job installed:"
crontab -l | grep "$CRON_MARKER"
echo ""
echo "Runs at 5:00am daily. Logs to $LOG"
echo "To run manually: python3 $SCRIPT --dry-run"
