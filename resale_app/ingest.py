"""Drop-folder ingest: turn image files into photos on items, then queue analysis.

How a dropped file finds its item (first rule that matches wins):
  1. RS-0012 in the file name or a parent folder name  -> add to that existing item.
  2. <drop>/<item folder>/photo.jpg                    -> one item per folder.
     <drop>/<category>/<item folder>/photo.jpg         -> same, with the category taken from the first folder
                                                          (boards, clothing, sneakers ...).
  3. A loose photo (in the drop root, a category folder, or outside the drop folder entirely)
     -> joins the newest "drop batch" item if its last photo arrived within RESALE_BATCH_GAP_SECONDS
        (default 120), otherwise starts a new item. This is what makes Hazel, which hands over one
        file at a time, group a phone shoot into one item.

After ingest the file is moved to <drop>/_processed/<date>/ (or <drop>/_failed/ with an .error.txt),
so a folder watcher or Hazel never handles it twice. Files outside the drop folder are left where they are.
Analysis is queued with a settle delay so photos still arriving don't trigger a half-finished read.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from . import db, images
from .config import Settings

# Not \b: "RS-0012_front" has no word boundary between the digits and the underscore.
SKU_RE = re.compile(r"(?i)(?<![A-Za-z0-9])RS-(\d{4,})(?!\d)")
CATEGORY_ALIASES = {
    "board": "board", "boards": "board", "motherboard": "board", "motherboards": "board", "mobo": "board", "mobos": "board",
    "clothing": "clothing", "clothes": "clothing", "apparel": "clothing",
    "sneaker": "sneakers", "sneakers": "sneakers", "shoe": "sneakers", "shoes": "sneakers",
    "other": "other",
}
PROCESSED_DIR, FAILED_DIR = "_processed", "_failed"
_NO_TOUCH_PARTS = {PROCESSED_DIR, FAILED_DIR}


@dataclass
class IngestResult:
    path: str
    sku: str = ""
    created: bool = False
    added: bool = False
    duplicate: bool = False
    error: str = ""
    moved_to: str = ""


def _relative(path: Path, root: Path) -> tuple[str, ...] | None:
    try:
        return path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return None


def _sku_in(path: Path, rel: tuple[str, ...] | None) -> str | None:
    names = [path.stem] + [p.name for p in list(path.parents)[:3]]
    if rel is not None:
        names = [path.stem] + list(reversed(rel[:-1]))
    for name in names:
        m = SKU_RE.search(name)
        if m:
            return f"RS-{m.group(1)}"
    return None


def _batch_item(conn: sqlite3.Connection, category: str, gap: float) -> dict[str, Any] | None:
    row = conn.execute("SELECT id FROM items WHERE intake_key LIKE ? ORDER BY id DESC LIMIT 1", (f"drop:batch:{category}:%",)).fetchone()
    if row and time.time() - db.newest_photo_epoch(conn, row["id"]) <= gap:
        return db.get_item(conn, row["id"])
    return None


def resolve_item(conn: sqlite3.Connection, settings: Settings, path: Path) -> tuple[dict[str, Any], bool]:
    """The item this file belongs to, creating it if needed. Returns (item, created)."""
    rel = _relative(path, settings.drop_dir)

    sku = _sku_in(path, rel)
    if sku:
        item = db.get_item_by_sku(conn, sku)
        if item is None:
            raise LookupError(f"{sku} is not in the database")
        return item, False

    category_hint = "unknown"
    folder_parts: tuple[str, ...] = ()
    if rel is not None and len(rel) >= 2:
        folders = rel[:-1]
        alias = CATEGORY_ALIASES.get(folders[0].lower())
        if alias:
            category_hint, folders = alias, folders[1:]
        folder_parts = folders

    if folder_parts:
        key = "drop:" + "/".join(folder_parts) + (f"@{category_hint}" if category_hint != "unknown" else "")
        item = db.get_item_by_key(conn, key)
        if item:
            return item, False
        return db.create_item(conn, category=category_hint, title=folder_parts[-1], intake_key=key), True

    if rel is not None and len(rel) == 2 and CATEGORY_ALIASES.get(rel[0].lower()):
        category_hint = CATEGORY_ALIASES[rel[0].lower()]
    item = _batch_item(conn, category_hint, settings.batch_gap_seconds)
    if item:
        return item, False
    key = f"drop:batch:{category_hint}:{uuid.uuid4().hex[:8]}"
    title = "Dropped photos " + datetime.now().strftime("%Y-%m-%d %H:%M")
    return db.create_item(conn, category=category_hint, title=title, intake_key=key), True


def _unique(dest_dir: Path, name: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / name
    n = 1
    while target.exists():
        target = dest_dir / f"{Path(name).stem}-{n}{Path(name).suffix}"
        n += 1
    return target


def _move(settings: Settings, path: Path, bucket: str, dated: bool) -> str:
    dest = settings.drop_dir / bucket / (date.today().isoformat() if dated else "")
    target = _unique(dest, path.name)
    shutil.move(str(path), target)
    return str(target)


def ingest_file(conn: sqlite3.Connection, settings: Settings, path: Path, analyze: bool = True, move: bool = True) -> IngestResult:
    result = IngestResult(path=str(path))
    inside = _relative(path, settings.drop_dir) is not None
    try:
        if not path.is_file():
            raise FileNotFoundError("file not found")
        if not images.is_image_name(path.name):
            raise images.ImageError(f"{path.name}: not an image file type")
        item, created = resolve_item(conn, settings, path)
        stored = images.store_photo(conn, settings, item, path.name, path.read_bytes())
        result.sku, result.created, result.duplicate = item["sku"], created, stored.duplicate
        result.added = not stored.duplicate
        if result.added and analyze and item["status"] not in ("listed", "sold"):
            db.queue_analysis(conn, item["id"], delay=settings.settle_seconds)
        if move and inside:
            result.moved_to = _move(settings, path, PROCESSED_DIR, dated=True)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        if move and inside and path.exists():
            try:
                result.moved_to = _move(settings, path, FAILED_DIR, dated=False)
                Path(result.moved_to).with_name(Path(result.moved_to).name + ".error.txt").write_text(result.error + "\n", encoding="utf-8")
            except OSError:
                pass
    return result


def expand(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            out += sorted(f for f in p.rglob("*") if f.is_file() and images.is_image_name(f.name) and not (_NO_TOUCH_PARTS & set(f.parts)))
        else:
            out.append(p)
    return out


def ingest_paths(paths: Iterable[Path], settings: Settings, analyze: bool = True, move: bool = True) -> list[IngestResult]:
    files = expand(Path(p).expanduser() for p in paths)
    # Oldest first, so a phone shoot lands in the order it was taken.
    files.sort(key=lambda f: f.stat().st_mtime if f.exists() else 0)
    conn = db.connect(settings)
    try:
        return [ingest_file(conn, settings, f, analyze=analyze, move=move) for f in files]
    finally:
        conn.close()
