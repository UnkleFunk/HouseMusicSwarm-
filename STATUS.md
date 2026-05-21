# Current Status — READ THIS FIRST (Local Claude Code Session)

## The Mission
Get unklefunk.music showing the real Unkle Funk artist hub (dark gold theme,
equalizer animation, SoundCloud/Spotify players, Sunday Slackin' podcast).

## ✅ SITE IS LIVE — https://unklefunk.music
Fixed May 21, 2026. Site returns 200 and serves our full HTML.

### Root Cause (resolved)
The deploy workflow was uploading files to `~/public_html/` but Hostinger
serves `unklefunk.music` from `~/domains/unklefunk.music/public_html/`.
The Hostinger placeholder (`default.php`) was sitting in the domain web root
and blocking everything. Fixed by:
1. Copying files from `~/public_html/` to `~/domains/unklefunk.music/public_html/`
2. Removing `default.php`
3. Updating deploy-hostinger.yml to target the correct path going forward

## What's Built & Working
- `website/index.html` — full single-page artist hub, all content real ✅
- `website/style.css` — dark/gold theme, vinyl animation, responsive ✅
- `website/main.js` — canvas equalizer, mobile nav, scroll reveal ✅
- `website/.htaccess` — DirectoryIndex + gzip + caching headers ✅
- GitHub Actions deploy: `.github/workflows/deploy-hostinger.yml`
  - Triggers on push to `main` with `paths: ["website/**"]`
  - SCP uploads files to `~/domains/unklefunk.music/public_html/` ✅ (corrected)

## Server Info
- Host: 195.179.239.223
- SSH Port: 65002
- Username: in GitHub Secret `HOSTINGER_SSH_USER`
- **Actual web root: `~/domains/unklefunk.music/public_html/`** ← KEY FACT
- Legacy path `~/public_html/` exists but is NOT served by the domain

## What the Site Shows
- Black background (#09090b), gold (#c9a84c) accents
- Hero: large "UNKLE FUNK" text with animated equalizer bars behind it
- About: spinning vinyl record, bio, stats (16+ years, 2010 podcast, etc.)
- Podcast: Sunday Slackin' embedded Apple Podcasts player (id=406329520)
- Music: SoundCloud embed (unklefunkssounds) + Spotify embed (artist 3OIZINZmZ2lKSYVsmSmrnH)
- Releases: 5 release cards + chart links to Traxsource and Beatport
- Connect: 6 platform cards (SoundCloud, Spotify, Beatport, Apple Podcasts, Facebook, Discogs)

## Next Steps (Phase 2 — from VISION.md)
- [ ] Create `music_profile_agent/` with `music_profile.md`
- [ ] Add `SearchTraxsource` + `SearchBeatport` tools
- [ ] Create `music_curation_agent/`
- [ ] Add `PublishChart` tool to VirtualAssistant
- [ ] Wire all into `swarm.py` + `orchestrator/instructions.md`
- [ ] Test with one month of new Traxsource releases

## Repo Structure (relevant)
```
HouseMusicSwarm-/
├── website/              ← the static site
│   ├── index.html
│   ├── style.css
│   ├── main.js
│   └── .htaccess
├── .github/workflows/
│   ├── deploy-hostinger.yml   ← deploys to ~/domains/unklefunk.music/public_html/
│   └── diagnose.yml           ← checks server state
├── swarm.py              ← the Agency Swarm (separate from website)
├── orchestrator/
├── virtual_assistant/
├── deep_research/
└── ...other swarm agents
```

## Branch
All work is on `main`.

## Context
The user (Unkle Funk / Glenn) is a Chicago house music DJ/producer.
The swarm is a full OpenSwarm fork (Agency Swarm framework) that is
SEPARATE from the website — the website just lives in the `website/` folder.
See VISION.md for the full music curation swarm roadmap.
