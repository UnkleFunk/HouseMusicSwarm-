#!/usr/bin/env bash
# Save a single insight to today's daily log for nightly consolidation.
#
# Usage:
#   ./scripts/save_insight.sh CATEGORY "Title" "Content"
#
# Categories: PROFILE, PROJECT, RESOURCE, SKILL, LESSON
#
# Example:
#   ./scripts/save_insight.sh SKILL "DocAgent output path" \
#     "Always specify output path in the first message to avoid a separate confirm step."

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$REPO_ROOT/knowledge/daily_logs"
DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOGS_DIR/$DATE.md"

CATEGORY="${1:-}"
TITLE="${2:-}"
CONTENT="${3:-}"

VALID_CATEGORIES="PROFILE PROJECT RESOURCE SKILL LESSON"

usage() {
    echo "Usage: $0 CATEGORY \"Title\" \"Content\""
    echo "Categories: $VALID_CATEGORIES"
    exit 1
}

[[ -z "$CATEGORY" || -z "$TITLE" || -z "$CONTENT" ]] && usage

CATEGORY="${CATEGORY^^}"
if ! echo "$VALID_CATEGORIES" | grep -qw "$CATEGORY"; then
    echo "Invalid category '$CATEGORY'. Must be one of: $VALID_CATEGORIES"
    exit 1
fi

mkdir -p "$LOGS_DIR"

# Create file header if it doesn't exist
if [[ ! -f "$LOG_FILE" ]]; then
    echo "# Daily Log — $DATE" > "$LOG_FILE"
    echo "" >> "$LOG_FILE"
fi

# Append the tagged entry
cat >> "$LOG_FILE" <<EOF

## [$CATEGORY] $TITLE

$CONTENT
EOF

echo "Saved [$CATEGORY] '$TITLE' to $LOG_FILE"
