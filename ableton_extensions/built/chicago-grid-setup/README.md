# Chicago Grid Setup

An Ableton Live Extension that creates Glenn's default production scaffold in one right-click.

## What It Does

Right-click any track → "Chicago Grid Setup (123 BPM)" → 6 MIDI tracks appear, tempo set to 123 BPM, each track colored and named, with empty 8-bar clips ready to program.

| Track | Color | Purpose |
|-------|-------|---------|
| KICK  | Red   | Kick drum trigger |
| SNARE | Orange | Snare / clap |
| HATS  | Gold  | Hi-hat patterns |
| PERCS | Green | Congas, shakers, rimshots |
| BASS  | Blue  | Bass line |
| CHORDS | Purple | Chord stabs |

## Workflow

1. Open a blank Ableton Set
2. Right-click any track header → "Chicago Grid Setup (123 BPM)"
3. Load your samples: drag a kick sample onto the KICK track's Simpler, etc.
4. Program your patterns in the empty clips

## Requirements

- Ableton Live **Suite** 12.4.5+ (beta)
- Node.js 22.11.0+
- SDK vendor file (see main README)

## Installation

```bash
# Place vendor SDK file, then:
npm install
npm run build
```

Add to Ableton via Preferences → Extensions.
