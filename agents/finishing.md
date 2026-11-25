---
name: finishing
description: Steps 18-21. Colour grade chain, title render + tracked title overlays, and subtitles (alpha track, SRT, burned preview, bright-background flags).
tools: Bash, Read, Write, Edit, Glob
---
1. Grade (step 18): defaults come from the film's style pack (`00_brief/style.json` -> `grade`), written to
   `10_finish/grade.json`. The original playbook's heavy halation and grain lifted the blacks and washed the
   picture out, so the packs are tuned against measured targets. Workflow:
   a. `${CLAUDE_PLUGIN_ROOT}/fp master <film>` once, then `${CLAUDE_PLUGIN_ROOT}/fp lookmatch <film>` to measure luma, black point,
      saturation and contrast against the style's `target_metrics` (or `--ref <film.mp4>` to match a reference).
   b. `${CLAUDE_PLUGIN_ROOT}/fp lookmatch <film> --apply` fits the grade numerically on sampled frames of the cut
      (closed loop, about 1 minute), then master again and re-measure. It refuses to apply twice without a re-master.
   c. Style post runs automatically in the master: stop-motion stepping (`frame_step`), pixelation and a limited
      dithered palette, and paper texture. Don't add these by hand.
   Preview stills: `${CLAUDE_PLUGIN_ROOT}/fp grade-preview <film> <clip>`; get approval.
2. Titles (19-20): render each word with `blender -b -P ${CLAUDE_PLUGIN_ROOT}/blender/title.py -- --text WORD --font <otf>
   --out 10_finish/titles/WORD` (one Blender at a time). Tracked overlays are ProRes 4444 alpha tied
   to ONE source clip; record in `10_finish/titles.json` `{"overlay":"...mov","clip":"N01_t2"}`.
   The master pass trims the overlay by the same N frames the cut trims the clip head, and composites
   after grade, before grain. Never retime/reframe/stabilise that clip.
3. Subtitles (21): `${CLAUDE_PLUGIN_ROOT}/fp subs <film>` → SRT + alpha ProRes + burned preview + luminance flags.
   Show the flags to the human for a decision.
