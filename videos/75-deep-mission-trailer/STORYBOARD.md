---
format: 1920x1080
duration: 64s
message: "After 5 years off the grid working a 15-hour mail route, Unkle Funk built his own tools to survive the admin so he could finish 75 unfinished house tracks -- the music stays 100% human."
arc: Disappearance -> Late Shift -> Systems -> Climax -> Outro
audience: house-music fans and the DJ/producer community discovering Unkle Funk's mission
mode: autonomous
---

## Frame 1 — The Disappearance

- scene: Stylized night rain + lightning gives way to an empty 15-box social-post grid and a huge "5 YEARS" stat
- duration: 14s
- transition_in: cut
- status: animated
- voiceover: "For the last five years, I completely disappeared from the grid. No posts. No updates. No social scene. Just a fifteen-hour-a-day mail route, and the beautiful chaos of becoming a dad at forty-one."
- src: compositions/scene1-disappearance.html

Cold open. No literal mail-route footage exists (see BRIEF.md Notes), so this
is built as motion graphics: 12 animated rain streaks + two fixed-time
lightning flashes, crossfading into a dead-social-grid reveal and a "5 YEARS
OFF THE GRID" Archivo Black stat.

## Frame 2 — The Late Shift

- scene: Ken-Burns push on a real studio photo, an analog clock spins from 11:58 PM to 5:15 AM as the tint shifts night-blue to morning
- duration: 14s
- transition_in: cut
- status: animated
- voiceover: "But I never stopped creating. Every single night, while the world slept, I took the late-late shift in my studio. Fighting sleep at my desk just to squeeze out a few spare seconds of music before heading back to the route."
- src: compositions/scene2-late-shift.html

Real asset: website/assets/break_smoke.jpg (copied to assets/photos/). Clock
hands spin via a finite-repeat rotation tween; the two time readouts are
separate crossfaded elements, not a mid-timeline text swap, to stay seek-safe
at any render time.

## Frame 3 — The Systems

- scene: A mock terminal types out the discovery/deploy pipeline, hard-cuts to a mock Ableton-style arrangement window with a single playhead sweep
- duration: 14s
- transition_in: cut
- status: animated
- voiceover: "To survive the time crunch, I vibe-coded Python scripts and used AI automations to handle the administration, the website, and the tedious track-hunting. But the music? The music is one hundred percent human."
- src: compositions/scene3-systems.html

No real screen-capture footage exists; built as two HTML/CSS UI mockups
(terminal + arrangement window) in the site's plaid-weave/Neon-Nights
treatment, closing on "THE MUSIC IS 100% HUMAN."

## Frame 4 — The Climax

- scene: A glowing Archivo Black counter ticks 1 -> 75 over a pulsing teal/blue glow
- duration: 10s
- transition_in: cut
- status: animated
- voiceover: "Seventy-five tracks are sitting on this hard drive. Zero percent AI-generated. This is 75 Deep. Time to finish the journey."
- src: compositions/scene4-climax.html

Cites hyperframes-animation's `counting-dynamic-scale` rule (from the
dataviz-countup blueprint family) — a proxy-object GSAP tween drives both the
digit and a proportional scale-grow, onUpdate-based so it stays correct under
arbitrary-time seeking.

## Frame 5 — The Outro

- scene: "75 DEEP // unklefunk.music" brand lockup holds, then fades to black
- duration: 12s
- transition_in: cut
- status: animated
- voiceover: (none — reserved for the real track, see BRIEF.md Customizations)
- src: compositions/scene5-outro.html

No BGM generated on purpose — see BRIEF.md. This scene is a silent hold built
to receive a real Unkle Funk track bounce at assets/audio/bassline.mp3.
