# When it breaks, fix the cause (step 12)

Never patch a symptom with prompt wording. Find the input that caused it and change that input.

| Symptom | Cause | Fix |
|---|---|---|
| Shoes painted under the headshots | Sheet2 was built from the full-body turnaround | Rebuild Sheet2 from a single 4:5 portrait |
| Clip cuts mid-shot | A plate's framing matches the shot / previz camera | Remove that plate, or regenerate it from a different angle |
| Clip too dark | Plate is dark (plates set brightness + palette) | Generate a new plate from scratch. Never colour-boost |
| Wrong person driving | Reference order ambiguous | Put that character's sheets first and say who holds the wheel |
| Same person painted twice in a group | Mannequins were identical | Re-render previz with distinct builds/poses, cut cast to ≤7, list people one by one in front-view order |
| Line stops mid-word | Take too short | Extend the take (regenerate). Never trim a word |
| Physics morphing | Model artefact | Audit physics per take; drop only obvious morphing, not everything |
| "output video has sensitive content" | Picture side | Change only picture inputs/wording |
| "output audio ..." error | Sound side | Change only AUDIO section (remove human non-speech sounds, risers, music) |
| Action happens twice | Action described twice / no end frame | Each action once; end on a described last frame |
| Seedance ignores prompt camera | Previz owns camera | Change the previz render, not the words |
| Extra people near lens | People near camera multiply | Keep mannequins ≥2.5 m from camera |
| Speed doesn't read on roads | Featureless road | Line road with repeating objects (poles, cones) in previz |
| Dialogue sounds echoey | Dialogue stem + clip audio doubled with a lag | `pipeline echo` → shift by measured lag, then blend |
| Subtitle unreadable | Bright background behind line | Flagged by `pipeline subs`; human decides (reposition or accept) |
