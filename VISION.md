# House Music Swarm — Vision & Roadmap

## Current State (as of May 2026)

### ✅ Already Built
- **The swarm** — full OpenSwarm fork running on Agency Swarm framework
  - Orchestrator, Deep Research, Data Analyst, Docs, Slides, Image Gen, Video Gen, Virtual Assistant
  - All agents can communicate and hand off to each other
  - Composio integration: 10,000+ external tools (Spotify, Gmail, GitHub, etc.)
  - SEARCH_API_KEY for web search (SearchAPI.io) — can query Traxsource & Beatport
  - Virtual Assistant has `EditFile` + `WriteFile` tools

- **The website** — unklefunk.music (live at Hostinger)
  - `website/index.html` — full single-page artist hub
  - Chart section already on the page, currently showing hand-curated Essential Cuts

- **The deploy pipeline** — GitHub Actions auto-deploys on push to `main`
  - Any agent that writes `website/index.html` + triggers `git push` → site updates live

### 🔧 What Needs to Be Added
1. **`music_profile_agent/`** — holds and refines Unkle Funk's taste DNA
2. **`SearchTraxsource` + `SearchBeatport` tools** — discovery layer (uses SEARCH_API_KEY)
3. **`PublishChart` tool** — writes chart HTML to website + commits + pushes
4. **Wiring** — add music agents to `swarm.py` and `orchestrator/instructions.md`

---

## The Goal

An AI swarm that knows Unkle Funk's musical DNA well enough to:
1. Find new tracks on Traxsource / Beatport that fit within his taste "overton window"
2. Auto-generate a publishable Top 10 chart (monthly or twice monthly)
3. Update unklefunk.music's chart section automatically — no manual effort
4. Surface fresh picks for Sunday Slackin' every week

---

## Taste Profile — Musical DNA

### Sub-genres
- Deep House, Tech House, Classic Chicago House, Detroit Deep Soul
- Warm, hypnotic, floor-functional — never commercial, always underground
- BPM window: ~118–128
- Vibe: tracks that sound like Unkle Funk would have made or played them

### His Own Productions (musical fingerprint)
- "1998" — 123 BPM, C Minor, Deep House (Soulsupplement Records, 2016)
- "La Honda Dreams" — with Anaiek feat. One Little Fishie (Wulfpack, 2016)
- "Groove Italio" — DOIN' WORK Records
- "Experimental" — DOIN' WORK Records

### Dream Labels (full catalogs = taste data)
- Soulsupplement Records
- Wulfpack
- DOIN' WORK Records
- *(expand as user provides more)*

### All-Time Essential Cuts (taste anchors — expand to ~100)
- Mr. Fingers — Can You Feel It (Trax, 1986) — Classic Chicago
- Larry Heard — Mystery of Love (Alleviated, 1985) — Deep Blueprint
- Frankie Knuckles — Your Love (Trax, 1987) — Chicago Classic
- Ron Trent — Altered States (Prescription, 1992) — Deep Hypnotic
- Cajmere feat. Dajae — Brighter Days (Cajual, 1992) — Chicago House
- Kerri Chandler — Bar A Thym (Kaoz Theory, 2001) — Deep House
- Moodymann — Dem Young Sconies (Mahogani Music, 2007) — Detroit Deep
- Dennis Ferrer — Hey Hey (Objektivity, 2009) — Soulful House

### Artist Network (trust signals)
- Anaiek, Disco Aliens collective, Tyrohn Brooks (Obitykenobi), Chris Mindel, DJ PLEXXX

---

## New Agent Architecture

### `music_profile_agent/`
- Holds the taste DNA as a living document (`music_profile.md`)
- Accepts approve/reject feedback on recommendations
- Refines weights over time (which labels, BPMs, keys get boosted)
- Provides taste vectors to CurationAgent on request

### `music_discovery_agent/` (or tools added to Deep Research)
- `SearchTraxsource` tool — queries Traxsource new releases by genre/label/BPM via SEARCH_API_KEY
- `SearchBeatport` tool — same for Beatport
- Returns raw candidate tracks with metadata (title, artist, label, BPM, key, genre tags)

### `music_curation_agent/`
- Receives candidates from discovery
- Scores each against taste profile (BPM match, label pedigree, genre alignment, artist network)
- Returns ranked top 20 for human review or top 10 auto-approved
- Explains why each track made the cut

### `PublishChart` tool (added to Virtual Assistant or new WebsiteAgent)
- Takes approved top 10 list
- Renders chart HTML matching the existing `dj-chart` CSS class structure in `website/index.html`
- Writes to repo, commits, pushes → GitHub Actions auto-deploys to unklefunk.music
- Archives previous chart to a `website/charts/` history page

---

## Communication Flow
```
User
  └─► Orchestrator
        ├─► MusicProfileAgent  (taste DNA queries + feedback)
        ├─► MusicDiscoveryAgent (new release candidates)
        ├─► MusicCurationAgent  (scored top 10)
        └─► VirtualAssistant → PublishChart → git push → GitHub Actions → unklefunk.music
```

---

## The Publish Pipeline (already works)
```
swarm writes website/index.html
  └─► git commit + push to main
        └─► GitHub Actions (deploy-hostinger.yml)
              └─► SCP to Hostinger public_html
                    └─► unklefunk.music live ✓
```

---

## Keys Already in `.env.example`
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` — model provider
- `COMPOSIO_API_KEY` + `COMPOSIO_USER_ID` — Spotify, SoundCloud, GitHub integrations
- `SEARCH_API_KEY` — Traxsource + Beatport web search

## Keys Still Needed
- Beatport API key (if they open their API — otherwise SEARCH_API_KEY covers it)
- GitHub token in env (for the `PublishChart` git push)

---

## Phases

### Phase 1 — Done ✓
- [x] Website live at unklefunk.music
- [x] GitHub Actions deploy pipeline
- [x] Swarm built (OpenSwarm fork)
- [x] Hand-curated Essential Cuts chart on site
- [x] Taste profile documented here

### Phase 2 — Next Session
- [ ] Create `music_profile_agent/` — reads from `knowledge/music_context.md` as its taste source
- [ ] Add `SearchTraxsource` + `SearchBeatport` tools
- [ ] Create `music_curation_agent/`
- [ ] Add `PublishChart` tool to VirtualAssistant
- [ ] Create `ableton_dreamer_agent/` (see architecture below)
- [ ] Wire all into `swarm.py` + `orchestrator/instructions.md`
- [ ] Test with one month of new Traxsource releases

---

## Ableton Dreamer Agent Architecture

### Role
A full creative stack agent that knows Unkle Funk's sonic identity deeply enough to:
1. Generate track concepts / arrangement ideas (co-writer)
2. Build Max for Live devices, Ableton racks, and device chains (engineering)
3. Create presets, drum kits, and sample packs in his sonic palette (sound design)
4. Explore the Ableton Extensions framework (Python-based scripting) to invent new workflows — co-inventor, not just executor

### Context Foundation
All taste decisions are grounded in **`knowledge/music_context.md`**. The agent reads this file before any creative task. The Ableton-specific sections (Section 4: Production DNA, Section 5: Extensions) are its primary reference.

### Communication Flow
```
User
  └─► Orchestrator
        └─► AbletonDreamerAgent
              ├── Reads: knowledge/music_context.md (taste + production DNA)
              ├── Reads: knowledge/agent_lessons.md (framework patterns)
              ├── Output: Ableton project files, racks, M4L devices, presets
              └── Feeds back: "this worked / this missed" → updates music_context.md
```

### Agent Spec
- **Model:** Latest Claude (Opus preferred for creative depth)
- **Instructions file:** `ableton_dreamer_agent/instructions.md`
- **Key tools to build:**
  - `GenerateAbletonClip` — creates MIDI clips matching taste profile
  - `BuildDrumRack` — assembles drum racks from specified one-shots
  - `ExportAbletonPreset` — generates `.adv` / `.adg` preset files
  - `ScaffoldExtension` — scaffolds Ableton Extensions Python boilerplate
  - `LogTasteSignal` — writes approve/reject signals back to `music_context.md`

### The Creative Contract
The agent is a collaborator, not a butler. Every output should:
1. Explain *why* it fits the aesthetic (not just what it is)
2. Be willing to surprise — the unexpected-but-right is the goal
3. Flag when it's pushing the taste boundary (invite yes/no)
4. Learn from approvals and rejections via `LogTasteSignal`

---

### Phase 3 — Full Automation
- [ ] Monthly chart cron via GitHub Actions
- [ ] Sunday Slackin' weekly picks pipeline
- [ ] Chart archive at unklefunk.music/charts
- [ ] Approve/reject UI on website for direct feedback loop
