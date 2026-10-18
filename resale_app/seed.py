"""Load preloaded inventory from a CSV. Safe to run again: rows are matched by a stable key.

Columns (header row required, all optional except at least one of category/brand/model/title):
    ref, category, brand, model, title, condition, status, cost, notes, photos

- ref        your own reference for the row; keeps re-runs from creating duplicates. If blank, a key is
             derived from category + brand + model + title.
- category   board | clothing | sneakers | other | unknown (blank = unknown; the photos decide later)
- condition  new | like_new | good | fair | for_parts (blank = let the photos suggest one)
- status     intake | needs_photos | review | approved | listed | sold | skipped (blank = intake)
- cost       what you paid, e.g. 12.50 or $12.50. Never goes into a listing.
- photos     file paths separated by | (relative paths are relative to the CSV's folder)
"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import db, images
from .categories import CATEGORIES, GRADES
from .config import Settings

DEFAULT_FILE = Path(__file__).parent / "seed" / "sample_inventory.csv"


@dataclass
class SeedSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    photos_added: int = 0
    errors: list[str] = field(default_factory=list)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def _key(row: dict[str, str]) -> str:
    if row.get("ref"):
        return f"seed:{row['ref']}"
    basis = "|".join(row.get(k, "").lower() for k in ("category", "brand", "model", "title"))
    return "seed:" + hashlib.sha1(basis.encode()).hexdigest()[:12]


def _fields(row: dict[str, str]) -> dict[str, Any]:
    category = (row.get("category") or "unknown").lower()
    if category not in CATEGORIES and category != "unknown":
        raise ValueError(f"unknown category {category!r}")
    condition = (row.get("condition") or "").lower() or None
    if condition and condition not in GRADES:
        raise ValueError(f"unknown condition {condition!r}")
    status = (row.get("status") or "intake").lower()
    if status not in db.ITEM_STATUSES:
        raise ValueError(f"unknown status {status!r}")
    if not any(row.get(k) for k in ("brand", "model", "title")):
        raise ValueError("needs at least a brand, model or title")
    cost = db.parse_money(row.get("cost"))
    if row.get("cost") and cost is None:
        raise ValueError(f"cannot read cost {row['cost']!r}")
    title = row.get("title") or " ".join(p for p in (row.get("brand"), row.get("model")) if p)
    return {
        "category": category, "brand": row.get("brand", ""), "model": row.get("model", ""), "title": title,
        "condition": condition, "status": status, "cost_basis_cents": cost, "notes": row.get("notes", ""),
    }


def seed(conn: sqlite3.Connection, settings: Settings, rows: list[dict[str, str]], base_dir: Path, update: bool = False) -> SeedSummary:
    out = SeedSummary()
    for n, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            fields = _fields(row)
        except ValueError as exc:
            out.errors.append(f"row {n}: {exc}")
            continue
        key = _key(row)
        item = db.get_item_by_key(conn, key)
        if item is None:
            item = db.create_item(conn, intake_key=key, **fields)
            out.created += 1
        elif update:
            item = db.update_item(conn, item["id"], **fields)
            out.updated += 1
        else:
            out.skipped += 1
        for raw in filter(None, (p.strip() for p in row.get("photos", "").split("|"))):
            path = Path(raw).expanduser()
            path = path if path.is_absolute() else base_dir / path
            try:
                stored = images.store_photo(conn, settings, item, path.name, path.read_bytes())
                out.photos_added += 0 if stored.duplicate else 1
            except (OSError, images.ImageError) as exc:
                out.errors.append(f"row {n}: photo {raw}: {exc}")
    return out
