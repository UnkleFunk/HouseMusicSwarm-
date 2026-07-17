"""
Unkle Funk — Discovery Module
==============================

Polls Beatport and Traxsource for new release candidates, normalizes
results into scoring.Track objects, hands off to the scorer.

Access route: SearchAPI.io (https://www.searchapi.io/) — a paid search
API that can query Google/Bing results scoped to a site, which lets us
pull recent Beatport/Traxsource release listings without needing
gated partner API access. This is the pragmatic path: works today, no
approval wait.

Requires: SEARCH_API_KEY environment variable (per VISION.md, this
was already planned — just needs the key set).

If/when Beatport partner API access is granted, swap this module's
`_fetch_beatport()` internals only — the Track normalization and
everything downstream stays the same.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from scoring import Track, Scorer

SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY", "")
SEARCH_API_URL = "https://www.searchapi.io/api/v1/search"

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

RAW_CANDIDATES_PATH = Path(__file__).parent / "raw_candidates.json"
RANKED_OUTPUT_PATH = Path(__file__).parent / "ranked_top_30.json"

# Labels we auto-search for new releases against — pulled from profile
# tier lists at runtime, but hardcoded fallback here in case profile
# load fails mid-run.
FALLBACK_LABELS = [
    "HOUSEu", "Toolroom Records", "Fool's Paradise", "Glasgow Underground",
    "Jackie's", "Defected Records", "Defined Records", "Caboose Records",
]


class DiscoveryError(Exception):
    pass


def _search(query: str, num: int = 20) -> list[dict]:
    """Run a single SearchAPI.io query, return raw organic results."""
    if not SEARCH_API_KEY:
        raise DiscoveryError(
            "SEARCH_API_KEY not set. Export it in your shell profile or "
            "pass it to the review UI's config screen."
        )
    params = {
        "engine": "google",
        "q": query,
        "api_key": SEARCH_API_KEY,
        "num": num,
    }
    resp = requests.get(SEARCH_API_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("organic_results", [])


def _search_site(site: str, label_or_artist: str, days_back: int = 14) -> list[dict]:
    """Search a specific site for recent releases from a label or artist."""
    query = f'site:{site} "{label_or_artist}" release'
    try:
        return _search(query)
    except DiscoveryError:
        raise
    except Exception as e:
        print(f"  ⚠ search failed for {label_or_artist} on {site}: {e}")
        return []


# ---------------------------------------------------------------
# Beatport
# ---------------------------------------------------------------

def _parse_beatport_result(result: dict) -> Track | None:
    """Best-effort extraction of track metadata from a search snippet.
    SearchAPI gives us title + snippet text, not structured data, so
    this is regex-based and will miss fields — that's fine, missing
    fields just get neutral scores from the scorer."""
    title_raw = result.get("title", "")
    link = result.get("link", "")
    snippet = result.get("snippet", "")

    if "beatport.com/track/" not in link:
        return None

    # Beatport titles are usually "Artist - Track Name | Beatport"
    m = re.match(r"^(.+?)\s*[-–]\s*(.+?)(\s*\|.*)?$", title_raw)
    artist = m.group(1).strip() if m else "Unknown"
    track_title = m.group(2).strip() if m else title_raw

    # BPM sometimes appears in snippet as "128 BPM" or "BPM: 128"
    bpm_match = re.search(r"(\d{2,3})\s*BPM", snippet, re.IGNORECASE)
    bpm = float(bpm_match.group(1)) if bpm_match else 122.0  # neutral default

    # Key sometimes appears as "Key: 8A" or similar Camelot notation
    key_match = re.search(r"\b(\d{1,2}[AB])\b", snippet)
    key = key_match.group(1) if key_match else ""

    track_id = link.split("/track/")[-1].split("/")[0] if "/track/" in link else link

    return Track(
        id=f"bp_{track_id}",
        title=track_title,
        artist=artist,
        label="",  # filled in by caller (we search per-label)
        bpm=bpm,
        key=key,
        duration_seconds=420,  # unknown from snippet; neutral default
        release_date=date.today().isoformat(),  # unknown; assume recent
        preview_url=link,
        source="beatport",
    )


def fetch_beatport_for_label(label: str, days_back: int = 14) -> list[Track]:
    results = _search_site("beatport.com", label, days_back)
    tracks = []
    for r in results:
        t = _parse_beatport_result(r)
        if t:
            t.label = label
            tracks.append(t)
    return tracks


# ---------------------------------------------------------------
# Traxsource
# ---------------------------------------------------------------

def _parse_traxsource_result(result: dict) -> Track | None:
    title_raw = result.get("title", "")
    link = result.get("link", "")
    snippet = result.get("snippet", "")

    if "traxsource.com/track/" not in link:
        return None

    m = re.match(r"^(.+?)\s*[-–]\s*(.+?)(\s*\|.*)?$", title_raw)
    artist = m.group(1).strip() if m else "Unknown"
    track_title = m.group(2).strip() if m else title_raw

    bpm_match = re.search(r"(\d{2,3})\s*BPM", snippet, re.IGNORECASE)
    bpm = float(bpm_match.group(1)) if bpm_match else 122.0

    key_match = re.search(r"\b(\d{1,2}[AB])\b", snippet)
    key = key_match.group(1) if key_match else ""

    track_id = link.split("/track/")[-1].split("/")[0] if "/track/" in link else link

    return Track(
        id=f"tx_{track_id}",
        title=track_title,
        artist=artist,
        label="",
        bpm=bpm,
        key=key,
        duration_seconds=420,
        release_date=date.today().isoformat(),
        preview_url=link,
        source="traxsource",
    )


def fetch_traxsource_for_label(label: str, days_back: int = 14) -> list[Track]:
    results = _search_site("traxsource.com", label, days_back)
    tracks = []
    for r in results:
        t = _parse_traxsource_result(r)
        if t:
            t.label = label
            tracks.append(t)
    return tracks


# ---------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------

def get_search_labels() -> list[str]:
    """Pull Tier 1 + Tier 2 label names from profile.yaml, plus
    high-affinity artists (searched by name too — Symms/Kinky Movement
    releases matter regardless of label)."""
    try:
        scorer = Scorer.load_default()
        tier1 = scorer.profile["labels"]["tiers"]["tier_1"]["names"]
        tier2 = scorer.profile["labels"]["tiers"]["tier_2"]["names"]
        artists = list(scorer.profile["artists"].get("seed_scores", {}).keys())
        # Only search for artists with high affinity (>=90) — searching
        # every neutral artist would blow the search budget for little gain
        high_affinity_artists = [
            a for a, s in scorer.profile["artists"]["seed_scores"].items()
            if s >= 90
        ]
        return list(tier1) + list(tier2) + high_affinity_artists
    except Exception as e:
        print(f"  ⚠ profile load failed ({e}), using fallback label list")
        return FALLBACK_LABELS


def run_discovery(days_back: int = 14, max_searches: int = 40) -> list[Track]:
    """Main entry point. Searches all Tier 1/2 labels + high-affinity
    artists across both platforms, dedupes, returns raw candidate list.

    max_searches caps total API calls — each label/artist costs 2 calls
    (Beatport + Traxsource), so 40 searches ≈ 20 labels/artists covered.
    """
    labels = get_search_labels()[: max_searches // 2]
    print(f"Searching {len(labels)} labels/artists across Beatport + Traxsource...")

    all_tracks: list[Track] = []
    seen_ids: set[str] = set()

    for i, label in enumerate(labels, 1):
        print(f"  [{i}/{len(labels)}] {label}")
        for fetch_fn in (fetch_beatport_for_label, fetch_traxsource_for_label):
            try:
                tracks = fetch_fn(label, days_back)
            except DiscoveryError:
                raise  # no API key — stop immediately, don't burn calls
            except Exception as e:
                print(f"    ⚠ {fetch_fn.__name__} failed: {e}")
                continue
            for t in tracks:
                if t.id not in seen_ids:
                    seen_ids.add(t.id)
                    all_tracks.append(t)
            time.sleep(0.3)  # polite rate limit

    print(f"Found {len(all_tracks)} unique candidates.")

    # Persist raw candidates for debugging / re-scoring without re-fetching
    RAW_CANDIDATES_PATH.write_text(
        json.dumps([asdict(t) for t in all_tracks], indent=2)
    )
    return all_tracks


def score_and_rank(tracks: list[Track], top_n: int = 30) -> list[dict]:
    """Score all candidates, return top N as JSON-serializable dicts
    with score breakdowns attached — this is what the review UI reads."""
    scorer = Scorer.load_default()
    scored = []
    for t in tracks:
        breakdown = scorer.score(t)
        if breakdown.rejected:
            continue
        scored.append({
            "track": asdict(t),
            "score": round(breakdown.total, 1),
            "explain": breakdown.explain(),
            "features": breakdown.features,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_n]

    RANKED_OUTPUT_PATH.write_text(json.dumps(top, indent=2))
    print(f"Ranked and saved top {len(top)} candidates to {RANKED_OUTPUT_PATH.name}")
    return top


if __name__ == "__main__":
    if not SEARCH_API_KEY:
        print("SEARCH_API_KEY not set.")
        print("Export it first:")
        print("  export SEARCH_API_KEY=your_key_here")
        print("Get a key at https://www.searchapi.io/")
        raise SystemExit(1)

    tracks = run_discovery()
    if tracks:
        top = score_and_rank(tracks)
        print(f"\nTop 5 preview:")
        for entry in top[:5]:
            t = entry["track"]
            print(f"  {entry['score']:5.1f}  {t['artist']} — {t['title']} [{t['label']}]")
