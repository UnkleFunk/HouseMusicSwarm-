"""Copy-paste listing packs, one per platform.

A pack is every *approved* listing for a platform as plain text (title, condition, description,
item specifics, keywords, photo order) plus a zip that also carries the photos renamed in upload
order (01_front.jpg, 02_socket.jpg, ...). Nothing here posts anywhere.
"""

from __future__ import annotations

import io
import re
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import db, images
from .categories import GRADES, shot_label
from .config import Settings
from .platforms import PLATFORMS, Platform


@dataclass
class PackPhoto:
    number: int
    filename: str  # stored filename
    export_name: str  # name inside the zip
    label: str


@dataclass
class PackEntry:
    item: dict[str, Any]
    listing: dict[str, Any]
    photos: list[PackPhoto]


def slugify(text: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or fallback


def build_entries(conn: sqlite3.Connection, platform_id: str, states: tuple[str, ...] = ("approved",)) -> list[PackEntry]:
    if platform_id not in PLATFORMS:
        raise KeyError(platform_id)
    entries = []
    for listing in db.list_listings(conn, platform=platform_id):
        if listing["state"] not in states:
            continue
        item = db.get_item(conn, listing["item_id"])
        by_id = {p["id"]: p for p in db.list_photos(conn, item["id"])}
        photos = []
        for number, pid in enumerate(listing["photo_order"], start=1):
            photo = by_id.get(pid)
            if photo is None:
                continue
            label = shot_label(item["category"], photo.get("shot"))
            ext = Path(photo["filename"]).suffix
            name = f"{number:02d}_{slugify(label, 'photo')}{ext}"
            photos.append(PackPhoto(number, photo["filename"], name, label))
        entries.append(PackEntry(item, listing, photos))
    return entries


def listing_text(entry: PackEntry, platform: Platform) -> str:
    item, listing = entry.item, entry.listing
    grade = listing.get("condition_grade") or item.get("condition") or "good"
    lines = [
        f"=== {item['sku']}  {item['title'] or item['model'] or ''} ({platform.label}) ===",
        "",
        f"TITLE ({len(listing['title'])}/{platform.title_max})",
        listing["title"],
        "",
        f"CONDITION  {platform.condition_labels.get(grade, GRADES[grade].label)}   [{GRADES[grade].label}]",
    ]
    if listing.get("price_cents") is not None:
        lines += ["", f"PRICE  {db.format_money(listing['price_cents'])}"]
    lines += ["", f"DESCRIPTION ({len(listing['description'])}/{platform.desc_max})", listing["description"]]
    if listing["specs"]:
        lines += ["", "ITEM SPECIFICS"] + [f"{s['name']}: {s['value']}" for s in listing["specs"]]
    if listing["keywords"]:
        lines += ["", "KEYWORDS", ", ".join(listing["keywords"])]
    if entry.photos:
        lines += ["", "PHOTO ORDER"] + [f"{p.number}. {p.export_name}  ({p.label})" for p in entry.photos]
    return "\n".join(lines).rstrip() + "\n"


def pack_text(entries: list[PackEntry], platform: Platform) -> str:
    if not entries:
        return f"No approved {platform.label} listings yet.\n"
    return ("\n\n" + "-" * 72 + "\n\n").join(listing_text(e, platform) for e in entries)


def entry_dir(entry: PackEntry) -> str:
    return f"{entry.item['sku']}_{slugify(entry.item['title'] or entry.item['model'])}"


def build_zip(conn: sqlite3.Connection, settings: Settings, platform_id: str) -> bytes:
    platform = PLATFORMS[platform_id]
    entries = build_entries(conn, platform_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.txt",
            f"{platform.label} listing pack: {len(entries)} approved listing(s).\n"
            "Each folder has listing.txt (copy each section into the form) and photos/ named in upload order.\n"
            "all_listings.txt has every listing in one file.\n",
        )
        zf.writestr("all_listings.txt", pack_text(entries, platform))
        for entry in entries:
            base = entry_dir(entry)
            zf.writestr(f"{base}/listing.txt", listing_text(entry, platform))
            for photo in entry.photos:
                path = images.media_path(settings, entry.item["sku"], "orig", photo.filename)
                if path:
                    zf.write(path, f"{base}/photos/{photo.export_name}")
    return buf.getvalue()


def write_pack(conn: sqlite3.Connection, settings: Settings, platform_id: str, out_dir: Path) -> Path:
    """Unzip-equivalent to disk, for the CLI."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(build_zip(conn, settings, platform_id))) as zf:
        zf.extractall(out_dir)
    return out_dir
