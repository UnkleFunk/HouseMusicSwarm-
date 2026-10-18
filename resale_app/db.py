"""SQLite storage: items, photos, vision analyses, and per-platform listings.

Plain sqlite3, one short-lived connection per request or job (WAL mode, so the web app,
the drop-folder ingest and the analysis worker can share the file). Money is stored as
integer cents.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sku              TEXT NOT NULL UNIQUE,
    category         TEXT NOT NULL DEFAULT 'unknown',
    brand            TEXT NOT NULL DEFAULT '',
    model            TEXT NOT NULL DEFAULT '',
    title            TEXT NOT NULL DEFAULT '',
    condition        TEXT,
    status           TEXT NOT NULL DEFAULT 'intake',
    cost_basis_cents INTEGER,
    notes            TEXT NOT NULL DEFAULT '',
    intake_key       TEXT UNIQUE,
    waived_shots     TEXT NOT NULL DEFAULT '[]',
    analysis_status  TEXT NOT NULL DEFAULT 'idle',
    analysis_error   TEXT NOT NULL DEFAULT '',
    analyze_after    REAL NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);

CREATE TABLE IF NOT EXISTS photos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id       INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    original_name TEXT NOT NULL DEFAULT '',
    sha256        TEXT NOT NULL,
    position      INTEGER NOT NULL,
    shot          TEXT,
    quality       TEXT,
    added_at      TEXT NOT NULL,
    added_epoch   REAL NOT NULL,
    UNIQUE (item_id, sha256)
);
CREATE INDEX IF NOT EXISTS idx_photos_item ON photos(item_id, position);

CREATE TABLE IF NOT EXISTS analyses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    mode       TEXT NOT NULL,
    model      TEXT NOT NULL DEFAULT '',
    data       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'draft',
    title           TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    specs           TEXT NOT NULL DEFAULT '[]',
    condition_grade TEXT,
    keywords        TEXT NOT NULL DEFAULT '[]',
    photo_order     TEXT NOT NULL DEFAULT '[]',
    warnings        TEXT NOT NULL DEFAULT '[]',
    price_cents     INTEGER,
    external_url    TEXT NOT NULL DEFAULT '',
    posted_at       TEXT,
    edited          INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (item_id, platform)
);
"""

ITEM_STATUSES = ("intake", "needs_photos", "review", "approved", "listed", "sold", "skipped")
LISTING_STATES = ("draft", "approved", "skipped", "posted", "sold")

_ITEM_FIELDS = {
    "category", "brand", "model", "title", "condition", "status", "cost_basis_cents", "notes",
    "waived_shots", "intake_key", "analysis_status", "analysis_error", "analyze_after",
}
_LISTING_FIELDS = {
    "state", "title", "description", "specs", "condition_grade", "keywords", "photo_order",
    "warnings", "price_cents", "external_url", "posted_at", "edited",
}
_LISTING_JSON = {"specs", "keywords", "photo_order", "warnings"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(settings: Settings | None = None) -> sqlite3.Connection:
    s = settings or get_settings()
    s.home.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may open a connection and use it on another pool thread.
    # Each connection serves one request or job at a time.
    conn = sqlite3.connect(s.db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn


def _item(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    d["waived_shots"] = json.loads(d.get("waived_shots") or "[]")
    return d


def _listing(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for col in _LISTING_JSON:
        d[col] = json.loads(d.get(col) or "[]")
    return d


# --- items ---------------------------------------------------------------------------------


def create_item(conn: sqlite3.Connection, **fields: Any) -> dict[str, Any]:
    unknown = set(fields) - _ITEM_FIELDS
    if unknown:
        raise ValueError(f"unknown item fields: {sorted(unknown)}")
    fields = dict(fields)
    if "waived_shots" in fields:
        fields["waived_shots"] = json.dumps(fields["waived_shots"])
    ts = now_iso()
    cols = ["sku", "created_at", "updated_at", *fields]
    vals = [f"tmp-{uuid.uuid4().hex}", ts, ts, *fields.values()]
    cur = conn.execute(
        f"INSERT INTO items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals
    )
    item_id = cur.lastrowid
    conn.execute("UPDATE items SET sku = ? WHERE id = ?", (f"RS-{item_id:04d}", item_id))
    conn.commit()
    return get_item(conn, item_id)  # type: ignore[return-value]


def get_item(conn: sqlite3.Connection, item_id: int) -> dict[str, Any] | None:
    return _item(conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone())


def get_item_by_sku(conn: sqlite3.Connection, sku: str) -> dict[str, Any] | None:
    return _item(conn.execute("SELECT * FROM items WHERE sku = ? COLLATE NOCASE", (sku,)).fetchone())


def get_item_by_key(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    return _item(conn.execute("SELECT * FROM items WHERE intake_key = ?", (key,)).fetchone())


def update_item(conn: sqlite3.Connection, item_id: int, touch: bool = True, **fields: Any) -> dict[str, Any]:
    unknown = set(fields) - _ITEM_FIELDS
    if unknown:
        raise ValueError(f"unknown item fields: {sorted(unknown)}")
    fields = dict(fields)
    if "waived_shots" in fields:
        fields["waived_shots"] = json.dumps(sorted(set(fields["waived_shots"])))
    if touch:
        fields["updated_at"] = now_iso()
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE items SET {sets} WHERE id = ?", [*fields.values(), item_id])
        conn.commit()
    return get_item(conn, item_id)  # type: ignore[return-value]


def list_items(
    conn: sqlite3.Connection,
    status: str | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    where, args = [], []
    if status:
        where.append("i.status = ?")
        args.append(status)
    if category:
        where.append("i.category = ?")
        args.append(category)
    if q:
        like = f"%{q}%"
        where.append("(i.sku LIKE ? OR i.brand LIKE ? OR i.model LIKE ? OR i.title LIKE ? OR i.notes LIKE ?)")
        args += [like] * 5
    sql = (
        "SELECT i.*, (SELECT COUNT(*) FROM photos p WHERE p.item_id = i.id) AS photo_count, "
        "(SELECT filename FROM photos p WHERE p.item_id = i.id ORDER BY position LIMIT 1) AS cover "
        "FROM items i"
        + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY i.updated_at DESC, i.id DESC LIMIT ?"
    )
    return [_item(r) for r in conn.execute(sql, [*args, limit]).fetchall()]  # type: ignore[misc]


def counts_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT status, COUNT(*) AS n FROM items GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}


def delete_item(conn: sqlite3.Connection, item_id: int) -> None:
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()


# --- photos --------------------------------------------------------------------------------


def photo_exists(conn: sqlite3.Connection, item_id: int, sha256: str) -> bool:
    return conn.execute("SELECT 1 FROM photos WHERE item_id = ? AND sha256 = ?", (item_id, sha256)).fetchone() is not None


def add_photo(conn: sqlite3.Connection, item_id: int, filename: str, original_name: str, sha256: str) -> dict[str, Any]:
    pos = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM photos WHERE item_id = ?", (item_id,)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO photos (item_id, filename, original_name, sha256, position, added_at, added_epoch) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (item_id, filename, original_name, sha256, pos, now_iso(), time.time()),
    )
    conn.execute("UPDATE items SET updated_at = ? WHERE id = ?", (now_iso(), item_id))
    conn.commit()
    return get_photo(conn, cur.lastrowid)  # type: ignore[return-value,arg-type]


def get_photo(conn: sqlite3.Connection, photo_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
    return dict(row) if row else None


def list_photos(conn: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM photos WHERE item_id = ? ORDER BY position, id", (item_id,)).fetchall()]


def delete_photo(conn: sqlite3.Connection, photo_id: int) -> None:
    conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    conn.commit()


def newest_photo_epoch(conn: sqlite3.Connection, item_id: int) -> float:
    row = conn.execute("SELECT MAX(added_epoch) FROM photos WHERE item_id = ?", (item_id,)).fetchone()
    return float(row[0] or 0)


def set_photo_reads(conn: sqlite3.Connection, reads: list[tuple[int, str | None, str | None]]) -> None:
    conn.executemany("UPDATE photos SET shot = ?, quality = ? WHERE id = ?", [(s, q, pid) for pid, s, q in reads])
    conn.commit()


# --- analyses ------------------------------------------------------------------------------


def save_analysis(conn: sqlite3.Connection, item_id: int, mode: str, model: str, data: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO analyses (item_id, mode, model, data, created_at) VALUES (?, ?, ?, ?, ?)",
        (item_id, mode, model, json.dumps(data), now_iso()),
    )
    conn.commit()


def latest_analysis(conn: sqlite3.Connection, item_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM analyses WHERE item_id = ? ORDER BY id DESC LIMIT 1", (item_id,)).fetchone()
    if not row:
        return None
    out = json.loads(row["data"])
    out["_created_at"] = row["created_at"]
    return out


# --- analysis queue ------------------------------------------------------------------------


def queue_analysis(conn: sqlite3.Connection, item_id: int, delay: float = 0.0) -> None:
    """Mark an item for (re-)analysis `delay` seconds from now. Later calls push the time out."""
    conn.execute(
        "UPDATE items SET analysis_status = 'queued', analysis_error = '', analyze_after = ? WHERE id = ?",
        (time.time() + delay, item_id),
    )
    conn.commit()


def claim_next_analysis(conn: sqlite3.Connection, now: float | None = None) -> int | None:
    now = time.time() if now is None else now
    row = conn.execute(
        "SELECT id FROM items WHERE analysis_status = 'queued' AND analyze_after <= ? ORDER BY analyze_after, id LIMIT 1",
        (now,),
    ).fetchone()
    if not row:
        return None
    cur = conn.execute("UPDATE items SET analysis_status = 'running' WHERE id = ? AND analysis_status = 'queued'", (row["id"],))
    conn.commit()
    return row["id"] if cur.rowcount == 1 else None


def recover_running(conn: sqlite3.Connection) -> None:
    """After a crash, anything left 'running' goes back in the queue."""
    conn.execute("UPDATE items SET analysis_status = 'queued', analyze_after = 0 WHERE analysis_status = 'running'")
    conn.commit()


# --- listings ------------------------------------------------------------------------------


def get_listing(conn: sqlite3.Connection, listing_id: int) -> dict[str, Any] | None:
    return _listing(conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone())


def get_listing_for(conn: sqlite3.Connection, item_id: int, platform: str) -> dict[str, Any] | None:
    return _listing(conn.execute("SELECT * FROM listings WHERE item_id = ? AND platform = ?", (item_id, platform)).fetchone())


def list_listings(
    conn: sqlite3.Connection,
    item_id: int | None = None,
    platform: str | None = None,
    state: str | None = None,
) -> list[dict[str, Any]]:
    where, args = [], []
    for col, val in (("item_id", item_id), ("platform", platform), ("state", state)):
        if val is not None:
            where.append(f"{col} = ?")
            args.append(val)
    sql = "SELECT * FROM listings" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY item_id, platform"
    return [_listing(r) for r in conn.execute(sql, args).fetchall()]  # type: ignore[misc]


def save_listing(conn: sqlite3.Connection, item_id: int, platform: str, **fields: Any) -> dict[str, Any]:
    """Insert or update the one listing an item has for a platform."""
    unknown = set(fields) - _LISTING_FIELDS
    if unknown:
        raise ValueError(f"unknown listing fields: {sorted(unknown)}")
    fields = {k: (json.dumps(v) if k in _LISTING_JSON else v) for k, v in fields.items()}
    ts = now_iso()
    existing = conn.execute("SELECT id FROM listings WHERE item_id = ? AND platform = ?", (item_id, platform)).fetchone()
    if existing:
        fields["updated_at"] = ts
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE listings SET {sets} WHERE id = ?", [*fields.values(), existing["id"]])
        listing_id = existing["id"]
    else:
        cols = ["item_id", "platform", "created_at", "updated_at", *fields]
        cur = conn.execute(
            f"INSERT INTO listings ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [item_id, platform, ts, ts, *fields.values()],
        )
        listing_id = cur.lastrowid
    conn.commit()
    return get_listing(conn, listing_id)  # type: ignore[arg-type,return-value]


def update_listing(conn: sqlite3.Connection, listing_id: int, **fields: Any) -> dict[str, Any]:
    row = conn.execute("SELECT item_id, platform FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if row is None:
        raise KeyError(listing_id)
    return save_listing(conn, row["item_id"], row["platform"], **fields)


# --- money ---------------------------------------------------------------------------------


def parse_money(text: str | None) -> int | None:
    """'$12.50' -> 1250. Blank or unparseable -> None."""
    if text is None:
        return None
    cleaned = str(text).replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return int(round(float(cleaned) * 100))
    except ValueError:
        return None


def format_money(cents: int | None) -> str:
    return "" if cents is None else f"${cents / 100:,.2f}"
