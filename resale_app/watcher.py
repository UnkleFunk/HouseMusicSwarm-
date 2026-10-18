"""Poll the drop folder and ingest images once they have stopped changing.

Polling beats filesystem events here: AirDrop, iCloud and camera imports write files in
pieces, and what matters is "this file has stopped growing". A file is ingested when its
size and modified time are unchanged between two scans AND it is at least `stable_seconds` old.

Run it on its own:     python -m resale_app watch
Or let Hazel call:     python -m resale_app ingest <file>      (see docs/HAZEL.md)
Both end up in the same ingest code, so you can use either or both.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from . import images
from .config import Settings
from .ingest import FAILED_DIR, PROCESSED_DIR, IngestResult, ingest_paths

log = logging.getLogger("resale.watcher")

_PARTIAL_SUFFIXES = {".part", ".crdownload", ".tmp", ".download", ".icloud"}
MAX_DEPTH = 4


def _eligible(path: Path, root: Path) -> bool:
    rel = path.relative_to(root).parts
    if len(rel) > MAX_DEPTH or rel[0] in (PROCESSED_DIR, FAILED_DIR):
        return False
    name = path.name
    if name.startswith((".", "~$")) or path.suffix.lower() in _PARTIAL_SUFFIXES:
        return False
    return images.is_image_name(name)


class Watcher:
    def __init__(self, settings: Settings, stable_seconds: float = 5.0, analyze: bool = True):
        self.settings = settings
        self.stable_seconds = stable_seconds
        self.analyze = analyze
        self._seen: dict[Path, tuple[int, float]] = {}

    def scan(self, now: float | None = None) -> list[Path]:
        """Files that are ready to ingest right now."""
        now = time.time() if now is None else now
        root = self.settings.drop_dir
        if not root.is_dir():
            return []
        ready, current = [], {}
        for path in root.rglob("*"):
            try:
                if not path.is_file() or not _eligible(path, root):
                    continue
                st = path.stat()
            except OSError:
                continue
            sig = (st.st_size, st.st_mtime)
            current[path] = sig
            if self._seen.get(path) == sig and now - st.st_mtime >= self.stable_seconds:
                ready.append(path)
        self._seen = {p: s for p, s in current.items() if p not in ready}
        return sorted(ready, key=lambda p: p.stat().st_mtime)

    def run_once(self, now: float | None = None) -> list[IngestResult]:
        ready = self.scan(now)
        return ingest_paths(ready, self.settings, analyze=self.analyze) if ready else []

    def run_forever(self, interval: float = 3.0) -> None:
        self.settings.drop_dir.mkdir(parents=True, exist_ok=True)
        log.info("watching %s", self.settings.drop_dir)
        while True:
            for r in self.run_once():
                log.info("%s -> %s%s", r.path, r.sku or "-", f"  ERROR {r.error}" if r.error else ("  (duplicate)" if r.duplicate else ""))
            time.sleep(interval)
