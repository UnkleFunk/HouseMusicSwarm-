# Current Status — READ THIS FIRST (Local Claude Code Session)

## The Mission
unklefunk.music now runs the **"75 Deep"** concept: Unkle Funk (Glenn Giles) is
a mailman finishing 25 years' worth of unfinished house tracks — 75 of
them — in public, with AI-assisted production tooling handling the busywork.
The site's job is to tell that story, showcase works-in-progress with a
built-in Q&A per track, and capture emails as tracks get finished.

## ✅ SITE IS LIVE — https://unklefunk.music
Deploy pipeline fixed May 21, 2026 (see Root Cause below); site has been
redesigned twice since — first to a dark/gold theme, then rebuilt as the
current "75 Deep" concept (see Design History below).

### Root Cause (resolved, historical)
The deploy workflow was uploading files to `~/public_html/` but Hostinger
serves `unklefunk.music` from `~/domains/unklefunk.music/public_html/`.
The Hostinger placeholder (`default.php`) was sitting in the domain web root
and blocking everything. Fixed by:
1. Copying files from `~/public_html/` to `~/domains/unklefunk.music/public_html/`
2. Removing `default.php`
3. Updating `deploy-hostinger.yml` to target the correct path going forward

### Design History
1. **v1** — dark/gold theme (`#c9a84c` accent), vinyl animation, embedded
   SoundCloud/Spotify players, curated chart section. (superseded)
2. **Neon Nights** — AMOLED black (`#09090b`) + sky-blue accent (`#3BA7E0`,
   pulled from a Movement Detroit photo). Approved palette, still the base
   theme today (CSS var is still literally named `--amber` for historical
   reasons even though the color is blue — see `website/style.css` comment).
3. **75 Deep rebuild** (current) — full content/structure rewrite around the
   "mailman finishing 75 tracks" narrative, plus real archive photography
   replacing all stock imagery.

## What's Built & Working
- `website/index.html` — single-page site: Hero (75-tally badge) → Mission →
  Music (WIP track cards) → About → Sunday Slackin' banner → Connect →
  The Start (2001 origin photos) ✅
- `website/style.css` — AMOLED black / sky-blue "Neon Nights" theme ✅
- `website/main.js` — tally badge, click-to-load embed facades, scroll
  reveal (the equalizer canvas animation from v1 is gone) ✅
- `website/wip.js` — per-track WaveSurfer.js waveform player + Supabase-
  backed Q&A widget (see Known Gaps — Supabase isn't wired up yet) ⏳
- `website/design-variants.html` — internal design comps, not linked from
  the live nav
- `website/.htaccess` — DirectoryIndex + gzip + caching headers ✅
- `supabase/wip_feedback_schema.sql` — schema backing the WIP Q&A widget
- GitHub Actions deploy: `.github/workflows/deploy-hostinger.yml`
  - Triggers on push to `main` with `paths: ["website/**"]`
  - Explicitly SCPs `index.html`, `design-variants.html`, `style.css`,
    `main.js`, `wip.js`, `.htaccess`, `favicon.svg`, `robots.txt`, `fonts/`,
    `assets/` to `~/domains/unklefunk.music/public_html/` ✅

## Known Gaps / Not Yet Live
- **Supabase not configured** — `website/wip.js` has empty
  `SUPABASE_URL` / `SUPABASE_ANON_KEY` constants, so the per-track Q&A
  widget is scaffolded but silently does nothing until those are filled in
  and `supabase/wip_feedback_schema.sql` is applied to a real project.
- **No WIP audio files** — the 4 track cards reference
  `assets/audio/track-a.mp3` … `track-d.mp3`, but `website/assets/audio/`
  doesn't exist yet. The waveform players have nothing to load until real
  clips are dropped in.
- **Placeholder links** (marked `data-todo` in `index.html`): mission
  trailer YouTube URL, YouTube channel, TikTok, Instagram.
- **Mailing list form** posts to a placeholder Buttondown endpoint
  (`.../embed-subscribe/YOUR_LIST`) — needs a real list ID.
- **No EPK file** — the "Download EPK" button links to `epk.pdf`, which
  doesn't exist in `website/` yet.
- `website/reference-finder/` (a static build of the Reference Finder UI)
  ships to the server via the deploy workflow's `assets` glob but is not
  linked from the live site nav — reachable only by direct URL.

## Server Info
- Host: 195.179.239.223
- SSH Port: 65002
- Username: GitHub Secret `HOSTINGER_SSH_USER`
- Password: GitHub Secret `HOSTINGER_SSH_PASS`
- **Actual web root: `~/domains/unklefunk.music/public_html/`** ← KEY FACT
- Legacy path `~/public_html/` exists but is NOT served by the domain

## Next Steps
- [ ] Wire up Supabase project + fill in `SUPABASE_URL`/`SUPABASE_ANON_KEY`
      in `website/wip.js`, apply `supabase/wip_feedback_schema.sql`
- [ ] Record/export real WIP clips into `website/assets/audio/`
- [ ] Fill in the `data-todo` placeholder links (YouTube, TikTok, Instagram,
      mission trailer)
- [ ] Point the mailing-list form at a real Buttondown (or equivalent) list
- [ ] Add a real `epk.pdf`
- [ ] Phase 2 (from `VISION.md` / `music_curation/README.md`): wire
      `music_curation/` (taste-scoring engine, already built) into a
      discovery pipeline once an access route (SearchAPI.io vs. Beatport
      partner API vs. RSS) is chosen — see those files for full detail

## Repo Structure (relevant)
```
HouseMusicSwarm-/
├── website/                    ← the static site
│   ├── index.html
│   ├── style.css
│   ├── main.js                 ← tally badge, embed facades, scroll reveal
│   ├── wip.js                  ← WIP waveform player + Supabase Q&A (not yet wired)
│   ├── design-variants.html    ← internal comps, unlinked
│   ├── reference-finder/       ← standalone Reference Finder UI, unlinked from nav
│   ├── assets/                 ← real archive photography
│   ├── fonts/
│   └── .htaccess
├── supabase/
│   └── wip_feedback_schema.sql ← backs the WIP Q&A widget
├── .github/workflows/
│   ├── deploy-hostinger.yml    ← deploys to ~/domains/unklefunk.music/public_html/
│   └── diagnose.yml            ← manual SSH check of the Hostinger web root
├── swarm.py                    ← the Agency Swarm (separate from the website)
├── orchestrator/, virtual_assistant/, deep_research/, ...  ← the 10 swarm agents
└── CLAUDE.md                   ← authoritative codebase guide, keep in sync
```

## Branch
All work merges to `main`.

## Context
The user (Unkle Funk / Glenn Giles) is a Chicago house music DJ/producer,
currently a mailman finishing 75 unreleased tracks in public. The swarm is a
full OpenSwarm fork (Agency Swarm framework) that is SEPARATE from the
website — the website just lives in the `website/` folder. See `VISION.md`
for the music curation swarm roadmap and `CLAUDE.md` for the full codebase
guide.
