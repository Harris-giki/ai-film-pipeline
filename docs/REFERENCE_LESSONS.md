# What a top-tier AI trailer does that our first film didn't

We measured a 66 s, professionally made AI game-trailer short frame by frame (cut detection, one frame per
shot, transcription, loudness, look metrics) and compared it with our first 60 s film, SUNSHINE.
These numbers drive the defaults of the realistic style pack and the scene designer.

| | Reference | SUNSHINE v1 | What changed in the pipeline |
|---|---|---|---|
| Distinct setups / cuts | ~45 / 49 | 16 / 23 | `pacing.setups_per_minute`; `fp scenes` warns below 70% of target |
| Median shot | 0.96 s | ~2.6 s | Editor targets from `pacing.median_shot_s`; 1-3 cuts per setup |
| Densest 10 s | 21 cuts (0.2-0.5 s montage) | 13 hits | `pacing.montage_hit_s` |
| Characters / locations | ~25 / ~30 (one-shot vignettes) | 3 / 7 | WORLD warning; vignette characters are cheap (4-6 s clips) |
| Dialogue | 125 words, about one line every second shot | 25 words | `pacing.dialogue_shot_share` warning |
| Title | over an aerial at 4.6 s | at the end | `pacing.title_by_s` |
| Lighting | motivated per shot (neon, practicals, golden hour, fluorescent, firelight) | one hazy LOOK everywhere | mandatory `LIGHTING` prompt section and per-scene `lighting` |
| Camera | close-ups, low angles, OTS foregrounds, inserts, aerials, handheld | mostly static mediums | per-scene `lens` from the style's `camera_language` |
| Luma / black point / saturation | 0.31 / 0.033 / 0.51 | 0.41 / 0.078 / 0.39 | new realistic LOOK (no blanket haze), retuned grade, `fp lookmatch` |
| Loudness | -13.9 LUFS / -1.6 dBTP | -14.3 / -1.5 | already on target |

## Diagnosis
1. **Too few images.** Quality in a trailer is mostly density: a new place, face or angle every second.
   We cut 16 clips into 23 shots, so the same images kept coming back.
2. **One look for every shot.** The playbook's LOOK block ("gentle haze, volumetric light rays ... heavy
   grain") was applied verbatim to every image and clip. It made night, day and interiors share the same
   milky haze. The reference lights each shot from its own sources.
3. **Grade lifted the blacks.** 35% halation, heavy grain and contrast below 1 pushed the black point to
   0.078 (reference 0.033) and drained the saturation.
4. **A small world.** Three leads in seven places can't feel like a city. The reference fills its world with
   one-shot characters (a beachgoer, a manicurist, a DJ) who each get a single striking moment.

## Re-grading SUNSHINE with the fixes (same clips, new grade only)
After `fp style sunshine realistic-cinematic` and `fp lookmatch sunshine --apply`, the master measured
luma 0.319 (target 0.31), saturation 0.499 (0.50), black point 0.026 (0.035), with dialogue still
word-perfect and loudness in spec. The grade gap is closed numerically. The density gap can only be closed
by designing more setups, which `fp scenes` now enforces.
