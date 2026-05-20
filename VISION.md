# House Music Swarm — Vision & Roadmap

## The Goal
An AI swarm that knows Unkle Funk's musical DNA well enough to:
1. Find new tracks on Traxsource / Beatport that fit within his taste "overton window"
2. Auto-generate a publishable Top 10 chart (monthly or twice monthly)
3. Keep unklefunk.music's chart section current with zero manual effort
4. Surface fresh picks for Sunday Slackin' every week

---

## The Taste Profile (known data points)

### Sub-genres
- Deep House, Tech House, Classic Chicago House, Detroit Deep Soul
- Warm, hypnotic, floor-functional — never commercial, always underground

### His Own Productions (musical fingerprint)
- "1998" — 123 BPM, C Minor, Deep House (Soulsupplement Records, 2016)
- "La Honda Dreams" — with Anaiek feat. One Little Fishie (Wulfpack, 2016)
- "Groove Italio" — DOIN' WORK Records
- "Experimental" — DOIN' WORK Records

### Dream Labels (catalog = taste data)
- Soulsupplement Records
- Wulfpack
- DOIN' WORK Records
- (expand list as user provides more)

### All-Time Essential Cuts (taste anchors)
- Mr. Fingers — Can You Feel It (Trax, 1986)
- Larry Heard — Mystery of Love (Alleviated, 1985)
- Frankie Knuckles — Your Love (Trax, 1987)
- Ron Trent — Altered States (Prescription, 1992)
- Cajmere feat. Dajae — Brighter Days (Cajual, 1992)
- Kerri Chandler — Bar A Thym (Kaoz Theory, 2001)
- Moodymann — Dem Young Sconies (Mahogani Music, 2007)
- Dennis Ferrer — Hey Hey (Objektivity, 2009)
- (expand to ~100 tracks as user provides)

### Artist Network (trust signals)
- Anaiek, Disco Aliens collective, Tyrohn Brooks (Obitykenobi), Chris Mindel, DJ PLEXXX

---

## The Swarm Architecture

### Agents

**ProfileAgent**
- Holds and refines the taste DNA document
- Accepts approve/reject feedback on recommendations
- Outputs taste vectors: BPM window, key preferences, energy level, label pedigree score

**DiscoveryAgent**
- Polls Traxsource new releases (by genre, by label, by BPM range)
- Polls Beatport new releases
- Optionally monitors SoundCloud for emerging artists
- Returns raw candidate track lists with metadata

**CurationAgent**
- Scores each candidate against the taste profile
- Filters by BPM window (~118–128), sub-genre tags, label reputation
- Ranks by multi-factor score
- Returns top 20 candidates for human review OR top 10 auto-approved

**ChartAgent**
- Formats the approved top 10 as a chart
- Updates website/index.html chart section
- Commits and pushes → auto-deploys to unklefunk.music
- Archives previous charts

### Communication Flow
```
User → ProfileAgent (taste updates, approvals)
ProfileAgent → CurationAgent (taste vectors)
DiscoveryAgent → CurationAgent (new release candidates)
CurationAgent → ChartAgent (ranked top 10)
ChartAgent → website (deployed chart)
```

---

## Data Sources & APIs Needed
- **Traxsource API** (or scraping) — new releases by genre/label
- **Beatport API** — new releases, chart data
- **SoundCloud API** — optional, for emerging artist discovery
- **Spotify API** — cross-reference artist data

---

## Website Integration
- Chart section in `website/index.html` updates automatically
- Each chart gets a date stamp: "May 2026 Selects", "June 2026 Selects"
- Archive page eventually: all past charts browsable at unklefunk.music/charts

---

## Skill: `/update-chart`
Future Claude Code skill that:
1. Asks DiscoveryAgent for this week's new releases
2. Runs CurationAgent to score against profile
3. Shows Unkle Funk the top 10 for approval
4. On approval, ChartAgent updates + deploys the website
5. Logs the chart to a monthly archive

---

## Phase 1 (Now)
- [x] Website built and deployed at unklefunk.music
- [x] Hand-curated Essential Cuts chart on site
- [x] Taste profile documented in this file

## Phase 2 (Next)
- [ ] Build ProfileAgent with taste DNA doc
- [ ] Build DiscoveryAgent with Traxsource/Beatport API tools
- [ ] Build CurationAgent with scoring logic
- [ ] Test with one month of new releases

## Phase 3 (Full Automation)
- [ ] ChartAgent writes + deploys charts to website
- [ ] Monthly chart automation via cron/scheduler
- [ ] Sunday Slackin' weekly picks pipeline
