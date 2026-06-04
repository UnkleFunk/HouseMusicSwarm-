# Unkle Funk Song Sketch

An Ableton Live Extension that loads AI-generated, personalized drum/groove templates directly into your arrangement. A new sketch is generated every night by the HouseMusicSwarm Dream Engine.

## What It Does

Right-click any MIDI or Audio track → find **"Load Sketch: [Name] (BPM, Key)"** in the context menu → click it → 6 MIDI tracks appear in your arrangement with a fully written, humanized groove ready to build on.

Each sketch contains:

| Track | Content |
|-------|---------|
| KICK  | 4/4 kick pattern with Chicago syncopation |
| SNARE | 2-and-4 placement with ghost notes |
| HATS  | Off-beat 8th/16th pattern with open hat breathe |
| PERCS | Rolling conga/rimshot texture |
| BASS  | C minor root-walking line |
| CHORDS | Sparse Cm stabs on beat 2 |

All notes are humanized — subtle timing drift (±8ms) and velocity variation (±6) give the grid an organic, analog feel.

## Requirements

- Ableton Live **Suite** 12.4.5 or later (beta)
- Node.js 22.11.0 or later
- The `vendor/` folder containing the Extensions SDK (get from Ableton's beta download)

## Installation

```bash
# 1. Get the SDK vendor file from Ableton's beta download page
# 2. Place ableton-extensions-sdk-1.0.0.tgz in the vendor/ folder
# 3. Install and build
npm install
npm run build
```

Then in Ableton:
1. Open Preferences → Extensions
2. Click "Add Extension" → navigate to this folder
3. Right-click any track → look for "Load Sketch:" items

## Available Sketches

| Date | Name | BPM | Key | Notes |
|------|------|-----|-----|-------|
| 2026-06-04 | Slow Burn on State Street | 123 | C Minor | First sketch — late-night Chicago deep house |

## Feedback

Tell the HouseMusicSwarm agent: "Rate sketch 'Slow Burn on State Street' 5/5, loved the rolling congas" and the dream engine will weight future sketches accordingly.

## How Sketches Are Added

Every night at 5am, `scripts/nightly_dream.py` runs and:
1. Generates a new sketch `.ts` file in `src/sketches/`
2. Adds the import to `src/index.ts`
3. Creates an idea file in `ableton_extensions/ideas/`
4. Emails Glenn with the sketch details
5. Commits and pushes to the repo
