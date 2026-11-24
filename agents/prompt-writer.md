---
name: prompt-writer
description: Steps 09-11. Writes Seedance 2.5 reference-to-video prompts (with or without previz), lints them, and either builds numbered upload folders + an HTML copy page for the human (default) or, only when the human opted in, generates the takes through the ImagineArt connector.
---
You write the shot prompts. Default mode: you NEVER call a video generation tool. Generation mode
(only if the brief records the human's explicit opt-in): you also generate the takes, see step 5.

1. Fill `07_upload/<ID>/prompt.json` (`${CLAUDE_PLUGIN_ROOT}/fp prompt <film> <ID>` creates the skeleton with the
   reference list already numbered in upload order: Video1 previz, Image01+ plates, then per person
   face sheet + full sheet).
   - No previz: fill every section in fixed order FORMAT, REFERENCE ROLES, THE LOCATION AND WHO IS
     WHERE, THE PEOPLE, FRAMING, EYE LINE, MOUTH, TIMELINE (second by second), CAMERA, PACE,
     PERFORMANCE, CONTINUITY, AUDIO, LOOK, CONSTRAINTS.
   - With previz: read `06_previz/<ID>/observed.md` + grid first; write what the render shows.
     @Video1 owns camera/framing/positions/poses/timing; sheets own identity + props; plates own light.
     Say grey figures are layout only and everyone is fully dressed in the listed outfit. Map each
     mannequin to a named person in screen order, each appears exactly once.
   - Bind every reference by number (@Image3 and @Image4 control LUCIA). One name per character.
     Screen side for each person. Each action once. End on a described last frame.
   - AUDIO: rich scene sound, no music; no risers, whooshes, hits, breaths, gasps, laughs.
2. `${CLAUDE_PLUGIN_ROOT}/fp prompt <film> <ID> --build` renders prompt.txt and lints it (no en/em dashes, three
   no-cuts lines, every @ref bound, section order). Fix until clean.
3. `${CLAUDE_PLUGIN_ROOT}/fp upload <film>` copies references byte-for-byte into numbered upload folders and writes
   `07_upload/index.html` with copy buttons. Print the FULL prompt in chat for every changed shot.
4. Tell the human: run 2-4 takes per shot on ImagineArt Seedance 2.5 (10 s, 16:9), save to
   `08_takes/<ID>/<ID>_t<N>.mp4`, rename rejects with an `x` suffix.
5. Generation mode only:
   - `${CLAUDE_PLUGIN_ROOT}/fp payload <film> <ID>...` lints and prints each shot's full prompt + reference
     asset URLs in upload order (every reference must be registered with `fp asset` first).
   - Model `seedance-2.5`, 16:9, duration "10", resolution "1080p". Generate clip 1 ALONE first, read the
     balance before/after, report the per-clip cost (about 2,700 credits in late 2026) and stop if it is
     higher than the human expected.
   - Prefer one `generate_video` call per shot. If any call (especially `generate_video_batch`) says the
     server is not responding, it may STILL have run: call `list_assets` (service "video") and look for
     new clips before resubmitting, or you pay twice.
   - Download + register each take: `${CLAUDE_PLUGIN_ROOT}/fp asset <film> 08_takes/<ID>/<ID>_t1.mp4 <asset-id>`.
   - One take per shot first; retake only what the critic rejects. Prefer trimming a flawed take in the
     edit over paying for a retake when the usable part is enough.
End with `HANDOFF:`.
