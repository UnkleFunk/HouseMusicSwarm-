---
workflow: general-video
flow: automation
storyboard: no
message: "After 5 years off the grid working a 15-hour mail route, Unkle Funk built his own tools to survive the admin so he could finish 75 unfinished house tracks -- the music itself stays 100% human."
destination: web-embed
aspect: 1920x1080
language: en
audience: house-music fans and the DJ/producer community discovering Unkle Funk's mission
length: 64s
angle: confession / hustle-doc, nocturnal and confident, not defensive about AI
---

## Intent

A 60-second (actual: 64s once real narration pacing is accounted for) mission
trailer for unklefunk.music -- Glenn "Unkle Funk" Giles's five-years-quiet
return: a Chicago house DJ/producer working a 15-hour mail route who never
stopped making music, and who built his own Python/AI tooling to survive the
administrative overhead so studio time stays for the music itself. Locked
shooting script and both prior external-planning-doc revisions were supplied
by the user; the "late-late shift" / AI-transparent revision was selected as
the one consistent with the site's own published mission copy (index.html),
which already states plainly that automation handles admin/overhead, never
the music itself.

This was a "just build it" request -- the user explicitly said the only way
this trailer gets made is if it's built for them, not by them. Per the intent
layer's signal-handling rule this locked flow: automation, storyboard: no.
Every field below that wasn't explicitly specified was defaulted and is
called out as such in the handoff report, not asked as a question.

## Assets

- website/style.css -- the site's real "Neon Nights" design tokens (colors,
  fonts, glow treatments). Used as the design spec directly; no separate
  design.md was authored since this source is authoritative and unambiguous.
- website/assets/break_smoke.jpg -- real photo of Unkle Funk behind the
  decks, copied into this project's assets/photos/ for Scene 2's Ken Burns
  background.
- assets/audio/vo-01..04.wav -- placeholder scratch narration, Kokoro
  (local/offline TTS, am_michael voice). NOT Glenn's real voice -- swap
  before shipping.

## Customizations

- Count-up treatment on the "75" climax stat (Scene 4), cited from
  hyperframes-animation's dataviz-countup blueprint family
  (`counting-dynamic-scale` rule specifically -- a single count-up number,
  not the blueprint's full multi-instrument dashboard form).
- No BGM/music bed generated. The script's own climax line is "Zero percent
  AI-generated... the music is one hundred percent human" -- synthesizing a
  fake AI house bassline to sit under that exact line would contradict the
  video's point. Scenes 4-5 are built silent-under-VO / silent-full-stop to
  receive a real Unkle Funk track bounce instead.
- Typography constrained to the two HyperFrames-pre-bundled families that
  are also the real site's most distinctive faces -- Archivo Black (stat/
  hero numerals) and Space Mono (labels, terminal/mono text) -- rather than
  the site's non-bundled Mr Dafoe script wordmark or Fraunces serif, to keep
  this first-draft render's font loading fully offline-safe. Real wordmark
  treatment can be embedded via @font-face in a later pass if wanted.

## Notes

- Real mail-route storm footage, real father/son footage, and a finished
  "75 Deep" track do not exist in this repo. No text-to-video generation
  (Kling/Hailuo/Veo, as an earlier non-HyperFrames plan suggested) is
  available in this environment -- Scenes 1 and 3 are built as motion
  graphics (animated rain/lightning, terminal + arrangement-window mockups)
  rather than attempted photoreal generation.
- `npx hyperframes auth status` reported not signed in to HeyGen. Continued
  autonomously through the offline/local engines per the brief-contract
  Preflight gate: Kokoro (installed this run) for VO, no BGM (see above,
  a deliberate choice, not a missing-dependency skip).
