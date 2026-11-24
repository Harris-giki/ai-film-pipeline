---
name: mastering
description: Step 24. One-pass master from the cut intermediate (grade, titles, grain, subtitles, final mix) to the delivery spec, then verifies the file and packages stems, SRT, alpha tracks, board JSON and scripts beside it.
tools: Bash, Read, Glob
---
1. Ask the human before rendering. Then `${CLAUDE_PLUGIN_ROOT}/fp master <film>` → `12_master/<film>_final.mp4`
   (H.264 High, 1920x1080, 24 fps, CRF 14 capped 50 Mbps, bt709 tags, faststart, AAC 320k).
2. `${CLAUDE_PLUGIN_ROOT}/fp verify <film> 12_master/<film>_final.mp4 --final` → frame count, LUFS, true peak,
   transcript vs cut, frames from intro/body/outro. Read the frame sheet.
3. `${CLAUDE_PLUGIN_ROOT}/fp package <film>` copies stems, SRT, alpha tracks, board JSON and build scripts beside it.
4. Report measurements and what was not checked. The human posts.
