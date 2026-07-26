"""
Unkle Funk — Discovery Module (free, no API key)
=================================================

Fetches new releases directly from Beatport's own genre pages and
parses the embedded __NEXT_DATA__ JSON blob. No search API, no
credentials, no per-request cost.

WHY THIS APPROACH:
An earlier version used SearchAPI.io to *find* Beatport URLs, then
fetched each one to enrich it. That worked but cost ~40 paid requests
per pass, and the cheapest plan was $40/mo for volume we'd never use
(~1.6% utilization). It was also worse data: search snippets don't
carry release dates, so "is this actually new?" was guesswork.

Beatport's genre pages already list new releases, are directly
fetchable with a normal User-Agent, and embed complete structured
metadata: exact BPM, Camelot key, genre, verified artist names, label,
and real release dates. Strictly better, and free.

TRAXSOURCE:
Their site sits behind Cloudflare bot protection that blocks plain
requests AND headless browsers (verified — Playwright gets served the
JS challenge page, not content). No reliable automated path today.
Traxsource stays a manual-check platform. Beatport is the engine.

Usage:
    python3 discovery.py                 # default genres, 1 page each
    python3 discovery.py --pages 3       # deeper pass
    python3 discovery.py --days 14       # only last 14 days of releases
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from scoring import Track, Scorer

LABEL_IDS_PATH = Path(__file__).parent / "label_ids.json"
RAW_CANDIDATES_PATH = Path(__file__).parent / "raw_candidates.json"
RANKED_OUTPUT_PATH = Path(__file__).parent / "ranked_top_30.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Beatport genre slugs + IDs relevant to the Unkle Funk sound.
# Verified working 2026-07. Add or remove freely — each is one page fetch.
GENRES = [
    ("deep-house", 12),
    ("house", 5),
    ("tech-house", 11),
    ("minimal-deep-tech", 14),
    ("afro-house", 89),
    ("organic-house-downtempo", 93),
]

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', re.DOTALL
)

COMPILATION_MARKERS = [
    r"\bvol\.?\s*\d+\b", r"\bcompilation\b", r"various artists",
    r"\byears? of\b", r"\bpresents\b", r"\bessential mix\b",
    r"\bbest of\b", r"\bmixed by\b", r"\bcontinuous mix\b", r"\bdj mix\b",
]
COMPILATION_RE = re.compile("|".join(COMPILATION_MARKERS), re.IGNORECASE)


class DiscoveryError(Exception):
    pass


def _is_compilation(title: str) -> bool:
    return bool(COMPILATION_RE.search(title))


def _find_all_tracks(obj, depth: int = 0, acc: list | None = None) -> list[dict]:
    """Collect every track-shaped object in the Next.js data tree."""
    if acc is None:
        acc = []
    if depth > 10:
        return acc
    if isinstance(obj, dict):
        if "bpm" in obj and "name" in obj and "artists" in obj:
            acc.append(obj)
            return acc
        for v in obj.values():
            _find_all_tracks(v, depth + 1, acc)
    elif isinstance(obj, list):
        for v in obj:
            _find_all_tracks(v, depth + 1, acc)
    return acc


def fetch_genre_page(slug: str, genre_id: int, page: int = 1) -> list[dict]:
    """Fetch one Beatport genre page, return raw track JSON objects."""
    url = f"https://www.beatport.com/genre/{slug}/{genre_id}/tracks"
    if page > 1:
        url += f"?page={page}"
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    except Exception as e:
        print(f"    fetch failed for {slug} p{page}: {e}")
        return []
    if resp.status_code != 200:
        print(f"    HTTP {resp.status_code} for {slug} p{page}")
        return []
    m = NEXT_DATA_RE.search(resp.text)
    if not m:
        print(f"    no structured data for {slug} p{page}")
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        print(f"    malformed JSON for {slug} p{page}")
        return []
    return _find_all_tracks(data)


def _to_track(tj: dict) -> Track | None:
    """Normalize a Beatport track JSON object into a scoring.Track."""
    artists = tj.get("artists", [])
    artist_name = ", ".join(a.get("name", "") for a in artists) if artists else "Unknown"

    title = tj.get("name", "") or ""
    mix_name = tj.get("mix_name", "") or ""
    if _is_compilation(f"{title} {mix_name}"):
        return None
    full_title = (
        f"{title} ({mix_name})"
        if mix_name and mix_name.lower() != "original mix"
        else title
    )

    key_obj = tj.get("key") or {}
    camelot = ""
    if key_obj.get("camelot_number") and key_obj.get("camelot_letter"):
        camelot = f"{key_obj['camelot_number']}{key_obj['camelot_letter']}"

    length = tj.get("length", "") or ""
    duration_seconds = 420
    if ":" in length:
        try:
            parts = length.split(":")
            duration_seconds = int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            pass

    release = tj.get("release") or {}
    label_name = (release.get("label") or {}).get("name", "") or ""
    genre_name = (tj.get("genre") or {}).get("name", "") or ""

    release_date = (
        tj.get("new_release_date")
        or tj.get("publish_date")
        or date.today().isoformat()
    )

    tid = tj.get("id")
    slug = tj.get("slug", "")
    url = f"https://www.beatport.com/track/{slug}/{tid}" if slug and tid else ""

    return Track(
        id=f"bp_{tid or slug or full_title}",
        title=full_title,
        artist=artist_name,
        label=label_name,
        bpm=float(tj.get("bpm") or 0) or 122.0,
        key=camelot,
        duration_seconds=duration_seconds,
        release_date=release_date,
        genre_tags=[genre_name] if genre_name else [],
        preview_url=url,
        source="beatport",
    )


def fetch_label_page(slug: str, label_id: int, page: int = 1) -> list[dict]:
    """Fetch one Beatport label page. Same structure as genre pages."""
    url = f"https://www.beatport.com/label/{slug}/{label_id}/tracks"
    if page > 1:
        url += f"?page={page}"
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    except Exception as e:
        print(f"    fetch failed for {slug} p{page}: {e}")
        return []
    if resp.status_code != 200:
        print(f"    HTTP {resp.status_code} for {slug} p{page}")
        return []
    m = NEXT_DATA_RE.search(resp.text)
    if not m:
        return []
    try:
        return _find_all_tracks(json.loads(m.group(1)))
    except json.JSONDecodeError:
        return []


def load_label_ids() -> dict:
    if LABEL_IDS_PATH.exists():
        return json.loads(LABEL_IDS_PATH.read_text()).get("labels", {})
    return {}


def run_discovery(pages: int = 1, days_back: int | None = None,
                  source: str = "labels") -> list[Track]:
    """Fetch across all configured genres. Free — no API calls, no key."""
    all_tracks: list[Track] = []
    seen_ids: set[str] = set()
    cutoff = (date.today() - timedelta(days=days_back)) if days_back else None

    if source in ("labels", "both"):
        labels = load_label_ids()
        print(f"Fetching {len(labels)} target label pages "
              f"({pages} page{'s' if pages > 1 else ''} each)... free, no API key.\n")
        for name, meta in labels.items():
            for page in range(1, pages + 1):
                raw = fetch_label_page(meta["slug"], meta["id"], page)
                added = 0
                for tj in raw:
                    t = _to_track(tj)
                    if not t or t.id in seen_ids:
                        continue
                    if cutoff:
                        try:
                            if datetime.fromisoformat(str(t.release_date)).date() < cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass
                    seen_ids.add(t.id)
                    all_tracks.append(t)
                    added += 1
                print(f"  {name[:28]:28s} p{page}: +{added}")
                time.sleep(1.0)

    if source not in ("genres", "both"):
        print(f"\nFound {len(all_tracks)} unique candidates.")
        RAW_CANDIDATES_PATH.write_text(json.dumps([asdict(t) for t in all_tracks], indent=2))
        return all_tracks

    print(f"\nFetching {len(GENRES)} genre pages...")
    for slug, gid in GENRES:
        for page in range(1, pages + 1):
            raw = fetch_genre_page(slug, gid, page)
            added = 0
            for tj in raw:
                t = _to_track(tj)
                if not t or t.id in seen_ids:
                    continue
                if cutoff:
                    try:
                        rd = datetime.fromisoformat(str(t.release_date)).date()
                        if rd < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass
                seen_ids.add(t.id)
                all_tracks.append(t)
                added += 1
            print(f"  {slug} p{page}: +{added}")
            time.sleep(1.0)  # polite — we're a guest on their servers

    print(f"\nFound {len(all_tracks)} unique candidates.")
    RAW_CANDIDATES_PATH.write_text(json.dumps([asdict(t) for t in all_tracks], indent=2))
    return all_tracks


def score_and_rank(tracks: list[Track], top_n: int = 30) -> list[dict]:
    scorer = Scorer.load_default()
    scored = []
    for t in tracks:
        b = scorer.score(t)
        if b.rejected:
            continue
        scored.append({
            "track": asdict(t),
            "score": round(b.total, 1),
            "explain": b.explain(),
            "features": b.features,
            "confidence": "high",
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_n]
    RANKED_OUTPUT_PATH.write_text(json.dumps(top, indent=2))
    print(f"Scoreable: {len(scored)}. Saved top {len(top)} to {RANKED_OUTPUT_PATH.name}")
    return top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--source", default="labels", choices=["labels","genres","both"])
    args = ap.parse_args()

    tracks = run_discovery(pages=args.pages, days_back=args.days, source=args.source)
    if not tracks:
        print("No candidates found.")
        return
    top = score_and_rank(tracks, top_n=args.top)
    print(f"\n{'SCORE':>6}  {'ARTIST — TITLE':50s} {'LABEL':20s} {'BPM':>4} {'KEY':4s}")
    print("-" * 92)
    for e in top:
        t = e["track"]
        at = f"{t['artist']} — {t['title']}"
        print(f"{e['score']:6.1f}  {at[:50]:50s} {t['label'][:20]:20s} "
              f"{t['bpm']:4.0f} {t['key']:4s}")


if __name__ == "__main__":
    main()
