import type { NoteDescription } from "@ableton-extensions/sdk";

export type HumanizeIntensity = "tight" | "loose";

// Applies subtle timing drift and velocity variation to MIDI notes.
// "tight" = club-ready but not robotic (~8ms drift, ±6 velocity)
// "loose" = raw organic feel (~16ms drift, ±12 velocity)
export function humanize(
  notes: NoteDescription[],
  bpm: number,
  intensity: HumanizeIntensity = "tight"
): NoteDescription[] {
  const beatsPerMs = bpm / 60000;
  const maxDriftMs = intensity === "tight" ? 8 : 16;
  const maxDriftBeats = maxDriftMs * beatsPerMs;
  const velRange = intensity === "tight" ? 6 : 12;

  return notes.map((note) => ({
    ...note,
    startTime: Math.max(0, note.startTime + (Math.random() - 0.5) * maxDriftBeats * 2),
    velocity: Math.max(1, Math.min(127, note.velocity + Math.round((Math.random() - 0.5) * velRange * 2))),
  }));
}
