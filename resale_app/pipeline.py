"""Photos -> analysis -> missing-photo check -> listing drafts -> item status."""

from __future__ import annotations

import sqlite3
from typing import Any

from . import db, drafting, vision
from .categories import CATEGORIES, MissingShot, missing_shots, required_missing
from .config import Settings
from .models import Analysis


def stored_analysis(conn: sqlite3.Connection, item_id: int) -> Analysis | None:
    data = db.latest_analysis(conn, item_id)
    if data is None:
        return None
    data.pop("_created_at", None)
    return Analysis(**data)


def missing_for(item: dict[str, Any], photos: list[dict[str, Any]], analysis: Analysis | None) -> list[MissingShot]:
    """Shots still to photograph, from the shot label on each photo. Empty until photos are read."""
    if analysis is None or item["category"] not in CATEGORIES:
        return []
    present: set[str] = set()
    bad: dict[str, str] = {}
    for photo in photos:
        shot = photo.get("shot")
        if not shot or shot == "other":
            continue
        if photo.get("quality") in (None, "ok", "glare"):
            present.add(shot)
        else:
            bad.setdefault(shot, photo["quality"])
    bad = {s: q for s, q in bad.items() if s not in present}
    return missing_shots(item["category"], present, bad, has_flaws=bool(analysis.flaws), waived=item.get("waived_shots", []))


def derive_status(item: dict[str, Any], listings: list[dict[str, Any]], required_gaps: bool) -> str:
    states = [l["state"] for l in listings]
    if not states:
        return "intake"
    if "draft" in states:
        return "needs_photos" if required_gaps else "review"
    if "approved" in states:
        return "approved"
    live = [s for s in states if s != "skipped"]
    if live:
        return "sold" if all(s == "sold" for s in live) else "listed"
    return "skipped"


def refresh_status(conn: sqlite3.Connection, item_id: int) -> dict[str, Any]:
    item = db.get_item(conn, item_id)
    listings = db.list_listings(conn, item_id=item_id)
    analysis = stored_analysis(conn, item_id)
    gaps = bool(required_missing(missing_for(item, db.list_photos(conn, item_id), analysis)))
    return db.update_item(conn, item_id, touch=False, status=derive_status(item, listings, gaps))


def store_drafts(conn: sqlite3.Connection, item_id: int, drafts: dict[str, dict[str, Any]], force: bool = False) -> dict[str, int]:
    """Save drafts without trampling the seller's work: edited or already-decided listings are kept."""
    counts = {"created": 0, "updated": 0, "kept": 0}
    for platform, fields in drafts.items():
        existing = db.get_listing_for(conn, item_id, platform)
        if existing is None:
            db.save_listing(conn, item_id, platform, state="draft", edited=0, **fields)
            counts["created"] += 1
        elif force:
            db.save_listing(conn, item_id, platform, state="draft", edited=0, **fields)
            counts["updated"] += 1
        elif existing["edited"] or existing["state"] != "draft":
            counts["kept"] += 1
        else:
            db.save_listing(conn, item_id, platform, **fields)
            counts["updated"] += 1
    return counts


def _fill_item(conn: sqlite3.Connection, item: dict[str, Any], analysis: Analysis) -> dict[str, Any]:
    """Fill blanks from the analysis. Anything the seller already entered is left alone."""
    changes: dict[str, Any] = {}
    if item["category"] not in CATEGORIES:
        changes["category"] = analysis.category
    if not item["brand"] and analysis.brand:
        changes["brand"] = analysis.brand
    if not item["model"] and analysis.model:
        changes["model"] = analysis.model
    if not item["title"]:
        changes["title"] = " ".join(p for p in (changes.get("brand", item["brand"]), changes.get("model", item["model"])) if p) or analysis.product_name
    return db.update_item(conn, item["id"], touch=False, **changes) if changes else item


def run_analysis(conn: sqlite3.Connection, item_id: int, settings: Settings, client: Any = None) -> dict[str, Any]:
    """Read the photos, store the analysis, draft every platform, and set the item's status."""
    item = db.get_item(conn, item_id)
    if item is None:
        raise KeyError(item_id)
    photos = db.list_photos(conn, item_id)
    analysis = vision.analyze(item, photos, settings, client)

    if item["category"] in CATEGORIES and analysis.category != item["category"] and analysis.category != "other":
        analysis.unknowns.append(f"The photos look like {CATEGORIES[analysis.category].label.lower()}, but this item is filed as {CATEGORIES[item['category']].label.lower()}. Check the category.")

    reads = [(analysis.photo_ids[r.photo_number - 1], r.shot, r.quality) for r in analysis.photos]
    db.set_photo_reads(conn, reads)
    db.save_analysis(conn, item_id, analysis.mode, analysis.model_used, analysis.model_dump())
    item = _fill_item(conn, item, analysis)

    photos = db.list_photos(conn, item_id)
    drafts = drafting.draft_listings(item, analysis, photos, settings, client)
    counts = store_drafts(conn, item_id, drafts)
    refresh_status(conn, item_id)
    return {"analysis": analysis, "drafts": counts}


def redraft(conn: sqlite3.Connection, item_id: int, settings: Settings, client: Any = None, force: bool = False) -> dict[str, int]:
    """Rewrite drafts from the stored analysis and the item's current details. No photo re-read."""
    item = db.get_item(conn, item_id)
    analysis = stored_analysis(conn, item_id)
    if item is None or analysis is None:
        raise ValueError("Analyse the photos first.")
    drafts = drafting.draft_listings(item, analysis, db.list_photos(conn, item_id), settings, client)
    counts = store_drafts(conn, item_id, drafts, force=force)
    refresh_status(conn, item_id)
    return counts
