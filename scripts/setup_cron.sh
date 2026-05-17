#!/usr/bin/env bash
# Install the nightly 5am knowledge consolidation cron job.
#
# Usage:
#   bash scripts/setup_cron.sh
#
# To remove the cron job:
#   crontab -l | grep -v "consolidate_knowledge" | crontab -

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/consolidate_knowledge.py"
PYTHON=$(command -v python3 || command -v python)
LOG_FILE="$REPO_ROOT/knowledge/consolidation.log"

if [[ ! -f "$SCRIPT" ]]; then
    echo "Error: consolidate_knowledge.py not found at $SCRIPT"
    exit 1
fi

CRON_CMD="0 5 * * * cd $REPO_ROOT && $PYTHON $SCRIPT --commit >> $LOG_FILE 2>&1"

# Check if already installed
if crontab -l 2>/dev/null | grep -q "consolidate_knowledge"; then
    echo "Cron job already installed. Current entry:"
    crontab -l | grep "consolidate_knowledge"
    echo ""
    read -rp "Replace it? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
    # Remove existing and re-add
    ( crontab -l 2>/dev/null | grep -v "consolidate_knowledge"; echo "$CRON_CMD" ) | crontab -
else
    ( crontab -l 2>/dev/null; echo "$CRON_CMD" ) | crontab -
fi

echo ""
echo "Cron job installed:"
echo "  $CRON_CMD"
echo ""
echo "Runs daily at 5:00am local time."
echo "Output logged to: $LOG_FILE"
echo ""
echo "To verify: crontab -l"
echo "To remove: crontab -l | grep -v 'consolidate_knowledge' | crontab -"
