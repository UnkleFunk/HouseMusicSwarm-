"""
Unkle Funk — Label & Artist ID Resolver
========================================

Beatport routes label/artist pages by numeric ID; the slug in the URL
is decorative and ignored. Their search results load client-side, so a
plain HTTP fetch returns an empty shell. This module renders the search
page with Playwright (local, free) and extracts real IDs.

Run once per new label/artist. IDs are stable — cache them in
label_ids.json and never look them up again.

Usage:
    python3 resolve_labels.py "Toolroom" "Defected" "Glasgow Underground"
    python3 resolve_labels.py --from-profile     # resolve all Tier 1/2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

CACHE_PATH = Path(__file__).parent / "label_ids.json"
PROFILE_PATH = Path(__file__).parent / "profile.yaml"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {"labels": {}, "artists": {}}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def resolve(names: list[str], kind: str = "labels") -> dict[str, dict]:
    """Resolve names -> {slug, id} via Beatport's JS-rendered search."""
    from playwright.sync_api import sync_playwright

    cache = _load_cache()
    out = {}
    pending = [n for n in names if n not in cache.get(kind, {})]

    if not pending:
        print("All names already cached.")
        return {n: cache[kind][n] for n in names if n in cache[kind]}

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        for name in pending:
            ctx = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                                      locale="en-US")
            ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )
            page = ctx.new_page()
            q = name.replace(" ", "+")
            url = f"https://www.beatport.com/search/{kind}?q={q}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(5000)
                html = page.content()
            except Exception as e:
                print(f"  {name}: fetch error — {str(e)[:50]}")
                continue

            singular = kind.rstrip("s")
            hits = re.findall(rf'/{singular}/([a-z0-9\-]+)/(\d+)', html)
            # Prefer the hit whose slug best matches the query
            norm = re.sub(r'[^a-z0-9]', '', name.lower())
            best = None
            for slug, _id in hits:
                sn = re.sub(r'[^a-z0-9]', '', slug)
                if sn == norm:
                    best = (slug, _id)
                    break
                if best is None and norm in sn:
                    best = (slug, _id)
            if best is None and hits:
                best = hits[0]

            ctx.close()
            if best:
                slug, _id = best
                cache.setdefault(kind, {})[name] = {"slug": slug, "id": int(_id)}
                out[name] = cache[kind][name]
                print(f"  {name:32s} -> {slug} (id={_id})")
            else:
                print(f"  {name:32s} -> NOT FOUND")

        browser.close()

    _save_cache(cache)
    for n in names:
        if n in cache.get(kind, {}):
            out[n] = cache[kind][n]
    return out


def from_profile() -> list[str]:
    prof = yaml.safe_load(PROFILE_PATH.read_text())
    t = prof["labels"]["tiers"]
    return list(t["tier_1"]["names"]) + list(t["tier_2"]["names"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--from-profile", action="store_true")
    ap.add_argument("--kind", default="labels", choices=["labels", "artists"])
    args = ap.parse_args()

    names = from_profile() if args.from_profile else args.names
    if not names:
        print("Nothing to resolve. Pass names or --from-profile.")
        sys.exit(1)

    print(f"Resolving {len(names)} {args.kind}...")
    res = resolve(names, args.kind)
    print(f"\nResolved {len(res)}/{len(names)}. Cached in {CACHE_PATH.name}")


if __name__ == "__main__":
    main()
