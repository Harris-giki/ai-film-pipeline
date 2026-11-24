---
name: dailies
description: Step 13. Transcribes every take with faster-whisper word timestamps, builds the take table, weights folders, snaps dialogue to silence, and logs unused clips.
tools: Bash, Read, Write, Glob
---
1. `${CLAUDE_PLUGIN_ROOT}/fp transcribe <film>` → `09_edit/transcripts.json` (word timestamps + silent ranges per take;
   takes ending in `x` are skipped).
2. `${CLAUDE_PLUGIN_ROOT}/fp dailies <film>` → `09_edit/dailies.md` table: clip id, line, speaker pair, usable in/out
   snapped to the nearest silence, silent action ranges, score. Newest/primary folders first; older
   folders weighted 15-25% lower (`--older-penalty 0.2`).
3. Read it and pick: one banger line per clip beats a full exchange; a clip may be used twice from
   different parts; dropped lines can stay as picture-only cutaways/montage hits.
4. Write `09_edit/selects.json` (`[{"clip":"N01_t2","in":1.20,"out":4.85,"use":"line|cutaway|montage","why":"..."}]`)
   and the unused log with reasons at the bottom of dailies.md.
End with `HANDOFF:` for `editor`.
