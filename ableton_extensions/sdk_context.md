# Ableton Extensions SDK Reference

Version: 1.0.0 (Beta, Live 12.4.5+)
Package: `@ableton-extensions/sdk`
Runtime: Node.js >=22.11.0

## Entry Point Pattern

Every extension exports a single `activate` function:

```typescript
import { initialize, type ActivationContext } from "@ableton-extensions/sdk";

export async function activate(activation: ActivationContext) {
  const api = initialize(activation, "1.0.0");
  // register commands and context menu actions here
}
```

## Core API Object (`api`)

`initialize(activation, "1.0.0")` returns the API context with these top-level properties:

- `api.application.song` — the Song object (see below)
- `api.commands` — command registration
- `api.ui` — context menu / dialog integration
- `api.withinTransaction(fn)` — wrap mutations for undo support
- `api.getObjectFromHandle(handle, Type)` — resolve handles to typed objects

## Song Object

```typescript
const song = api.application.song;

// Properties
song.tempo: number           // BPM, readable and writable
song.tracks: Track[]         // all tracks in the Set (iterable)
song.cuePoints: CuePoint[]   // arrangement cue points

// Methods
await song.createMidiTrack()         // → MidiTrack
await song.createAudioTrack()        // → AudioTrack
await song.createCuePoint(beat)      // → CuePoint
await song.deleteCuePoint(cuePoint)  // removes a cue point
```

## Track Object

```typescript
// Properties
track.name: string           // track name (writable)
track.color: number          // integer color value (writable, e.g. 0xC8003C)
track.arrangementClips: Clip[]  // clips in arrangement view

// Methods
await track.createMidiClip(startBeat, durationBeats)   // → MidiClip
await track.createAudioClip({ filePath, startTime, duration, isWarped, loopSettings }) // → AudioClip
await track.clearClipsInRange(startBeat, endBeat)       // removes clips in range
```

## Clip Object

```typescript
// MidiClip properties
clip.name: string
clip.color: number
clip.duration: number     // in beats
clip.startTime: number    // in beats from song start (arrangement clips)
clip.notes: NoteDescription[]  // MIDI notes (readable and writable)

// Read notes
const notes = [...clip.notes];

// Write notes (replaces entire note array)
clip.notes = [
  { pitch: 36, startTime: 0, duration: 0.25, velocity: 100 },
  { pitch: 36, startTime: 4, duration: 0.25, velocity: 100 },
];
```

## NoteDescription

```typescript
interface NoteDescription {
  pitch: number;      // 0–127 (MIDI pitch)
  startTime: number;  // beats from clip start (not bars — divide by 4 for bars)
  duration: number;   // in beats
  velocity: number;   // 1–127
  muted?: boolean;
}
```

## Transactions

All mutations that should be undoable as a unit must be wrapped:

```typescript
// Async transaction (for operations that return values)
const tracks = await api.withinTransaction(() =>
  Promise.all([
    song.createMidiTrack(),
    song.createMidiTrack(),
  ])
);

// Sync transaction (for setting properties)
api.withinTransaction(() => {
  track.name = "KICK";
  track.color = 0xC8003C;
});
```

## Context Menu Registration

```typescript
api.commands.registerCommand("namespace.commandId", async (args) => {
  // command implementation
});

api.ui.registerContextMenuAction(
  contextType,  // string: which context shows this item
  label,        // string: display text in right-click menu
  "namespace.commandId"
);
```

### Known Context Types

| Context Type | When shown |
|---|---|
| `"MidiTrack"` | Right-click a MIDI track header |
| `"AudioTrack"` | Right-click an audio track header |
| `"MidiTrack.ArrangementSelection"` | Time selection on a MIDI track in arrangement |
| `"Song"` | Right-click in empty arrangement area (may vary by beta version) |

## Type Imports

```typescript
import {
  initialize,
  MidiTrack,
  AudioTrack,
  Track,
  DataModelObject,
  MidiClip,
  AudioClip,
  Clip,
  ApiVersion,
  type NoteDescription,
  type ArrangementSelection,
  type ActivationContext,
  type ClipLoopSettings,
} from "@ableton-extensions/sdk";
```

## manifest.json Structure

```json
{
  "name": "Extension Name",
  "author": "Author Name",
  "entry": "./dist/extension.js",
  "version": "1.0.0",
  "minimumApiVersion": "1.0.0"
}
```

## package.json Structure

```json
{
  "name": "extension-name",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22.11.0" },
  "main": "dist/extension.js",
  "scripts": {
    "build": "tsc && node build.ts",
    "build:dev": "tsc && node build.ts --dev",
    "start": "npm run build:dev",
    "package": "npm run build && ableton-extensions package"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "esbuild": "^0.20.0",
    "tsx": "^4.0.0",
    "@types/node": "^22.0.0"
  },
  "dependencies": {
    "@ableton-extensions/sdk": "file:./vendor/ableton-extensions-sdk-1.0.0.tgz"
  }
}
```

## GM Drum Map Reference (for single-track drum rack)

| Note | MIDI | Description |
|------|------|-------------|
| C1   | 24   | Kick (low) |
| C#1  | 25   | Rim shot |
| D1   | 26   | Snare |
| D#1  | 27   | Clap |
| E1   | 28   | Snare edge |
| F1   | 29   | Floor Tom |
| F#1  | 30   | Closed Hi-Hat |
| G1   | 31   | Tom |
| G#1  | 32   | Open Hi-Hat |
| A1   | 33   | Tom |
| A#1  | 34   | Crash |

## Standard Separate-Track Convention

When using one instrument per MIDI track (not a drum rack), trigger notes are typically:
- `C3 = 48` — most common (Simpler default)
- `C2 = 36` — also common

## Pitch Reference (Chromatic)

```
C4 = 60 (middle C)
C3 = 48, C2 = 36, C1 = 24
D = +2, E = +4, F = +5, G = +7, A = +9, B = +11
Flat = -1, Sharp = +1

Cm scale: C(0), D(2), Eb(3), F(5), G(7), Ab(8), Bb(10)
C2 scale: 36, 38, 39, 41, 43, 44, 46
C3 scale: 48, 50, 51, 53, 55, 56, 58
```

## Timing Reference

```
1 bar = 4 beats
8 bars = 32 beats
16 bars = 64 beats

Quarter note = 1 beat
8th note = 0.5 beats
16th note = 0.25 beats
8th note triplet = 0.333 beats
```

## Color Palette (approximate Ableton colors as integers)

```typescript
export const COLORS = {
  RED:        0xC8003C,   // Kick
  ORANGE:     0xFF4E00,   // Snare  
  AMBER:      0xC5A400,   // Hi-Hats
  GREEN:      0x009A39,   // Percs
  BLUE:       0x0047FF,   // Bass
  PURPLE:     0x9100FF,   // Chords
  TEAL:       0x00C8C8,   // Return
  WHITE:      0xFFFFFF,   // Master
};
```

## Installation

1. In Ableton Live 12.4.5+ (Suite), open Preferences → Extensions
2. Click "Add Extension" and navigate to the extension folder
3. The extension loads from `dist/extension.js` (must be built first)
4. To build: `npm install && npm run build` inside the extension folder
5. Right-click in Live to access extension menu items

## Key Limitations (Beta 1.0.0)

- No programmatic triggering — must be manually invoked from right-click menu
- No Max for Live integration
- No headless / server-side execution
- Extensions only run while Ableton is open with GUI
- Suite license required (not Standard, Intro, or Lite)
- Session view clip creation API may differ from arrangement — verify in docs as SDK matures

---

## Dialog / HTML UI (Community-Confirmed)

Extensions can open full HTML dialog windows with custom UIs. Pattern used by Track Creator, Chord Progression Helper, and PaulStretch:

- Build the dialog as a **separate Vite app** (dialog/ subdirectory in the extension)
- Detect Live vs dev mode: `if (window.__INITIAL_DATA__) { /* running in Live */ }`
- The extension host opens the dialog via `api.ui` (exact method TBD — check latest SDK docs)
- Dialog communicates with extension host via the `__INITIAL_DATA__` bridge
- Bundle both the host (`esbuild`) and the dialog (`vite build`) in the same project

```
my-extension/
├── src/index.ts          # host (esbuild → dist/extension.js)
├── dialog/               # Vite app
│   ├── index.html
│   └── src/dialog.ts     # references window.__INITIAL_DATA__
├── vendor/               # SDK tarballs (not on npm yet)
└── package.json          # build:all script runs both
```

This is the pattern to use when an extension needs user input (key selection, sketch picker, intensity sliders, etc.).

---

## External HTTP API Access (Community-Confirmed)

Extensions run in a full Node.js environment with unrestricted network access. Confirmed by:
- **Freesound Sampler** (calls Freesound.org REST API at runtime)
- **Spotify Basic Pitch** (loads neural network model — may fetch model weights)

You can call any external REST API or local server:

```typescript
// Call a local backend (e.g. HouseMusicSwarm running on localhost)
const response = await fetch("http://localhost:8080/generate-sketch", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ key: "C Minor", bpm: 123, vibe: "late night" }),
});
const sketch = await response.json();
```

**Implication:** The dream engine can generate patterns on-demand directly from inside Live, rather than relying solely on pre-generated files from a nightly cron.

---

## WASM Support (Community-Confirmed)

Complex C++ algorithms can run inside extensions via WebAssembly. Confirmed by:
- **PaulStretch for Live** (C++ libpaulstretch compiled to WASM)

Build pattern: compile C++ → WASM, include `.wasm` file in the extension's dist, load via `WebAssembly.instantiateStreaming()` or similar.

---

## Session View Clips (Community-Confirmed)

Session View clips are accessible and writable. Confirmed by the Session→Arrangement Bridge extension which reads Session View clips and writes them to Arrangement View.

The Session clip API likely mirrors the Arrangement clip API (`clip.notes`, `clip.name`, etc.) — verify exact property names in SDK docs.

---

## Distribution Format

Built extensions package as **`.ablx`** files:

```bash
npm run build     # compiles TypeScript + bundles
npm run package   # → produces extension-name.ablx
```

The `.ablx` file is what you share / install. It bundles:
- `dist/extension.js` (the compiled host code)
- `dist/dialog/` (compiled dialog HTML/JS/CSS if present)
- Any fonts, WASM modules, or static assets

During development, install directly from the extension folder (unpackaged). For distribution, share the `.ablx`.

---

## Community Extensions Catalog

See `knowledge/research/extensions-community.md` for a full list of community-built extensions and what API features they confirm. Key ones:

| Extension | Key capability demonstrated |
|---|---|
| Spotify Basic Pitch | Offline neural network audio→MIDI inside an extension |
| Chord Progression Helper | Full chord grid UI dialog, writes 4-note voicings |
| Freesound Sampler | External HTTP API calls |
| PaulStretch | WASM, complex DSP |
| Session→Arrangement Bridge | Session View clip read/write |
| Doom / Bird Game / Snake | Full game-level DOM, HTML canvas, unlimited JS |
