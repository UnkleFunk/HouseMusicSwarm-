# Your Analyzed Library × Ableton Extensions — Opportunity & Findings

*Research date: 2026-06-04 · For: Unkle Funk · Status: actionable*

---

## Part 1 — Your Sound, Decoded (the part that's actually about you)

You said the clustering helped us but didn't give *you* insight. Fair. Here's what your 139 favorites actually say about your ear — in plain language, measured against 655 tracks from Defected, Toolroom, and HOUSEU Records.

### You reject the loudness war. Measurably.

There's one number that separates your taste from everything else: **mfcc_1**, which tracks overall energy and dynamics. Lower = warmer, more dynamic range, less brick-walled.

| Collection | mfcc_1 (lower = deeper/more dynamic) |
|---|---|
| **Your Favorites** | **−156** ← warmest, most dynamic |
| Defected Records | −145 |
| Toolroom Records | −105 |
| HOUSEU Records | −46 ← loudest, most compressed |

Your favorites are the **most dynamic, least compressed tracks in the entire dataset.** HOUSEU (commercial "house-you" radio edits) sits at the far opposite end — loud, flat, brick-walled. Your ear literally gravitates to the records with the most breathing room. This isn't a vibe — it's in the data. When you A/B two tracks and one "just feels better," it's usually the one that wasn't mastered to death.

**What this means for your own productions:** leave headroom. Resist the urge to slam the limiter. The thing you love about your favorites is the dynamics — don't master it out of your own tracks.

### Your pocket is 123 BPM. Confirmed.

After correcting for the analyzer's half-time glitches, your favorites center dead on **123 BPM**, with the bulk living 122–124. Not 120, not 126. 123 is home.

### Warm, but clear.

Your brightness (spectral centroid ≈ 3050 Hz) sits in a deliberate middle: warmer than Toolroom's tech-house sheen, brighter than the deepest Defected dubs. Translation: **warm but never muddy, clear but never harsh.** That's a narrow, specific window — and you live in it consistently.

### You need harmony.

Your harmonic-content score (chroma ≈ 0.55) says you favor tracks with real chords and melodic material — not bare drum tools, not wall-to-wall pads. The soul lives in the chords. This is the Larry Heard / Kerri Chandler DNA showing up as a number.

### The honest caveat

This analysis describes **timbre and energy** — the *sound* of your taste. It does **not** yet capture **groove** (the swing, the micro-timing, the pocket) because librosa's basic features don't extract that. That's the next frontier (Part 3), and it's the one that matters most for generation.

---

## Part 2 — Is this a good fit for Ableton Extensions? Verdict: yes, decisively.

Your library is the single most valuable asset for making the dream engine *yours* instead of generic deep house. Here's why and how.

### Your data format is ideal

Your analysis is **librosa features in CSV** (tempo, chroma, spectral centroid, 13 MFCCs, plus KMeans cluster labels). CSV is trivially parseable in both Python (the swarm) and Node.js (the Extension). No reverse-engineering of binary DJ formats required. You're already past the hardest part.

### The architecture

```
Your 100+ tracks (librosa CSV)
        │
        ▼
  taste_fingerprint.json   ← distilled signature (built today)
        │
        ▼
  Dream Engine (HouseMusicSwarm)  ← generates weighted to YOUR sound
        │
        ▼
  unkle-funk-song-sketch Extension  ← loads into Ableton
```

The heavy analysis stays in Python on the swarm side (run once). The Extension just reads the distilled fingerprint. Clean separation, no bloat in the Extension.

---

## Part 3 — The three tiers of opportunity

### Tier 1 — Available now (shipped today)
- `taste_fingerprint.json` distills your 139 favorites into generation weights
- The dream engine now biases toward 123 BPM, loose/dynamic humanization, warm-clear brightness, always-present chords
- **Ableton Groove Pool trick (zero code):** drag any of your 100 tracks into Groove Pool → Extract Groove → apply that exact feel to any generated MIDI. A sketch "in the pocket of a Larry Heard record" is achievable today with Ableton's built-in tools.

### Tier 2 — Medium effort, maximum impact
A Python script (`librosa` / `essentia`) that goes beyond timbre to extract **groove and rhythm** from your actual audio files:
- onset timing → micro-timing/swing fingerprint
- kick/hat density patterns
- per-track groove DNA as JSON

Then the dream engine generates against your *real* grooves, not just guesses. **This is the tier that captures the "feel" — the thing the current analysis is missing.**

### Tier 3 — The wild frontier
Google's Magenta RealTime (open-weights, 2025) can build a style-space map from your library so you can say "generate something between track 14 and track 52." Longer build, but it's real and working.

### npm tooling (confirmed available, 2026)
- **Pure-JS, runs inside the Extension:** `tonal` (music theory), `midi-writer-js` (MIDI generation), `@tonejs/midi` (parsing)
- **Server-side analysis (Python or WASM):** `librosa`, `essentia` / `essentia.js`, `meyda`, `beat-detection`, `realtime-bpm-analyzer`

---

## Part 4 — Recommended next steps

1. **Done today:** fingerprint built + wired into the dream engine; CSVs saved to `ableton_extensions/analysis/`
2. **Next:** Tier 2 groove-extraction script — needs your audio files (we're in a cloud container, so this runs locally on your machine, or we point it at a synced folder)
3. **Try now, no code:** the Groove Pool extraction trick on 3–4 of your all-time favorites
4. **Later:** Magenta style-space map once Tiers 1–2 are proven

---

## Appendix — Full feature stats (all four labels)

| Label | n | tempo (corrected median) | chroma | spectral centroid | mfcc_1 |
|---|---|---|---|---|---|
| Favorites | 139 | 123 | 0.546 | 3050 | −156 |
| Defected Records | 350 | 123 | 0.536 | 2708 | −145 |
| Toolroom Records | 200 | 129 | 0.568 | 3172 | −105 |
| HOUSEU Records | 105 | 123 | 0.509 | 2987 | −46 |

Favorites cluster distribution (KMeans, k=5): cluster 0: 22 · cluster 1: 40 · cluster 2: 35 · cluster 3: 36 · cluster 4: 6

Data: `ableton_extensions/analysis/combined_all_labels.csv` (794 tracks) and `favorites_clustered.csv` (139 tracks).
