#!/usr/bin/env python3
"""One-time script to build (or refresh) the local reference track database.

Usage:
    python scripts/build_ref_db.py
    python scripts/build_ref_db.py --refresh
    python scripts/build_ref_db.py --genres house,tech-house --sources beatport
    python scripts/build_ref_db.py --max 50   (faster test run)
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from reference_finder_agent.tools.BuildDatabase import BuildDatabase


def main():
    parser = argparse.ArgumentParser(description="Build the house music reference track database.")
    parser.add_argument(
        "--sources", default="beatport,traxsource",
        help="Comma-separated: beatport,traxsource (default: both)"
    )
    parser.add_argument(
        "--genres", default="house,deep-house,tech-house",
        help="Comma-separated genre slugs (default: house,deep-house,tech-house)"
    )
    parser.add_argument(
        "--max", type=int, default=100,
        dest="max_tracks",
        help="Max tracks per genre per source (default: 100)"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Re-scrape and upsert even if already indexed"
    )
    args = parser.parse_args()

    print(f"Building reference database...")
    print(f"  Sources : {args.sources}")
    print(f"  Genres  : {args.genres}")
    print(f"  Max/genre: {args.max_tracks}")
    print(f"  Refresh  : {args.refresh}")
    print()
    print("This scrapes Beatport and Traxsource, downloads preview audio,")
    print("and extracts audio features. Expect 30–90 minutes for a full run.")
    print()

    tool = BuildDatabase(
        sources=args.sources,
        genres=args.genres,
        max_tracks_per_genre=args.max_tracks,
        refresh=args.refresh,
    )

    result = json.loads(tool.run())

    print(f"Done.")
    print(f"  Added   : {result.get('added', 0)} tracks")
    print(f"  Skipped : {result.get('skipped', 0)} (already indexed)")
    print(f"  Total DB: {result.get('total_in_db', 0)} tracks")

    errors = result.get("errors", [])
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:10]:
            print(f"  - {e}")

    print(f"\nDatabase stored at: ~/.housemusic_refs/chromadb/")
    print("Start the Reference Finder: python reference_finder_server.py")


if __name__ == "__main__":
    main()
