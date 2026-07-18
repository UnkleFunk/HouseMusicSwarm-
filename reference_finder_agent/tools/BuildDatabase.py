"""Scrape Beatport/Traxsource charts, download previews, extract features, index in ChromaDB.

Strategy (informed by current 2026 page structures):
- Beatport: Next.js app. The full chart is embedded in <script id="__NEXT_DATA__">.
  We load with Playwright (domcontentloaded), read that JSON, and recursively find
  the track list. Preview MP3s come from each track's `sample_url`.
- Traxsource: server-rendered HTML, parsed with BeautifulSoup (best-effort).
- All downloads use the Playwright browser request context (browser TLS/headers),
  which avoids the 403s that plain httpx hits on these sites.
- Never uses `networkidle` (it never settles on these sites — that was the old bug).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any

try:
    from agency_swarm.tools import BaseTool
except ModuleNotFoundError:
    from pydantic import BaseModel as BaseTool  # type: ignore[assignment]
from pydantic import Field

REFS_DIR = Path.home() / ".housemusic_refs"
PREVIEW_DIR = REFS_DIR / "previews"
CHROMADB_DIR = REFS_DIR / "chromadb"
DEBUG_DIR = REFS_DIR / "debug"
COLLECTION_NAME = "house_references"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Genre slugs + numeric IDs per platform
BEATPORT_GENRES: dict[str, tuple[str, int]] = {
    "house":      ("house", 5),
    "deep-house": ("deep-house", 12),
    "tech-house": ("tech-house", 11),
}

TRAXSOURCE_GENRES: dict[str, tuple[str, int]] = {
    "house":         ("house", 2),
    "deep-house":    ("deep-house", 13),
    "tech-house":    ("tech-house", 18),
    "funky-minimal": ("funky-house", 9),
}


class BuildDatabase(BaseTool):
    """Scrape chart tracks from Beatport and Traxsource, download previews, and index
    them in a local ChromaDB vector database for reference matching.

    Run once to populate (~30-60 min for a full corpus). Re-run with refresh=True to
    upsert new chart entries.
    """

    sources: str = Field(
        default="beatport,traxsource",
        description="Comma-separated sources: beatport, traxsource",
    )
    genres: str = Field(
        default="house,deep-house,tech-house",
        description="Comma-separated genre slugs",
    )
    max_tracks_per_genre: int = Field(default=100, ge=10, le=200)
    refresh: bool = Field(default=False, description="Re-scrape and upsert even if already indexed")

    def run(self) -> str:
        for d in (PREVIEW_DIR, CHROMADB_DIR, DEBUG_DIR):
            d.mkdir(parents=True, exist_ok=True)

        source_list = [s.strip().lower() for s in self.sources.split(",") if s.strip()]
        genre_list = [g.strip().lower() for g in self.genres.split(",") if g.strip()]

        results = asyncio.run(self._build(source_list, genre_list))
        return json.dumps(results)

    # ── Main pipeline ──────────────────────────────────────────────────────

    async def _build(self, sources: list[str], genres: list[str]) -> dict:
        import chromadb
        from playwright.async_api import async_playwright
        from reference_finder_agent.audio_utils import extract_features

        client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
        collection = client.get_or_create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )

        added = skipped = 0
        errors: list[str] = []
        all_tracks: list[dict] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=_USER_AGENT,
                viewport={"width": 1440, "height": 900},
                locale="en-US",
            )

            # ── Scrape all requested source/genre combinations ──
            for source in sources:
                for genre in genres:
                    label = f"{source}/{genre}"
                    try:
                        print(f"  Scraping {label} …", flush=True)
                        if source == "beatport":
                            tracks = await self._scrape_beatport(context, genre)
                        elif source == "traxsource":
                            tracks = await self._scrape_traxsource(context, genre)
                        else:
                            errors.append(f"Unknown source: {source}")
                            continue
                        print(f"    → found {len(tracks)} tracks", flush=True)
                        all_tracks.extend(tracks)
                    except Exception as exc:
                        msg = f"{label}: {type(exc).__name__}: {exc}"
                        print(f"    ✗ {msg}", flush=True)
                        errors.append(msg)

            # ── Deduplicate ──
            seen: set[str] = set()
            unique: list[dict] = []
            for t in all_tracks:
                h = _track_hash(t["artist"], t["title"])
                if h not in seen:
                    seen.add(h)
                    unique.append({**t, "id": h})

            print(f"  {len(unique)} unique tracks. Downloading previews + analyzing …", flush=True)

            # ── Download + analyze + index ──
            for i, track in enumerate(unique, 1):
                track_id = track["id"]

                if not self.refresh and collection.get(ids=[track_id])["ids"]:
                    skipped += 1
                    continue

                preview_url = track.get("preview_url", "")
                if not preview_url:
                    skipped += 1
                    continue

                preview_path = PREVIEW_DIR / f"{track_id}.mp3"
                if not preview_path.exists():
                    ok = await _download_via_browser(context, preview_url, preview_path)
                    if not ok:
                        errors.append(f"Preview download failed: {track['title']}")
                        continue

                try:
                    features = extract_features(str(preview_path))
                except Exception as exc:
                    errors.append(f"Feature extraction failed for {track['title']}: {exc}")
                    continue

                collection.upsert(
                    ids=[track_id],
                    embeddings=[features["vector"]],
                    metadatas=[_build_meta(track, features, preview_path)],
                    documents=[f"{track['title']} by {track['artist']}"],
                )
                added += 1
                if added % 10 == 0:
                    print(f"    indexed {added} …", flush=True)

            await browser.close()

        return {
            "added": added,
            "skipped": skipped,
            "errors": errors[:25],
            "total_in_db": collection.count(),
        }

    # ── Beatport ───────────────────────────────────────────────────────────

    async def _scrape_beatport(self, context, genre: str) -> list[dict]:
        slug, gid = BEATPORT_GENRES.get(genre, (genre, 0))
        url = f"https://www.beatport.com/genre/{slug}/{gid}/top-100"

        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_selector("#__NEXT_DATA__", timeout=15000)
            raw = await page.locator("#__NEXT_DATA__").text_content()
        finally:
            await page.close()

        if not raw:
            raise RuntimeError("No __NEXT_DATA__ found on Beatport page")

        data = json.loads(raw)
        track_objs = _find_track_list(data)
        if not track_objs:
            _save_debug(f"beatport_{genre}.json", raw)
            raise RuntimeError(
                f"Could not locate track list in __NEXT_DATA__ "
                f"(saved to {DEBUG_DIR}/beatport_{genre}.json)"
            )

        tracks: list[dict] = []
        for pos, obj in enumerate(track_objs[: self.max_tracks_per_genre], 1):
            t = _parse_beatport_track(obj, genre, pos)
            if t:
                tracks.append(t)
        return tracks

    # ── Traxsource (best-effort) ─────────────────────────────────────────────

    async def _scrape_traxsource(self, context, genre: str) -> list[dict]:
        from bs4 import BeautifulSoup

        slug, gid = TRAXSOURCE_GENRES.get(genre, (genre, 0))
        url = f"https://www.traxsource.com/genre/{gid}/{slug}/top"

        page = await context.new_page()
        captured_mp3: dict[str, str] = {}

        # Sniff any preview MP3 responses that fire during load
        def _on_response(resp):
            u = resp.url
            if ".mp3" in u.lower():
                captured_mp3[u.split("/")[-1].split("?")[0]] = u

        page.on("response", _on_response)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            # Wait for any track-row-like container; tolerate variations
            try:
                await page.wait_for_selector(
                    "div.trk-row, div.play-trk, [data-trid], [data-trackid]",
                    timeout=15000,
                )
            except Exception:
                pass
            await page.wait_for_timeout(2500)
            html = await page.content()
        finally:
            await page.close()

        soup = BeautifulSoup(html, "html.parser")
        rows = (
            soup.select("div.trk-row")
            or soup.select("div.play-trk")
            or soup.select("[data-trid]")
            or soup.select("[data-trackid]")
        )
        if not rows:
            _save_debug(f"traxsource_{genre}.html", html)
            raise RuntimeError(
                f"No track rows found on Traxsource page "
                f"(saved to {DEBUG_DIR}/traxsource_{genre}.html for inspection)"
            )

        tracks: list[dict] = []
        for pos, row in enumerate(rows[: self.max_tracks_per_genre], 1):
            t = _parse_traxsource_row(row, genre, pos, captured_mp3)
            if t:
                tracks.append(t)
        return tracks


# ── Beatport JSON parsing ───────────────────────────────────────────────────

def _find_track_list(data: Any) -> list[dict]:
    """Recursively find the longest array of track-like objects in arbitrary JSON.

    Robust against Next.js structure changes — we don't hardcode the path, we look
    for objects that quack like Beatport tracks (have a sample_url, or name+artists).
    """
    best: list[dict] = []

    def _is_track(o: Any) -> bool:
        if not isinstance(o, dict):
            return False
        if "sample_url" in o:
            return True
        return "name" in o and "artists" in o

    def _walk(node: Any) -> None:
        nonlocal best
        if isinstance(node, list):
            if node and sum(_is_track(x) for x in node) >= max(1, len(node) // 2):
                track_items = [x for x in node if _is_track(x)]
                if len(track_items) > len(best):
                    best = track_items
            for x in node:
                _walk(x)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)

    _walk(data)
    return best


def _parse_beatport_track(obj: dict, genre: str, pos: int) -> dict | None:
    try:
        title = obj.get("name", "") or obj.get("title", "")
        mix = obj.get("mix_name", "")
        if mix and mix.lower() not in title.lower():
            title = f"{title} ({mix})"

        artists = obj.get("artists", []) or []
        artist = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict)).strip(", ")

        release = obj.get("release", {}) or {}
        label_obj = release.get("label", {}) if isinstance(release, dict) else {}
        label = label_obj.get("name", "") if isinstance(label_obj, dict) else ""

        bpm = str(obj.get("bpm", "") or "")

        key_obj = obj.get("key", "")
        if isinstance(key_obj, dict):
            key = key_obj.get("name", "") or key_obj.get("camelot_number", "")
        else:
            key = str(key_obj or "")

        tid = obj.get("id", "")
        slug = obj.get("slug", "")
        buy_url = f"https://www.beatport.com/track/{slug}/{tid}" if slug and tid else ""

        preview_url = obj.get("sample_url", "") or ""

        if not title or not artist:
            return None

        return {
            "title": title, "artist": artist, "label": label,
            "bpm": bpm, "key": key, "genre": genre,
            "source": "beatport", "buy_url": buy_url,
            "preview_url": preview_url, "chart_position": pos,
        }
    except Exception:
        return None


# ── Traxsource DOM parsing (best-effort) ─────────────────────────────────────

def _parse_traxsource_row(row, genre: str, pos: int, captured_mp3: dict) -> dict | None:
    try:
        def _text(sel: str) -> str:
            el = row.select_one(sel)
            return el.get_text(strip=True) if el else ""

        # Title: first anchor pointing at a /title/ page
        title = ""
        buy_url = ""
        for a in row.select("a"):
            href = a.get("href", "")
            if "/title/" in href or "/track/" in href:
                title = a.get_text(strip=True)
                buy_url = href if href.startswith("http") else f"https://www.traxsource.com{href}"
                break
        if not title:
            title = _text(".title") or _text(".com-title")

        # Artist
        artist = ", ".join(
            a.get_text(strip=True)
            for a in row.select(".artists a, .artist a")
        ) or _text(".artists") or _text(".artist")

        label = _text(".label a") or _text(".label")
        bpm = _text(".bpm")
        key = _text(".key")

        # Preview: try data attributes, then sniffed network responses by track id
        tid = row.get("data-trid") or row.get("data-trackid") or ""
        preview_url = (
            row.get("data-sample") or row.get("data-preview") or row.get("data-url") or ""
        )
        if not preview_url and tid:
            for fname, u in captured_mp3.items():
                if str(tid) in fname:
                    preview_url = u
                    break

        if not title or not artist:
            return None

        return {
            "title": title, "artist": artist, "label": label,
            "bpm": bpm, "key": key, "genre": genre,
            "source": "traxsource", "buy_url": buy_url,
            "preview_url": preview_url, "chart_position": pos,
        }
    except Exception:
        return None


# ── Shared helpers ───────────────────────────────────────────────────────────

def _build_meta(track: dict, features: dict, preview_path: Path) -> dict:
    return {
        "title": track.get("title", ""),
        "artist": track.get("artist", ""),
        "label": track.get("label", ""),
        "bpm": str(track.get("bpm", "")),
        "key": track.get("key", ""),
        "genre": track.get("genre", ""),
        "source": track.get("source", ""),
        "chart_position": str(track.get("chart_position", "")),
        "buy_url": track.get("buy_url", ""),
        "preview_path": str(preview_path),
        "date_indexed": time.strftime("%Y-%m-%d"),
        "lufs": str(features["metadata"].get("lufs", "")),
        "sub_bass_ratio": str(features["metadata"].get("sub_bass_ratio", "")),
        "bass_ratio": str(features["metadata"].get("bass_ratio", "")),
        "spectrum_json": json.dumps(features["spectrum"]),
    }


def _track_hash(artist: str, title: str) -> str:
    key = f"{artist.lower().strip()}||{title.lower().strip()}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


async def _download_via_browser(context, url: str, dest: Path) -> bool:
    """Download a preview using the browser's request context (browser TLS/headers).

    Far more reliable than plain httpx against bot-protected CDNs.
    """
    try:
        resp = await context.request.get(url, timeout=30000)
        if resp.ok:
            body = await resp.body()
            if len(body) > 1000:
                dest.write_bytes(body)
                return True
        return False
    except Exception:
        return False


def _save_debug(name: str, content: str) -> None:
    try:
        (DEBUG_DIR / name).write_text(content, encoding="utf-8")
    except Exception:
        pass
