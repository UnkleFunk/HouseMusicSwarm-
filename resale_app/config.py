"""Runtime settings, read from the environment each time so tests can override them."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent

# Opus is the Claude API default for this kind of image-reading work. For a cheaper
# pass, set RESALE_VISION_MODEL / RESALE_DRAFT_MODEL to claude-sonnet-5-5.
DEFAULT_MODEL = "claude-opus-5-5"


@dataclass(frozen=True)
class Settings:
    home: Path
    drop_dir: Path
    mode: str  # "live" calls Claude; "demo" runs the offline stand-in
    vision_model: str
    draft_model: str
    max_vision_photos: int
    settle_seconds: float  # wait this long after the last dropped photo before analysing
    batch_gap_seconds: float  # loose drop-folder photos closer together than this are one item
    access_token: str
    worker_enabled: bool

    @property
    def db_path(self) -> Path:
        return self.home / "resale.sqlite3"

    @property
    def media_dir(self) -> Path:
        return self.home / "media"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_mode() -> str:
    explicit = _env("RESALE_MODE").lower()
    if explicit in ("live", "demo"):
        return explicit
    if explicit:
        raise ValueError(f"RESALE_MODE must be 'live' or 'demo', got {explicit!r}")
    # No explicit choice: use Claude when a key is present, otherwise stay offline.
    # (If you log in with `ant auth login` instead of a key, set RESALE_MODE=live.)
    return "live" if _env("ANTHROPIC_API_KEY") else "demo"


def get_settings() -> Settings:
    home = Path(_env("RESALE_HOME") or PACKAGE_DIR / "data").expanduser()
    drop = Path(_env("RESALE_DROP_DIR") or "~/ResaleDrop").expanduser()
    return Settings(
        home=home,
        drop_dir=drop,
        mode=resolve_mode(),
        vision_model=_env("RESALE_VISION_MODEL") or DEFAULT_MODEL,
        draft_model=_env("RESALE_DRAFT_MODEL") or DEFAULT_MODEL,
        max_vision_photos=int(_env("RESALE_MAX_VISION_PHOTOS") or 12),
        settle_seconds=float(_env("RESALE_SETTLE_SECONDS") or 45),
        batch_gap_seconds=float(_env("RESALE_BATCH_GAP_SECONDS") or 120),
        access_token=_env("RESALE_ACCESS_TOKEN"),
        worker_enabled=_env("RESALE_WORKER", "1") != "0",
    )


def load_env_files() -> None:
    """Fill os.environ from resale_app/.env then the repo-root .env (never overriding)."""
    for path in (PACKAGE_DIR / ".env", REPO_ROOT / ".env"):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
