---
name: sound
description: Steps 22-23. Three-layer mix (dialogue, clip scene sound, music with band-limited dips), designed effects, echo detection/fix, loudness to -14 LUFS / -1 dBTP.
tools: Bash, Read, Write, Edit, Glob
---
1. `${CLAUDE_PLUGIN_ROOT}/fp stems <film>` → `11_sound/dialogue.wav`, `scene.wav` (from the board, 4-frame
   constant-power crossfades, tails ≤0.5 s, ~12 dB under speech outside montage), `music.wav`.
2. `${CLAUDE_PLUGIN_ROOT}/fp echo <film>` — cross-correlates the dialogue stem against clip audio per line; a constant
   lag (e.g. 32 ms) means a doubled voice → shift and blend. Report lags.
3. `${CLAUDE_PLUGIN_ROOT}/fp mix <film>` gain-stages first (speech to -20 LUFS, music 10 dB under speech during
   dialogue segments and 2 dB under elsewhere; generated songs arrive far louder than AI-clip dialogue), then — music dips only 350-4500 Hz by ~4.6 dB across whole dialogue segments
   (0.8 s down, 1.2 s up), full in montage; dialogue +2 dB in montage; optional `--clarity`;
   designed FX from `11_sound/fx.json` 3 dB under spec with 12% dark reverb; master -14 LUFS,
   TP ≤ -1 dBTP through a 4x oversampled limiter. Report measured LUFS/TP, and if `verify` hears no speech
   in the mix, the dialogue is buried: fix the mix, not the verifier.
