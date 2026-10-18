"""Photo storage: keep the original, make a thumbnail and a vision-sized copy.

Phone photos are 12MP+ and often HEIC. We keep the original bytes (JPEG/PNG/WebP) for
the marketplace upload, convert HEIC to JPEG, apply EXIF rotation to the derived copies,
and send only a ~1568px copy to the vision model.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from . import db
from .config import Settings

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_UPLOAD_BYTES = 40 * 1024 * 1024
VISION_EDGE = 1568
THUMB_EDGE = 480
VARIANTS = ("orig", "thumb", "vision")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_SKU = re.compile(r"^RS-\d{4,}$")

try:  # iPhone photos arrive as HEIC; pillow-heif teaches Pillow to read them.
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_SUPPORTED = True
except Exception:  # pragma: no cover - depends on the install
    HEIF_SUPPORTED = False


class ImageError(ValueError):
    """The upload is not a usable image."""


@dataclass
class StoredPhoto:
    photo: dict
    duplicate: bool = False


def is_image_name(name: str) -> bool:
    return Path(name).suffix.lower() in ALLOWED_EXTS


def _derived(img: Image.Image, edge: int) -> Image.Image:
    out = ImageOps.exif_transpose(img)
    if out.mode not in ("RGB", "L"):
        out = out.convert("RGB")
    out.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    return out


def store_photo(conn, settings: Settings, item: dict, original_name: str, data: bytes) -> StoredPhoto:
    """Validate, de-duplicate and write one photo for an item. Raises ImageError if unusable."""
    if not data:
        raise ImageError(f"{original_name}: empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageError(f"{original_name}: larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        hint = " (HEIC needs pillow-heif installed)" if Path(original_name).suffix.lower() in (".heic", ".heif") and not HEIF_SUPPORTED else ""
        raise ImageError(f"{original_name}: not a readable image{hint}") from exc

    sha = hashlib.sha256(data).hexdigest()
    if db.photo_exists(conn, item["id"], sha):
        existing = conn.execute("SELECT * FROM photos WHERE item_id = ? AND sha256 = ?", (item["id"], sha)).fetchone()
        return StoredPhoto(dict(existing), duplicate=True)

    fmt = (img.format or "").upper()
    if fmt in ("JPEG", "PNG", "WEBP"):
        ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[fmt]
        original_bytes = data
    else:  # HEIC and anything else Pillow can read: store as a JPEG
        ext = ".jpg"
        buf = io.BytesIO()
        _full = ImageOps.exif_transpose(img)
        _full.convert("RGB").save(buf, "JPEG", quality=92)
        original_bytes = buf.getvalue()

    stem = sha[:16]
    filename = f"{stem}{ext}"
    base = settings.media_dir / item["sku"]
    for variant in VARIANTS:
        (base / variant).mkdir(parents=True, exist_ok=True)
    (base / "orig" / filename).write_bytes(original_bytes)
    _derived(img, THUMB_EDGE).save(base / "thumb" / f"{stem}.jpg", "JPEG", quality=82)
    _derived(img, VISION_EDGE).save(base / "vision" / f"{stem}.jpg", "JPEG", quality=88)

    photo = db.add_photo(conn, item["id"], filename, Path(original_name).name, sha)
    return StoredPhoto(photo)


def media_path(settings: Settings, sku: str, variant: str, filename: str) -> Path | None:
    """Resolve a media URL to a file, or None if it is malformed or missing."""
    if variant not in VARIANTS or not _SAFE_SKU.match(sku) or not _SAFE_NAME.match(filename):
        return None
    name = filename if variant == "orig" else f"{Path(filename).stem}.jpg"
    path = settings.media_dir / sku / variant / name
    return path if path.is_file() else None


def vision_bytes(settings: Settings, sku: str, filename: str) -> bytes:
    path = media_path(settings, sku, "vision", filename)
    if path is None:
        raise FileNotFoundError(f"{sku}/{filename}: vision copy missing")
    return path.read_bytes()


def remove_photo_files(settings: Settings, sku: str, filename: str) -> None:
    for variant in VARIANTS:
        path = media_path(settings, sku, variant, filename)
        if path:
            path.unlink(missing_ok=True)
