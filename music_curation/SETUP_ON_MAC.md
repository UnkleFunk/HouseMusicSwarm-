# Running the Curation Tools on your Mac

Everything here runs locally. Nothing is a website you visit — the
review UI is a small program you start, and it serves a page to your
own browser while it's running.

## One-time setup

Open Terminal, then:

```bash
# 1. Go into this folder (adjust the path to wherever you unzipped it)
cd ~/Downloads/music_curation      # or wherever it lives

# 2. Install the three Python packages it needs
pip3 install flask pyyaml requests
```

That's the whole setup. You only do it once.

## Each time you want fresh candidates

```bash
cd ~/Downloads/music_curation

# Pull the latest releases from your target labels + score them.
# --days 45 = only releases from the last 45 days
# --top 60  = keep the 60 highest-scoring
python3 discovery.py --pages 1 --days 45 --top 60
```

This writes `ranked_top_30.json` — the list the review UI reads.

## Start the review UI

```bash
python3 review_ui.py
```

It prints a line like:

```
Review UI starting at http://0.0.0.0:5678
```

- On the **same Mac**: open your browser to  http://localhost:5678
- On your **phone** (same wifi): the terminal shows your Mac's IP —
  open  http://THAT-IP:5678  on your phone.

Leave the Terminal window open. Closing it stops the server. To stop
it deliberately, click the Terminal window and press Control-C.

## What the review UI does that the static HTML doesn't

Every 👍 / 👎 / 🤔 you tap is saved to `feedback.sqlite`. Over time the
scorer learns which *artists* you actually rate — not just which labels
— so next month's candidate list is sharper than this month's. The
static `chart_candidates.html` is a one-shot list; the review UI is the
part that gets smarter.

## Refreshing label IDs (rarely)

If you add labels to `profile.yaml`, resolve their Beatport IDs once:

```bash
python3 resolve_labels.py --from-profile
```

This needs Playwright:  `pip3 install playwright && playwright install chromium`
(only needed for label-ID lookup, not for normal discovery or review.)

## Building a chart export by hand

```bash
python3 export_chart.py --min-score 60
```

Writes `chart_candidates.html` (tap-to-preview, tick-to-shortlist,
copy-picks button) and `chart_candidates.csv`.
