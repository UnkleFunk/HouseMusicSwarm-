"""
Unkle Funk — Chart Publisher
==============================

Takes the final 10 tracks (marked 'yes' in feedback.sqlite) and writes
Beatport + Traxsource embed shortcodes into the site's charts section.

No chart infrastructure of our own — this just assembles the official
embed widgets from each platform and drops them into index.html between
marker comments. Commits are staged but NOT auto-pushed; run
`git push` yourself after eyeballing the diff, or hand this off to
Claude Code to push once reviewed.

Beatport embed format (official):
  <iframe src="https://embed.beatport.com/track?id={TRACK_ID}&color=teal"
          width="100%" height="120" frameborder="0"></iframe>

Traxsource doesn't have a first-party public embed widget as of this
writing — we link out with a styled card instead, matching the site's
visual system. If Traxsource ships an embed widget later, swap
_traxsource_embed() only.

Run:
    python3 publish.py --top-n 10
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

FEEDBACK_DB = Path(__file__).parent / "feedback.sqlite"
SITE_HTML = Path(__file__).parent.parent / "website" / "index.html"

CHARTS_START = "<!-- CHARTS:START -->"
CHARTS_END = "<!-- CHARTS:END -->"


def get_final_tracks(top_n: int = 10) -> list[dict]:
    if not FEEDBACK_DB.exists():
        raise SystemExit(f"No feedback database at {FEEDBACK_DB}. Run review_ui.py first.")
    with sqlite3.connect(FEEDBACK_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM feedback WHERE decision='yes' ORDER BY ts DESC LIMIT ?",
            (top_n,)
        ).fetchall()
    if not rows:
        raise SystemExit("No tracks marked 'yes' yet. Review candidates in review_ui.py first.")
    return [dict(r) for r in rows]


def _beatport_embed(track_id: str) -> str:
    return (
        f'<iframe class="chart-embed-frame" '
        f'src="https://embed.beatport.com/track?id={track_id}&color=1F7A72" '
        f'width="100%" height="120" frameborder="0" loading="lazy" '
        f'title="Beatport track embed"></iframe>'
    )


def _traxsource_card(title: str, artist: str, url: str) -> str:
    return f'''<a class="chart-track-card" href="{url}" target="_blank" rel="noopener">
      <span class="chart-track-title">{title}</span>
      <span class="chart-track-artist">{artist}</span>
      <span class="chart-track-link">Listen on Traxsource →</span>
    </a>'''


def build_charts_section(tracks: list[dict]) -> str:
    items = []
    for i, t in enumerate(tracks, 1):
        source = t.get("source", "beatport")
        title = t["title"]
        artist = t["artist"]
        # track_id parsing depends on how discovery.py tagged the id (bp_/tx_ prefix)
        raw_id = t["track_id"]
        if raw_id.startswith("bp_"):
            embed = _beatport_embed(raw_id[3:])
        elif raw_id.startswith("tx_"):
            # No official Traxsource embed yet — use styled card with the
            # original preview URL if we still have it; else generic search link
            embed = _traxsource_card(title, artist, f"https://www.traxsource.com/search?term={artist}+{title}")
        else:
            embed = _traxsource_card(title, artist, "#")

        items.append(f'''      <li class="chart-item reveal">
        <span class="chart-rank">{i:02d}</span>
        <div class="chart-embed-wrap">{embed}</div>
      </li>''')

    return (
        f"{CHARTS_START}\n"
        f'    <section class="section" id="charts">\n'
        f'      <div class="wrap">\n'
        f'        <p class="label reveal">02 — The Chart</p>\n'
        f'        <h2 class="reveal">What I\'m playing.</h2>\n'
        f'        <p class="bio-p reveal" style="margin-bottom:2rem">Ten tracks, hand-picked and scored against '
        f'25 years of taste. Updated regularly — this is the actual chart, not a curated best-of.</p>\n'
        f'        <ol class="chart-list">\n'
        + "\n".join(items) +
        f'\n        </ol>\n'
        f'      </div>\n'
        f'    </section>\n'
        f"{CHARTS_END}"
    )


def inject_into_site(charts_html: str) -> bool:
    if not SITE_HTML.exists():
        raise SystemExit(f"Site file not found at {SITE_HTML}")
    content = SITE_HTML.read_text()

    if CHARTS_START in content and CHARTS_END in content:
        # Replace existing block
        pattern = re.compile(
            re.escape(CHARTS_START) + r".*?" + re.escape(CHARTS_END),
            re.DOTALL
        )
        new_content = pattern.sub(charts_html, content)
        action = "updated"
    else:
        # First run — insert after the Mission section closes, before About.
        # Anchor: insert right before the About section comment.
        anchor = '<!-- ============ 4. ABOUT ============ -->'
        if anchor not in content:
            raise SystemExit(
                "Could not find insertion anchor in index.html. "
                "Insert the CHARTS:START/END block manually this once."
            )
        new_content = content.replace(anchor, charts_html + "\n\n    " + anchor)
        action = "inserted"

    SITE_HTML.write_text(new_content)
    print(f"Charts section {action} in {SITE_HTML}")
    return True


CHARTS_CSS = """
/* ---------- Charts ---------- */
.chart-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.75rem; }
.chart-item { display: flex; align-items: center; gap: 1rem; }
.chart-rank {
  font-family: var(--display); font-size: 1.4rem; color: var(--amber);
  flex: none; width: 2.5rem; text-align: right; opacity: 0.85;
}
.chart-embed-wrap { flex: 1; min-width: 0; }
.chart-embed-frame { border-radius: 4px; }
.chart-track-card {
  display: block; background: var(--surface); border: 1px solid var(--line);
  border-radius: 6px; padding: 0.85rem 1rem; text-decoration: none; color: var(--ink);
  transition: border-color 0.2s ease;
}
.chart-track-card:hover { border-color: var(--amber); }
.chart-track-title { display: block; font-weight: 600; }
.chart-track-artist { display: block; color: var(--ink-muted); font-size: 0.9rem; }
.chart-track-link { display: block; margin-top: 0.35rem; font-size: 0.8rem; color: var(--amber); }
"""


def ensure_charts_css() -> None:
    css_path = SITE_HTML.parent / "style.css"
    css = css_path.read_text()
    if ".chart-list" in css:
        return  # already present
    css_path.write_text(css.rstrip() + "\n\n" + CHARTS_CSS)
    print(f"Charts CSS appended to {css_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    tracks = get_final_tracks(args.top_n)
    print(f"Publishing {len(tracks)} tracks:")
    for t in tracks:
        print(f"  {t['artist']} — {t['title']} [{t['label']}]")

    charts_html = build_charts_section(tracks)
    inject_into_site(charts_html)
    ensure_charts_css()

    print("\nDone. Review the diff with `git diff website/`, then commit + push")
    print("(or hand off to Claude Code to review and push).")


if __name__ == "__main__":
    main()
