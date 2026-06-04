import { initialize, MidiClip, type ActivationContext } from "@ableton-extensions/sdk";
import { COLORS } from "./colors.js";

// ─── Import all available sketches ────────────────────────────────────────────
// Each sketch exports: SKETCH_NAME, BPM, BARS, KEY, and 6 note generator functions
import * as sketch_20260604 from "./sketches/2026-06-04.js";
// NEW SKETCHES ARE ADDED HERE AUTOMATICALLY BY THE DREAM ENGINE

const SKETCHES = [
  sketch_20260604,
  // additional sketch imports appended here nightly
] as const;

const BEATS_PER_BAR = 4;
const ARRANGEMENT_START = 0; // beat position where sketch is placed

interface SketchModule {
  SKETCH_NAME: string;
  BPM: number;
  BARS: number;
  KEY: string;
  kickNotes: () => import("@ableton-extensions/sdk").NoteDescription[];
  snareNotes: () => import("@ableton-extensions/sdk").NoteDescription[];
  hatNotes: () => import("@ableton-extensions/sdk").NoteDescription[];
  percNotes: () => import("@ableton-extensions/sdk").NoteDescription[];
  bassNotes: () => import("@ableton-extensions/sdk").NoteDescription[];
  chordNotes: () => import("@ableton-extensions/sdk").NoteDescription[];
}

const TRACK_DEFS = [
  { key: "kickNotes",   name: "KICK",   color: COLORS.KICK   },
  { key: "snareNotes",  name: "SNARE",  color: COLORS.SNARE  },
  { key: "hatNotes",    name: "HATS",   color: COLORS.HATS   },
  { key: "percNotes",   name: "PERCS",  color: COLORS.PERCS  },
  { key: "bassNotes",   name: "BASS",   color: COLORS.BASS   },
  { key: "chordNotes",  name: "CHORDS", color: COLORS.CHORDS },
] as const;

async function loadSketch(api: ReturnType<typeof initialize>, sketch: SketchModule) {
  const song = api.application.song;
  const durationBeats = sketch.BARS * BEATS_PER_BAR;

  // Set tempo
  api.withinTransaction(() => {
    song.tempo = sketch.BPM;
  });

  // Create 6 MIDI tracks
  const tracks = await api.withinTransaction(() =>
    Promise.all(TRACK_DEFS.map(() => song.createMidiTrack()))
  );

  // Name and color tracks
  api.withinTransaction(() => {
    tracks.forEach((track, i) => {
      track.name = TRACK_DEFS[i].name;
      track.color = TRACK_DEFS[i].color;
    });
  });

  // Create arrangement clips
  const clips = await api.withinTransaction(() =>
    Promise.all(
      tracks.map((track) =>
        track.createMidiClip(ARRANGEMENT_START, durationBeats)
      )
    )
  );

  // Name clips and write MIDI notes
  api.withinTransaction(() => {
    clips.forEach((clip, i) => {
      clip.name = `${sketch.SKETCH_NAME} — ${TRACK_DEFS[i].name}`;
      clip.color = TRACK_DEFS[i].color;
      if (clip instanceof MidiClip) {
        const noteKey = TRACK_DEFS[i].key as keyof SketchModule;
        const noteFn = sketch[noteKey] as () => import("@ableton-extensions/sdk").NoteDescription[];
        clip.notes = noteFn();
      }
    });
  });
}

export async function activate(activation: ActivationContext) {
  const api = initialize(activation, "1.0.0");

  // Register one command and context menu item per sketch
  for (const sketch of SKETCHES) {
    const commandId = `unkle-funk-sketch.${sketch.SKETCH_NAME.toLowerCase().replace(/\s+/g, "-")}`;
    const label = `Load Sketch: ${sketch.SKETCH_NAME} (${sketch.BPM} BPM, ${sketch.KEY})`;

    api.commands.registerCommand(commandId, async () => {
      await loadSketch(api, sketch as SketchModule);
    });

    api.ui.registerContextMenuAction("MidiTrack",  label, commandId);
    api.ui.registerContextMenuAction("AudioTrack", label, commandId);
  }
}
