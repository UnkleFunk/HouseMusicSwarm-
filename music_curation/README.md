# Music Curation — the taste engine

Compresses a 50:1 track-listen ratio into ~5:1 by pre-filtering candidates against Unkle Funk's taste profile. Explainable scoring, learning loop, humans still pick the top 10.

## What's in this directory

| File | Purpose | Status |
|---|---|---|
| `profile.yaml` | Hand-tuned taste profile — weights, label tiers, artist seeds. **Edit this to teach the engine.** | ✅ built (v1) |
| `profile.learned.yaml` | Auto-generated overrides from feedback loop. Delete this to reset learning. | ⏳ auto-created on first feedback |
| `scoring.py` | Core scorer. Takes a `Track`, returns explainable breakdown. | ✅ built + tested |
| `feedback.sqlite` | Every yes/no/maybe decision Glenn makes. Feeds retraining. | ⏳ auto-created |
| `discovery.py` | Polls Beatport + Traxsource for new candidates. | ⏸️ blocked — needs API access decision |
| `review_ui.py` | Local Flask app: 30s previews + thumb-up/down. | ⏸️ scheduled after discovery |
| `publish.py` | Writes final chart embed markup to the site, commits, pushes. | ⏸️ scheduled after review UI |
| `run_weekly.sh` | Cron-driven pipeline: discover → score → notify. | ⏸️ scheduled last |

## The pipeline (end state)

```
                                     ┌───────────────────────────┐
      Sunday 07:00 launchd trigger →│ discovery.py              │
                                     │  Beatport + Traxsource    │
                                     │  → raw_candidates.json    │
                                     └──────────────┬────────────┘
                                                    ▼
                                     ┌───────────────────────────┐
                                     │ scoring.py                │
                                     │  profile.yaml + learned    │
                                     │  → ranked_top_30.json     │
                                     └──────────────┬────────────┘
                                                    ▼
                                     ┌───────────────────────────┐
      Glenn's phone push notif  ←───│  review_ui.py (localhost)  │
      "30 candidates ready"          │  30s previews · 👍/👎/tag │
                                     │  → feedback.sqlite         │
                                     └──────────────┬────────────┘
                                                    ▼
                                     ┌───────────────────────────┐
                                     │ publish.py                │
                                     │  Beatport embed + Traxsource │
                                     │  embed → website/index.html│
                                     │  → git push → live         │
                                     └───────────────────────────┘
```

## Explainability — what a score actually looks like

```
=== "Late Night Mailman" by Dantiez Saunderson on Toolroom Records ===
Total: 96.8 / 100
         bpm: 100.0 × 20.0%  → 20.0   (122.0 in bullseye 120-123)
         key: 100.0 ×  5.0%  → 5.0   (8A minor)
       label: 100.0 × 25.0%  → 25.0   ('Toolroom Records' Tier 1)
      artist: 88.0 × 20.0%  → 17.6   ('Dantiez Saunderson' → 88 from history)
    duration: 100.0 ×  5.0%  → 5.0   (7:10 DJ tool)
       sonic: 96.1 × 15.0%  → 14.4   (tags: warm, analog, chicago house)
       vocal: 95.0 ×  5.0%  → 4.8   ('soulful lead' rewarded)
     recency: 100.0 ×  5.0%  → 5.0   (32d old)
```

No black boxes. If a track scored wrong, you can see exactly which feature is off and either tune the profile OR give feedback that will auto-adjust weights.

## The learning loop

Every review decision (yes/no/maybe + reason tags like "too tech" / "wrong vibe") lands in `feedback.sqlite`. Every 25 decisions, weights auto-retrain:

- Artist scores shift up on yes, down on no (bounded ±15% per event)
- Label tier confidence adjusts — a Tier 2 label with 8 yes-votes gets promoted to Tier 1
- Sonic descriptor weights adjust based on which tags predict yes vs no

Learned weights land in `profile.learned.yaml` — `profile.yaml` stays your clean hand-tuned baseline. Delete `profile.learned.yaml` to reset.

## What's needed to unblock the rest

1. **Discovery module (`discovery.py`)** — need to decide access route:
   - **Option A:** SearchAPI.io key (per `VISION.md`) — flexible, works today, minor scraping of result pages
   - **Option B:** Beatport partner API — cleaner data, gated access (usually for retailers only)
   - **Option C:** Traxsource + Beatport RSS/label pages — free, brittle, needs polite rate limiting
   - **Recommendation:** start with A. It works now.

2. **Seed feedback data** — 30-50 tracks Glenn would play right now, with artist + title + label. This bootstraps the artist scores and validates the profile weights before the first run. Without it, the engine starts cold and Glenn's first 100 candidates are noisier than they need to be.

3. **Review UI hosting** — Flask app runs on his Hackintosh at `localhost:5678`. Auth via a shared token; his phone bookmark lets him review candidates on break.

## Site-side integration

The chart section on `unklefunk.music` uses Beatport's and Traxsource's official embed widgets. `publish.py` writes shortcodes like:

```html
<div class="chart-embed" data-source="beatport" data-chart-id="{ID}">…</div>
<div class="chart-embed" data-source="traxsource" data-chart-id="{ID}">…</div>
```

No chart infrastructure built or maintained by us. Their platforms handle rendering, updates, and legal.
