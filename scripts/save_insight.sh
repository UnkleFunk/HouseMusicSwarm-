#!/usr/bin/env bash
# Quick CLI shortcut to log a tagged insight to today's daily log.
# Usage: ./scripts/save_insight.sh LESSON "Deploy always needs SSH key auth"
#        ./scripts/save_insight.sh PROFILE "Prefers deep house over afro house"

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGS_DIR="$REPO_ROOT/knowledge/daily_logs"
DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOGS_DIR/$DATE.md"

CATEGORY="${1:-}"
CONTENT="${2:-}"

if [[ -z "$CATEGORY" || -z "$CONTENT" ]]; then
  echo "Usage: $0 <CATEGORY> <content>"
  echo "Categories: PROFILE PROJECT RESOURCE LESSON"
  exit 1
fi

CATEGORY=$(echo "$CATEGORY" | tr '[:lower:]' '[:upper:]')

mkdir -p "$LOGS_DIR"

if [[ ! -f "$LOG_FILE" ]]; then
  echo "# Daily Log — $DATE" > "$LOG_FILE"
  echo "" >> "$LOG_FILE"
fi

echo "[$CATEGORY] $CONTENT" >> "$LOG_FILE"
echo "Saved to $LOG_FILE"
