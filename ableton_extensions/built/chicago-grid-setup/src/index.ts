import { initialize, type ActivationContext } from "@ableton-extensions/sdk";

// Track order and colors
const TRACKS = [
  { name: "KICK",   color: 0xC8003C },
  { name: "SNARE",  color: 0xFF4E00 },
  { name: "HATS",   color: 0xC5A400 },
  { name: "PERCS",  color: 0x009A39 },
  { name: "BASS",   color: 0x0047FF },
  { name: "CHORDS", color: 0x9100FF },
] as const;

const DEFAULT_BPM = 123;
const CLIP_LENGTH_BARS = 8;
const BEATS_PER_BAR = 4;

export async function activate(activation: ActivationContext) {
  const api = initialize(activation, "1.0.0");

  api.commands.registerCommand("chicago-grid-setup.create", async () => {
    const song = api.application.song;

    // Set tempo
    api.withinTransaction(() => {
      song.tempo = DEFAULT_BPM;
    });

    // Create all 6 MIDI tracks
    const tracks = await api.withinTransaction(() =>
      Promise.all(TRACKS.map(() => song.createMidiTrack()))
    );

    // Name and color tracks
    api.withinTransaction(() => {
      tracks.forEach((track, i) => {
        track.name = TRACKS[i].name;
        track.color = TRACKS[i].color;
      });
    });

    // Create empty 8-bar clips in each track starting at bar 1 (beat 0)
    const clips = await api.withinTransaction(() =>
      Promise.all(
        tracks.map((track) =>
          track.createMidiClip(0, CLIP_LENGTH_BARS * BEATS_PER_BAR)
        )
      )
    );

    // Name each clip
    api.withinTransaction(() => {
      clips.forEach((clip, i) => {
        clip.name = TRACKS[i].name;
        clip.color = TRACKS[i].color;
      });
    });
  });

  api.ui.registerContextMenuAction("MidiTrack", "Chicago Grid Setup (123 BPM)", "chicago-grid-setup.create");
  api.ui.registerContextMenuAction("AudioTrack", "Chicago Grid Setup (123 BPM)", "chicago-grid-setup.create");
}
