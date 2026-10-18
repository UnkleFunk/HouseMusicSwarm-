"""Demo data: a few made-up items with generated placeholder photos, run through the real pipeline.

Photos are drawn with Pillow (a coloured card with the shot name on it), named like the shots they
stand for, so the offline analyzer can classify them. The demo shows each state the review UI has:
a clean item, an untested board, and items with missing or blurry required shots.
"""

from __future__ import annotations

import io
import sqlite3
from dataclasses import dataclass, replace

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import db, images, pipeline
from .config import Settings


@dataclass(frozen=True)
class DemoItem:
    category: str
    brand: str
    model: str
    notes: str
    cost: str
    photos: tuple[str, ...]
    analyze: bool = True


DEMO_ITEMS = (
    DemoItem(
        "board", "ASUS", "TUF GAMING X570-PLUS",
        "Tested: boots to BIOS, all four RAM slots detected. Small scratch near the M.2 heatsink. Serial: K1MB0123456.",
        "85.00", ("front.jpg", "socket_blurry.jpg", "back.jpg", "io.jpg"),
    ),
    DemoItem(
        "board", "Gigabyte", "B450 AORUS M",
        "Came out of a parts lot. Haven't had a CPU to try it with.",
        "22.50", ("front.jpg", "socket.jpg", "io.jpg", "back.jpg", "serial_sticker.jpg"),
    ),
    DemoItem(
        "clothing", "Carhartt WIP", "Hooded Sweatshirt",
        "Size: L. Color: Heather grey. Light pilling on the cuffs; small faded spot on the left sleeve.",
        "14.00", ("front.jpg", "back.jpg", "brand_tag.jpg", "size_tag.jpg", "flaw_closeup.jpg"),
    ),
    DemoItem(
        "sneakers", "Nike", "Air Max 90",
        "Size: 10. Colorway: White/Black. Style code CN8490-100. Scuffs on the toe box and some yellowing on the midsole. No box.",
        "40.00", ("side.jpg", "soles.jpg", "insoles.jpg"),
    ),
    DemoItem("unknown", "", "", "Found in the garage lot. Not looked at yet.", "5.00", ("IMG_0001.jpg", "IMG_0002.jpg"), analyze=False),
)

_COLORS = ((52, 94, 128), (96, 70, 120), (60, 110, 84), (128, 92, 56), (110, 64, 74), (70, 78, 96))


def make_photo(label: str, index: int) -> bytes:
    """A readable placeholder picture. 'blurry' in the name makes it blurry on purpose."""
    img = Image.new("RGB", (1000, 1000), _COLORS[index % len(_COLORS)])
    draw = ImageDraw.Draw(img)
    draw.rectangle((50, 50, 950, 950), outline=(255, 255, 255), width=6)
    draw.ellipse((300, 200, 700, 600), outline=(255, 255, 255), width=8)
    big = ImageFont.load_default(size=72)
    small = ImageFont.load_default(size=40)
    draw.text((500, 120), "DEMO PHOTO", fill=(255, 255, 255), font=small, anchor="mm")
    draw.text((500, 760), label.replace("_", " "), fill=(255, 255, 255), font=big, anchor="mm")
    if "blurry" in label:
        img = img.filter(ImageFilter.GaussianBlur(14))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def seed_demo(conn: sqlite3.Connection, settings: Settings) -> int:
    """Create the demo items. Does nothing if the database already has items. Returns items created."""
    if conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]:
        return 0
    settings = replace(settings, mode="demo")  # never spend API calls on placeholder pictures
    created = 0
    for n, demo in enumerate(DEMO_ITEMS):
        title = " ".join(p for p in (demo.brand, demo.model) if p) or "Garage lot find"
        item = db.create_item(
            conn, category=demo.category, brand=demo.brand, model=demo.model, title=title,
            notes=demo.notes, cost_basis_cents=db.parse_money(demo.cost), intake_key=f"demo:{n}",
        )
        for i, name in enumerate(demo.photos):
            images.store_photo(conn, settings, item, name, make_photo(name.rsplit(".", 1)[0], n + i))
        if demo.analyze:
            pipeline.run_analysis(conn, item["id"], settings)
            db.update_item(conn, item["id"], touch=False, analysis_status="done")
        created += 1
    return created
