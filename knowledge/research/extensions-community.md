# Ableton Extensions — Community Discoveries (June 2026)

*Compiled from community repos, articles, and developer sites. Updated as links come in.*

---

## Key Resources (Check Regularly)

| Resource | URL | What's There |
|---|---|---|
| **liveextensions.co** | https://liveextensions.co/browse | Community library — find/share `.ablx` files |
| **Akihiko Matsumoto** | https://akihikomatsumoto.com/study/ableton-extensions-sdk.html | SDK study notes from a generative music developer; made "Ableton Air" (ambient generative sequencer) with the SDK |
| **Federico Pepe's repo** | https://github.com/federico-pepe/ableton-live-extensions | 13 open-source extensions, full TypeScript source |
| **PaulStretch for Live** | https://github.com/olilarkin/paulstretch-for-live | WASM extension pattern, `.ablx` packaging |
| **Ableton Discord** | discord.gg/ableton | Dedicated Extensions channel — fastest community signal |
| **Hacker News thread** | https://news.ycombinator.com/item?id=48389681 | Technical discussion, launch day discoveries |

---

## Community-Built Extensions Catalog

### Federico Pepe's Collection (13 extensions, all open source)

| Extension | What it does | Relevance to dream engine |
|---|---|---|
| **Arrangement Helper** | Named, colored MIDI sections for song structure | Could scaffold Intro/Drop/Breakdown structure |
| **Basic Pitch (Spotify)** | Neural network: audio file → MIDI clip, runs offline | **Tier 2 breakthrough** — feed a Larry Heard track in, get MIDI groove out |
| **Bird Game** | Flappy Bird that writes MIDI from gameplay | Proves: full HTML games run inside extensions |
| **Chord Progression Helper** | Grid UI, functional jazz + dark harmony modes, writes 4-note close voicings to clip | **Direct template** for a chord UI in the dream engine |
| **Chord Voicing Helper** | Detects chords in clips, applies voicing strategies | Post-generation voicing transform |
| **ChromaFlux** | Randomizes Instrument Rack parameters | Inspiration variation without changing MIDI |
| **Doom** | Full 1993 Doom running inside Live | Proves: offline games, WASM, full DOM |
| **Duplicate Track** | Copies track settings, no clips | Workflow util |
| **Freesound Sampler** | Searches Freesound.org, downloads samples | Proves: external HTTP API calls work in extensions |
| **Session→Arrangement Bridge** | Moves Session View clips to Arrangement | Session View clips are readable/writable too |
| **Snake** | Snake game → MIDI | More game-as-MIDI-generator |
| **Track Creator** | Dialog UI → creates N tracks | Reference for dialog input pattern |
| **Transposer** | Transposes all clips in a set by semitones | Bulk MIDI transform |

### Other Notable Community Work

| Extension | What it does |
|---|---|
| **BBenCut** | Automated breakbeat slicer based on SuperCollider's BBCut. Multiple algorithms + parameters. jungle/DnB chopping logic as an extension |
| **PaulStretch for Live** | Extreme audio time-stretching (WASM, C++ core). Ambient soundscape generator from any audio snippet |
| **Ableton Air** (Matsumoto) | Ambient generative sequencer — full generative composition running as an extension |

---

## Technical Capabilities Confirmed by Community

### Dialog / HTML UI System
Extensions can open full HTML dialog windows with custom UIs:
- Build the dialog as a separate Vite app
- Detect Live mode vs dev mode via `window.__INITIAL_DATA__`
- Pass data in/out of the dialog
- Track Creator and Chord Progression Helper both use this pattern (input fields, grids)
- PaulStretch uses it for its full processing UI

**Dream engine implication:** We can build a "tonight's sketch" dialog where Glenn picks key, kick pattern, vibe, and the extension generates accordingly — instead of just right-click options.

### External HTTP API Access
Confirmed by Freesound Sampler (calls Freesound.org REST API from inside Live).

**Dream engine implication:** The extension itself could call the swarm API or an AI endpoint. Glenn opens Live, right-clicks, the extension hits the HouseMusicSwarm backend, gets a fresh AI-generated pattern, and loads it. No separate nightly cron required — on-demand generation.

### Offline Neural Network (Spotify Basic Pitch)
Full offline audio-to-MIDI via neural network running inside Node.js with no internet required.

**Tier 2 implication:** This is exactly the groove extraction pipeline we wanted. Instead of a separate Python script, Glenn could install the Basic Pitch extension, drop any of his 139 favorite tracks into a track, right-click → "Extract MIDI Groove" → get a MIDI clip representing the actual groove of that record. Then we analyze those MIDI clips for micro-timing. This replaces the entire planned Python librosa groove-extraction script.

### WASM Support
Confirmed by PaulStretch (C++ libpaulstretch via WebAssembly). Complex DSP algorithms can run inside extensions.

**Future implication:** Magenta RealTime (Tier 3) might be deployable as a WASM module inside an extension. Style-conditioned generation without leaving Live.

### Session View Clips
The Session→Arrangement Bridge reads Session View clips and writes them to Arrangement View, confirming that Session View clip API exists.

### Full DOM / Games
Doom and Bird Game confirm that extensions run in a full Chromium/Node.js environment with no sandboxing on DOM access. This means rich HTML, WebGL, WebAudio within the dialog all work.

---

## What This Changes for the Dream Engine Roadmap

### Immediate (can add now)

1. **Dialog UI for sketch selection** — instead of one right-click item per sketch, one right-click "Dream Sketch..." that opens a dialog showing all sketches with ratings, letting Glenn pick or regenerate
2. **External API call** — the extension can call `api.housemusicswarm.io` or `localhost:PORT` to get fresh AI-generated patterns on demand. This removes the need for a separate nightly cron entirely (it becomes a "generate now" button in Live)

### Medium (next sprint)

3. **Basic Pitch integration** — Glenn right-clicks any audio track with a reference track loaded → "Extract Groove to MIDI" → MIDI clip created. This is Tier 2 groove extraction without any Python

### Future (Tier 3 territory)

4. **WASM Magenta** — if Magenta RealTime ships as a portable WASM module, it could run entirely inside an extension. "Generate in style of these 3 tracks" from inside Live.

---

## Videos Shared by Glenn (to research when accessible)

- https://youtu.be/rFjkRVo6n_s — Extensions community showcases (24hrs after launch)
- https://youtu.be/f6XJ7QlxInY — Extensions demonstrations
- https://akihikomatsumoto.com/study/ableton-extensions-sdk.html — Matsumoto's SDK study notes

*Note: YouTube videos return 403 from cloud container. When Glenn can share titles/descriptions, or when the content becomes searchable, update this file.*
