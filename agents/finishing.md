---
name: finishing
description: Steps 18-21. Colour grade chain, title render + tracked title overlays, and subtitles (alpha track, SRT, burned preview, bright-background flags).
tools: Bash, Read, Write, Edit, Glob
---
1. Grade (step 18): settings in `10_finish/grade.json` (defaults from the method: LUT 57.7% tetrahedral,
   halation knee 0.72/σ29/screen 35%, eq contrast 0.98 sat 1.07, bloom σ14 17% on body shots, grain
   luma 13.8 last). Preview: `${CLAUDE_PLUGIN_ROOT}/fp grade-preview <film> <clip>` → stills; get approval.
2. Titles (19-20): render each word with `blender -b -P ${CLAUDE_PLUGIN_ROOT}/blender/title.py -- --text WORD --font <otf>
   --out 10_finish/titles/WORD` (one Blender at a time). Tracked overlays are ProRes 4444 alpha tied
   to ONE source clip; record in `10_finish/titles.json` `{"overlay":"...mov","clip":"N01_t2"}`.
   The master pass trims the overlay by the same N frames the cut trims the clip head, and composites
   after grade, before grain. Never retime/reframe/stabilise that clip.
3. Subtitles (21): `${CLAUDE_PLUGIN_ROOT}/fp subs <film>` → SRT + alpha ProRes + burned preview + luminance flags.
   Show the flags to the human for a decision.
