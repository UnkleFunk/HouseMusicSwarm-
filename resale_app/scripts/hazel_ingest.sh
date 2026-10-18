#!/bin/sh
# Hazel -> Resale app. Hazel passes the matched file as $1 (see resale_app/docs/HAZEL.md).
# Adds the photo to an item, moves it to <drop>/_processed/, and queues the photo read.
#
# Hazel runs scripts with a bare-bones PATH, so this uses absolute paths. Edit the two
# variables below if your checkout or virtualenv lives somewhere else.

RESALE_REPO="${RESALE_REPO:-$HOME/HouseMusicSwarm-}"
RESALE_PYTHON="${RESALE_PYTHON:-$RESALE_REPO/.venv-resale/bin/python}"

LOG="$HOME/Library/Logs/resale-ingest.log"
[ -d "$HOME/Library/Logs" ] || LOG="$HOME/resale-ingest.log"

[ -x "$RESALE_PYTHON" ] || RESALE_PYTHON="$(command -v python3)"

cd "$RESALE_REPO" || { echo "$(date '+%F %T') cannot cd to $RESALE_REPO" >> "$LOG"; exit 1; }

# The exit status of the group is python's, so Hazel sees a failure as a failure.
{ echo "--- $(date '+%F %T') $*"; "$RESALE_PYTHON" -m resale_app ingest "$@"; } >> "$LOG" 2>&1
