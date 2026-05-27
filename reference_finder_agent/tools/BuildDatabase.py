"""Scrape Beatport/Traxsource chart pages, download previews, extract features, and index in ChromaDB."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from agency_swarm.tools import BaseTool
from pydantic import Field

PREVIEW_DIR = Path.home() / ".housemusic_refs" / "previews"
CHROMADB_DIR = Path.home() / ".housemusic_refs" / "chromadb"
COLLECTION_NAME = "house_references"

# Genre IDs used by each platform
BEATPORT_GENRES: dict[str, int] = {
    "house": 5,
    "deep-house": 12,
    "tech-house": 97,
}

TRAXSOURCE_GENRES: dict[str, int] = {
    "house": 2,
    "deep-house": 13,
    "tech-house": 169,
    "funky-minimal": 3,
}


class BuildDatabase(BaseTool):
    """Scrape chart tracks from Beatport and Traxsource, download previews, and index them
    in a local ChromaDB vector database for reference matching.

    Run this once to populate the database (~30-60 minutes for a full 6-month corpus).
    Re-run with refresh=True to upsert new chart entries.
    """

    sources: str = Field(
        default="beatport,traxsource",
        description="Comma-separated list of sources: beatport, traxsource",
    )
    genres: str = Field(
        default="house,deep-house,tech-house",
        description="Comma-separated genre slugs to scrape",
    )
    max_tracks_per_genre: int = Field(default=100, ge=10, le=200)
    refresh: bool = Field(default=False, description="Re-scrape and upsert even if track already indexed")

    def run(self) -> str:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        CHROMADB_DIR.mkdir(parents=True, exist_ok=True)

        source_list = [s.strip() for s in self.sources.split(",")]
        genre_list = [g.strip() for g in self.genres.split(",")]

        results = asyncio.run(self._build(source_list, genre_list))
        return json.dumps(results)

    # ── Internal async pipeline ───────────────────────────────────────────

    async def _build(self, sources: list[str], genres: list[str]) -> dict:
        import chromadb
        from reference_finder_agent.audio_utils import extract_features

        client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
        collection = client.get_or_create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        total_added = 0
        total_skipped = 0
        errors: list[str] = []

        async with httpx.AsyncClient(
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            follow_redirects=True,
        ) as client_http:
            tasks = []
            for source in sources:
                for genre in genres:
                    tasks.append(self._scrape_source(client_http, source, genre))

            track_batches = await asyncio.gather(*tasks, return_exceptions=True)

        all_tracks: list[dict] = []
        for batch in track_batches:
            if isinstance(batch, Exception):
                errors.append(str(batch))
            elif isinstance(batch, list):
                all_tracks.extend(batch)

        # Deduplicate by track hash
        seen: set[str] = set()
        unique_tracks: list[dict] = []
        for t in all_tracks:
            h = _track_hash(t["artist"], t["title"])
            if h not in seen:
                seen.add(h)
                unique_tracks.append({**t, "id": h})

        for track in unique_tracks:
            track_id = track["id"]

            # Skip if already indexed and not refreshing
            if not self.refresh:
                existing = collection.get(ids=[track_id])
                if existing["ids"]:
                    total_skipped += 1
                    continue

            # Download and analyze preview
            preview_path = PREVIEW_DIR / f"{track_id}.mp3"
            if not preview_path.exists() and track.get("preview_url"):
                downloaded = await _download_preview(track["preview_url"], preview_path)
                if not downloaded:
                    errors.append(f"Preview download failed: {track['title']}")
                    continue

            if not preview_path.exists():
                total_skipped += 1
                continue

            try:
                features = extract_features(str(preview_path))
            except Exception as exc:
                errors.append(f"Feature extraction failed for {track['title']}: {exc}")
                continue

            meta = {
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
                # Analysis metadata
                "lufs": str(features["metadata"].get("lufs", "")),
                "sub_bass_ratio": str(features["metadata"].get("sub_bass_ratio", "")),
                "bass_ratio": str(features["metadata"].get("bass_ratio", "")),
                # Store spectrum as JSON string for retrieval
                "spectrum_json": json.dumps(features["spectrum"]),
            }

            collection.upsert(
                ids=[track_id],
                embeddings=[features["vector"]],
                metadatas=[meta],
                documents=[f"{track['title']} by {track['artist']}"],
            )
            total_added += 1

        return {
            "added": total_added,
            "skipped": total_skipped,
            "errors": errors[:20],
            "total_in_db": collection.count(),
        }

    async def _scrape_source(
        self, client: httpx.AsyncClient, source: str, genre: str
    ) -> list[dict]:
        if source == "beatport":
            return await _scrape_beatport(client, genre, self.max_tracks_per_genre)
        if source == "traxsource":
            return await _scrape_traxsource(client, genre, self.max_tracks_per_genre)
        return []


# ── Platform scrapers ─────────────────────────────────────────────────────────

async def _scrape_beatport(client: httpx.AsyncClient, genre: str, limit: int) -> list[dict]:
    """Scrape Beatport top 100 chart for a genre using their internal catalog API."""
    genre_id = BEATPORT_GENRES.get(genre)
    if not genre_id:
        return []

    tracks: list[dict] = []
    page = 1
    per_page = min(limit, 100)

    while len(tracks) < limit:
        url = (
            f"https://api.beatport.com/v4/catalog/charts/top-100/"
            f"?genre_id={genre_id}&page={page}&per_page={per_page}"
        )
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                # Fall back to scraping the HTML chart page via Playwright
                return await _scrape_beatport_playwright(genre, genre_id, limit)
            data = resp.json()
            items = data.get("results", data.get("tracks", []))
            if not items:
                break
        except Exception:
            return await _scrape_beatport_playwright(genre, genre_id, limit)

        for item in items:
            track = _parse_beatport_track(item, genre)
            if track:
                tracks.append(track)
        page += 1
        if len(items) < per_page:
            break

    return tracks[:limit]


def _parse_beatport_track(item: dict, genre: str) -> dict | None:
    try:
        title = item.get("name", "") or item.get("title", "")
        artists = item.get("artists", [])
        artist = ", ".join(a.get("name", "") for a in artists) if artists else item.get("artist_name", "")
        label = (item.get("release", {}) or {}).get("label", {}).get("name", "") or item.get("label_name", "")
        bpm = str(item.get("bpm", ""))
        key = (item.get("key") or {}).get("camelot_number", "") if isinstance(item.get("key"), dict) else str(item.get("key", ""))
        track_id = item.get("id", "")
        slug = item.get("slug", "")
        buy_url = f"https://www.beatport.com/track/{slug}/{track_id}" if slug and track_id else ""
        preview_url = (item.get("preview", {}) or {}).get("mp3", {}).get("url", "") if isinstance(item.get("preview"), dict) else ""
        if not preview_url:
            preview_url = f"https://geo-samples.beatport.com/lofi/{track_id}.LOFI.mp3"

        if not title or not artist:
            return None

        return {
            "title": title,
            "artist": artist,
            "label": label,
            "bpm": bpm,
            "key": key,
            "genre": genre,
            "source": "beatport",
            "buy_url": buy_url,
            "preview_url": preview_url,
            "chart_position": 0,
        }
    except Exception:
        return None


async def _scrape_beatport_playwright(genre: str, genre_id: int, limit: int) -> list[dict]:
    """Fallback: use Playwright to scrape Beatport chart page with JS rendering."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    tracks: list[dict] = []
    url = f"https://www.beatport.com/genre/{genre}/{genre_id}/top-100"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        captured_json: list[dict] = []

        async def handle_response(response):
            if "api.beatport.com" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    if "results" in data or "tracks" in data:
                        captured_json.append(data)
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        await browser.close()

        for data in captured_json:
            items = data.get("results", data.get("tracks", []))
            for item in items:
                track = _parse_beatport_track(item, genre)
                if track:
                    tracks.append(track)

    return tracks[:limit]


async def _scrape_traxsource(client: httpx.AsyncClient, genre: str, limit: int) -> list[dict]:
    """Scrape Traxsource Essential chart via their internal API."""
    genre_id = TRAXSOURCE_GENRES.get(genre)
    if not genre_id:
        return []

    tracks: list[dict] = []

    # Try the internal API endpoint
    url = f"https://www.traxsource.com/api/1.0/track/getChartItems?genre={genre_id}&cn=essential&nt=1&start=0&size={limit}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", data.get("tracks", []))
            for i, item in enumerate(items):
                track = _parse_traxsource_track(item, genre, i + 1)
                if track:
                    tracks.append(track)
            if tracks:
                return tracks
    except Exception:
        pass

    # Playwright fallback
    return await _scrape_traxsource_playwright(genre, genre_id, limit)


def _parse_traxsource_track(item: dict, genre: str, position: int) -> dict | None:
    try:
        title = item.get("title", "") or item.get("trackTitle", "")
        artists_raw = item.get("artists", item.get("artistName", ""))
        if isinstance(artists_raw, list):
            artist = ", ".join(a.get("name", a) if isinstance(a, dict) else a for a in artists_raw)
        else:
            artist = str(artists_raw)
        label = item.get("label", {}).get("name", "") if isinstance(item.get("label"), dict) else str(item.get("label", ""))
        bpm = str(item.get("bpm", ""))
        key = str(item.get("key", ""))
        track_id = item.get("id", item.get("trackId", ""))
        buy_url = f"https://www.traxsource.com/title/{track_id}" if track_id else ""
        preview_url = item.get("previewUrl", item.get("sampleUrl", ""))

        if not title or not artist:
            return None

        return {
            "title": title,
            "artist": artist,
            "label": label,
            "bpm": bpm,
            "key": key,
            "genre": genre,
            "source": "traxsource",
            "buy_url": buy_url,
            "preview_url": preview_url,
            "chart_position": position,
        }
    except Exception:
        return None


async def _scrape_traxsource_playwright(genre: str, genre_id: int, limit: int) -> list[dict]:
    """Fallback: Playwright scraper for Traxsource Essential chart page."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return []

    tracks: list[dict] = []
    url = f"https://www.traxsource.com/genre/{genre_id}/{genre}/chart?cn=essential&nt=1"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        captured: list[dict] = []

        async def handle_response(response):
            if "traxsource.com/api" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    if "items" in data or "tracks" in data:
                        captured.append(data)
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        await browser.close()

        for data in captured:
            items = data.get("items", data.get("tracks", []))
            for i, item in enumerate(items):
                track = _parse_traxsource_track(item, genre, i + 1)
                if track:
                    tracks.append(track)

    return tracks[:limit]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _track_hash(artist: str, title: str) -> str:
    key = f"{artist.lower().strip()}||{title.lower().strip()}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


async def _download_preview(url: str, dest: Path) -> bool:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            resp = await c.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                dest.write_bytes(resp.content)
                return True
        return False
    except Exception:
        return False
