"""Offline stand-in for the vision step, used in demo mode and for trying the app without a key.

It does NOT look at pixels. It reads the details the seller typed, plus hints in the photo
file names (socket.jpg, tag_size.jpg, soles.jpg, ...), and produces an Analysis the rest of
the pipeline treats exactly like a real one. The review UI says so in a banner.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .drafting import NOT_WORKING_RE
from .models import Analysis

_BOARD_WORDS = re.compile(r"motherboard|mobo|\bam[45]\b|lga\d|\b[xzbh]\d{3}\b|chipset|socket", re.I)
_CLOTHING_WORDS = re.compile(r"hoodie|shirt|jacket|jeans|\btee\b|sweater|pants|shorts|coat|fleece|sweatshirt", re.I)
_SNEAKER_WORDS = re.compile(r"air max|jordan|\bdunk\b|yeezy|sneaker|shoe|runner|trainer|new balance|asics|converse", re.I)

# Checked in this order, so "insole" wins over "sole" and "size" over "tag".
_SHOT_TOKENS: list[tuple[str, str]] = [
    ("socket", "socket"), ("serial", "serial_sticker"), ("sticker", "serial_sticker"),
    ("ram", "ram_slots"), ("accessories", "accessories"), ("included", "accessories"),
    ("size", "size_tag"), ("care", "size_tag"), ("brand", "brand_tag"), ("tag", "brand_tag"),
    ("flaw", "flaw_closeup"), ("closeup", "flaw_closeup"),
    ("insole", "insoles"), ("insoles", "insoles"), ("sole", "soles"), ("soles", "soles"),
    ("outsole", "soles"), ("box", "box_label"), ("label", "box_label"),
    ("tongue", "tongue_label"), ("heel", "heel"), ("toe", "toe_box"), ("pair", "pair_top"),
    ("measure", "measurements"), ("measurements", "measurements"), ("detail", "detail"),
    ("io", "io"), ("side", "side"), ("back", "back"), ("front", "front"),
]
_FLAW_WORDS = re.compile(
    r"scratch|scuff|pilling|stain|fade|faded|bent|crease|yellow|hole|tear|torn|crack|chip|dent|burn|worn|wear|missing|stuck|frayed|discolor",
    re.I,
)
_MODERATE = re.compile(r"deep|large|big|major|crack|hole|torn|burn|missing|bent", re.I)
_CHIPSET_SOCKET = {
    "x570": "AM4", "b550": "AM4", "b450": "AM4", "x470": "AM4", "a520": "AM4", "b350": "AM4", "x370": "AM4",
    "x670": "AM5", "b650": "AM5", "a620": "AM5",
    "z790": "LGA1700", "b760": "LGA1700", "z690": "LGA1700", "b660": "LGA1700", "h610": "LGA1700",
    "z390": "LGA1151", "z370": "LGA1151", "b365": "LGA1151", "h370": "LGA1151",
}
_KV = re.compile(r"(?i)\b(socket|chipset|form factor|size|colou?r|colorway|material|fabric)\s*[:=]\s*([^.;\n]+)")
_STYLE_CODE = re.compile(r"\b[A-Z]{2}\d{4}-\d{3}\b")
_SERIAL = re.compile(r"(?i)\bserial(?: number)?\s*[:#]?\s*([A-Z0-9-]{6,})")


def _guess_category(text: str) -> str:
    if _SNEAKER_WORDS.search(text):
        return "sneakers"
    if _CLOTHING_WORDS.search(text):
        return "clothing"
    if _BOARD_WORDS.search(text):
        return "board"
    return "other"


def _shot_for(stem: str) -> str | None:
    tokens = set(re.split(r"[^a-z0-9]+", stem.lower()))
    for token, shot in _SHOT_TOKENS:
        if token in tokens:
            return shot
    return None


def _quality_for(stem: str) -> str:
    tokens = set(re.split(r"[^a-z0-9]+", stem.lower()))
    for q in ("blurry", "dark", "cropped", "glare"):
        if q in tokens:
            return q
    return "ok"


def analyze_demo(item: dict[str, Any], photos: list[dict[str, Any]]) -> Analysis:
    brand = (item.get("brand") or "").strip()
    model = (item.get("model") or "").strip()
    notes = item.get("notes") or ""
    title = item.get("title") or ""
    text = " ".join([brand, model, title, notes])
    category = item["category"] if item.get("category") in ("board", "clothing", "sneakers", "other") else _guess_category(text)

    photo_reads = []
    flaw_photo = 0
    for number, photo in enumerate(photos, start=1):
        stem = Path(photo.get("original_name") or photo["filename"]).stem
        shot = _shot_for(stem)
        if shot is None:
            shot = ("side" if category == "sneakers" else "front") if number == 1 else "other"
        if shot == "flaw_closeup" and not flaw_photo:
            flaw_photo = number
        photo_reads.append({"photo_number": number, "shot": shot, "quality": _quality_for(stem), "note": ""})

    flaws = []
    # Split on sentence ends, not bare periods, so "M.2" and "v1.2" stay in one piece.
    for sentence in re.split(r"(?<=[.!?])\s+|[;\n]+", notes):
        sentence = sentence.strip().rstrip(".")
        if sentence and _FLAW_WORDS.search(sentence) and not re.search(r"(?i)\bno (visible )?(flaws|scratches|wear)\b", sentence):
            flaws.append({
                "description": sentence[0].upper() + sentence[1:],
                "severity": "moderate" if _MODERATE.search(sentence) else "minor",
                "photo_number": flaw_photo,
            })

    attributes: dict[str, str] = {}
    for key, value in _KV.findall(notes + " " + model):
        name = {"colour": "Color", "color": "Color"}.get(key.lower(), key.title())
        attributes.setdefault(name, value.strip().rstrip(","))
    if category == "board":
        chipset = next((c for c in _CHIPSET_SOCKET if c in text.lower()), None)
        if chipset:
            attributes.setdefault("Chipset", chipset.upper())
            attributes.setdefault("Socket", _CHIPSET_SOCKET[chipset])
    if "Size" not in attributes:
        m = re.search(r"(?i)\bsize\s+([A-Z0-9.]{1,4})\b", notes)
        if m:
            attributes["Size"] = m.group(1)

    model_numbers = []
    if model and re.search(r"\d", model):
        model_numbers.append({"value": model, "kind": "model", "photo_number": 0})
    for code in _STYLE_CODE.findall(text):
        model_numbers.append({"value": code, "kind": "style_code", "photo_number": 0})
    for serial in _SERIAL.findall(notes):
        model_numbers.append({"value": serial, "kind": "serial", "photo_number": 0})

    lowered = notes.lower()
    if NOT_WORKING_RE.search(lowered):
        grade, why = "for_parts", "The notes say it does not work."
    elif re.search(r"new with tags|\bnwt\b|sealed|unused|brand new", lowered):
        grade, why = "new", "The notes say it is unused."
    elif any(f["severity"] == "moderate" for f in flaws):
        grade, why = "fair", "There is at least one flaw that is more than cosmetic."
    elif flaws:
        grade, why = "good", "Light wear only; the flaws listed are minor."
    else:
        grade, why = "good", "No flaws were noted. Check the photos before you accept this grade."

    unknowns = []
    if category == "board":
        unknowns.append("Whether it powers on and boots has not been confirmed.")
    if not brand and not model:
        unknowns.append("Brand and model were not given and could not be read.")

    product_name = {
        "board": "motherboard", "clothing": "garment", "sneakers": "sneakers", "other": "item",
    }[category]
    m = _CLOTHING_WORDS.search(text)
    if category == "clothing" and m:
        product_name = m.group(0).lower()

    return Analysis(
        category=category,
        brand=brand,
        model=model,
        product_name=product_name,
        identification_confidence="medium" if (brand or model) else "low",
        identification_evidence="Demo mode: taken from the details the seller entered, not from the photos.",
        model_numbers=model_numbers,
        label_text=[v for v in (brand, model) if v],
        photos=photo_reads,
        flaws=flaws,
        attributes=[{"name": k, "value": v} for k, v in attributes.items()],
        suggested_condition=grade,
        condition_rationale=why,
        unknowns=unknowns,
        photo_ids=[p["id"] for p in photos],
        mode="demo",
        model_used="demo",
    )
