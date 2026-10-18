"""Background analysis worker. Uploads, drop-folder ingest and the "re-run" button all just
queue an item; this picks queued items up (after their settle delay) and runs the pipeline.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from . import db, pipeline
from .config import Settings

log = logging.getLogger("resale.worker")


def process_one(settings: Settings, client: Any = None, now: float | None = None) -> bool:
    """Run one queued analysis if one is due. Returns True if an item was processed."""
    conn = db.connect(settings)
    try:
        item_id = db.claim_next_analysis(conn, now)
        if item_id is None:
            return False
        try:
            before = {p["id"] for p in db.list_photos(conn, item_id)}
            pipeline.run_analysis(conn, item_id, settings, client)
            db.update_item(conn, item_id, touch=False, analysis_status="done", analysis_error="")
            after = {p["id"] for p in db.list_photos(conn, item_id)}
            if after != before:  # photos arrived while we were reading; go again
                db.queue_analysis(conn, item_id)
        except Exception as exc:  # keep the worker alive; show the reason on the item
            log.exception("analysis failed for item %s", item_id)
            db.update_item(conn, item_id, touch=False, analysis_status="error", analysis_error=f"{type(exc).__name__}: {exc}"[:500])
        return True
    finally:
        conn.close()


def drain(settings: Settings, client: Any = None, max_items: int = 1000) -> int:
    """Process everything that is due right now. Used by the CLI and tests."""
    done = 0
    while done < max_items and process_one(settings, client):
        done += 1
    return done


def run_forever(settings: Settings, stop: threading.Event, client: Any = None, interval: float = 2.0) -> None:
    conn = db.connect(settings)
    try:
        db.recover_running(conn)
    finally:
        conn.close()
    while not stop.is_set():
        try:
            busy = process_one(settings, client)
        except Exception:  # pragma: no cover - last-resort guard
            log.exception("worker loop error")
            busy = False
        if not busy:
            stop.wait(interval)
        else:
            time.sleep(0)


def start_thread(settings: Settings, client: Any = None) -> tuple[threading.Thread, threading.Event]:
    stop = threading.Event()
    thread = threading.Thread(target=run_forever, args=(settings, stop, client), name="resale-worker", daemon=True)
    thread.start()
    return thread, stop
