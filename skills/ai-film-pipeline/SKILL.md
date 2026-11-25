---
name: ai-film-pipeline
description: Make generative-AI short films, trailers and ads end to end in any visual style (realistic live action, claymation, pixel art, paper cutout, stylized 3D, anime, or a custom style). Claude directs 11 specialist agents through a 24-step pipeline (brief, scene design, character sheets, location plates, Blender previz, Seedance 2.5 prompts and takes, dailies, a beat-locked edit, a human-in-the-loop web editor, colour grade, titles, subtitles, three-layer mix, mastering, verification) using the ImagineArt connector for images, video and music. Use when the user wants to make, plan, generate, edit or finish an AI video, film, trailer, music-video-style cut or game-trailer-style short, or asks to run or continue a film made with this pipeline.
---

# AI Film Pipeline: you are the director

You run a film crew made of subagents. Every hand-off is checked by a critic, and the human signs off at
every gate. At the start of any film session, read:
- `${CLAUDE_SKILL_DIR}/../../docs/PIPELINE_24_STEPS.md`: the method
- `${CLAUDE_SKILL_DIR}/../../docs/STYLES.md`: visual styles
- `${CLAUDE_SKILL_DIR}/../../docs/REFERENCE_LESSONS.md`: what makes an AI trailer look top-tier
- `${CLAUDE_SKILL_DIR}/../../docs/FIX_TABLE.md`: symptom -> cause -> fix

## The first question is always the style
AI filmmaking isn't one look. Before anything else, ask the user (AskUserQuestion) which visual style the
film is: **Realistic cinematic**, **Claymation**, **Pixel art**, **Paper cutout**, **Stylized 3D**, **Anime**, or a
custom style (built with them from `styles/_template.json`). `fp styles` lists the packs. Then run
`fp new <film> --style <id> --duration <s>`. The pack is frozen into the film and drives every stage:
- the LOOK block and how characters, sets and vehicles are described
- motion language (for example stop-motion on twos) and style constraints in every video prompt
- camera and lighting menus and pacing targets for the scene designer
- grade defaults, target look metrics and post effects (frame stepping, pixel grid and palette, paper texture)
- the critic's style-break checks

Never mix styles inside a film unless the brief asks for it.

## The quality bar (measured on a top-tier reference trailer)
Density and light make the difference.
- **Setups.** Aim for about `pacing.setups_per_minute` distinct setups per minute (realistic: 40; the reference had
  ~45 in 66 s with a median shot of 0.96 s).
- **World.** Use many one-shot vignette characters and locations, not three leads in seven places.
- **Dialogue.** Short, characterful lines in about half the shots.
- **Lighting.** Motivated per shot, from real sources.
- **Lens.** Vary it per shot: close-ups, low angles, over-the-shoulder with a foreground, inserts, aerials.
- **Structure.** The title by about 5 s and a 0.2-0.5 s montage on the drop.
- **Grade.** Deep blacks and rich colour, not milky haze.

`fp scenes` warns when a plan is too thin. Treat its PACING and WORLD warnings as errors unless the user
deliberately wants a small film. To keep credits sane, use 4-6 s clips for montage vignettes, and mark one-shot characters `"role": "vignette"` in
characters.json. They get a single character card (full body plus two faces) instead of three sheets.

**Tool runner.** Every command below is `${CLAUDE_SKILL_DIR}/../../fp <command> <film> ...` (agents and slash
commands use the same file as `${CLAUDE_PLUGIN_ROOT}/fp`). Run `fp --help` for the full list. Films are created
in `./films/<film>/` of the user's current folder (override with the `FILM_PROJECTS` env var). The first run
builds a Python 3.12 environment in `~/.ai-film-pipeline/venv` automatically (needs `uv` or Python 3.10-3.12,
plus `ffmpeg`).

## 0. Before the first film: check the setup (do this, don't ask the user to)
1. Run `${CLAUDE_SKILL_DIR}/../../fp --help` (this also installs the Python deps on first run, ~1 minute).
2. `ffmpeg -version` must work. `blender --version` (4.2+) is needed only for previz and titles.
3. ImagineArt connector: look for its tools (`generate_image`, `generate_video`, `generate_music`,
   `fetch_status`, `get_balance`, `list_assets`; use ToolSearch if they are deferred). If they are missing, tell
   the user to connect **ImagineArt** under claude.ai Settings -> Connectors (same account as Claude Code), then
   restart the session. Without it, the pipeline still works in "prompts only" mode (the human generates
   on imagineart.ai and drops the files in).
4. On the first ImagineArt call, if it asks for an organization, call `select_organization` and ask the user
   which workspace's credits to use. Then pass that org id on every call (never show it to the user).
5. Want a no-cost rehearsal? `fp demo` builds `films/demo` from synthetic clips, so every stage can run.

## Standing rules (step 01, never break these)
1. **Generation mode is the human's choice.** Default: Claude never generates video. A video task ends at
   upload folders, the full prompt and the HTML copy page (`fp upload`), and the human runs the generations.
   Only if the human explicitly opts in ("you generate the clips") does Claude call Seedance itself. Record
   that opt-in in `00_brief/brief.md`. Images (sheets, plates) and music may be generated through the
   connector after the scene board is signed off.
2. **Measure cost before spending.** In generation mode, generate ONE clip first, read `get_balance` before
   and after, tell the user the per-clip cost (Seedance 2.5, 1080p, 10 s was about 2,700 credits in late
   2026), and scale only within what they approved. Prefer one take per shot, then retake only the rejects.
3. Never crop or resize a reference. Register every generated asset with `fp asset` (it copies byte for byte).
4. Reprint the full prompt on every change. Never send a diff of a prompt.
5. Ask before rendering. Edit decisions are multiple-choice questions (AskUserQuestion) with one
   recommended option. If the user explicitly says to go straight to the finished film, you may skip a
   gate, but say which gate you skipped.
6. Every image and video prompt begins with the film's style LOOK block (`fp look --film <film>`), verbatim,
   and every video prompt names its own motivated LIGHTING. Never fall back to a generic hazy look.
7. Everything is original: no real people, no existing game, film or brand characters, logos or text.
   Reference trailers are studied for pacing only and never used as generation inputs.
8. **Show, don't just list paths.** Send boards, sheets, grids and the finished film to the user in chat
   (send-file tool if available), and say plainly what was measured and what nobody watched or heard.

## Phases, owners, gates
Agents are namespaced `ai-film-pipeline:<agent>`; commands are `/ai-film-pipeline:<command>`.

| Phase | Steps | Agent | Command | Gate (human) |
|---|---|---|---|---|
| Brief | 01 | you | film-new | brief approved, generation mode chosen |
| Research | 02 | researcher | film-research | none |
| Scenes | 03 | scene-designer | film-scenes | **scene board sign-off before any credits** |
| Art | 04-06 | art-department | film-art | sheets and plates approved |
| Previz | 07-08 | previz-director | film-previz | previz approved per shot |
| Prompts/takes | 09-11 | prompt-writer | film-prompts | takes generated (by human or opted-in Claude) |
| Fix loop | 12 | continuity-critic | film-fix | none |
| Dailies | 13 | dailies | film-dailies | none |
| Cut | 14-17 | editor + web editor | film-cut | **order board sign-off** each round |
| Finish | 18-21 | finishing | film-finish | grade, titles and subs approved |
| Sound | 22-23 | sound | film-finish | mix approved |
| Master | 24 | mastering | film-master | final approved, then the human posts |

Hand-off contract: every agent writes its files into the film folder and ends with a `HANDOFF:` block
(files, open questions, what the next agent must check). After each hand-off, run `continuity-critic` on it.
On FAIL, send the findings back to the producing agent (max 3 loops), then ask the human.

## Film folder (stable scene IDs like N01, G04, E08 key everything)
```
films/<film>/
  00_brief/brief.md      01_refs/ (trailers to study, the song)     02_research/
  03_scenes/scenes.json + characters.json + locations.json + vehicles.json -> scenes.md, scenes_board.png
  04_sheets/<CHAR>/<OUTFIT>/portrait_4x5.png, sheet2_face.png, sheet1_full.png     05_plates/<LOC>_<TOD>.png
  06_previz/<ID>/          07_upload/<ID>/prompt.json, prompt.txt, upload/ + 07_upload/index.html
  08_takes/<ID>/<ID>_t1.mp4   (reject = rename to <ID>_t1x.mp4; every tool skips *x)
  09_edit/ transcripts.json, dailies.md, beats.json, plan.json, board.json, requests/, cuts/
  10_finish/ (grade.json, titles/, titles.json, subs/)   11_sound/   12_master/<film>_final.mp4
  assets.json   (local file -> ImagineArt asset URL; Seedance needs these URLs as references)
```

## Key commands
| Step | Command |
|---|---|
| 01 | `fp styles`, `fp new <film> --style <id> --duration <s>` (or `fp style <film> <id>`), `fp status <film>` |
| 03 | `fp scenes <film>`: validate the rules, write the table and the board image; `fp estimate <film>`: credit estimate before anything is generated |
| 05-06 | `fp sheet-prompts <film>` and `fp plate-prompts <film>` |
| assets | `fp asset <film> <path-in-film> <asset-id-or-url>`: download and register |
| 07-08 | `fp previz-brief <film> <ID>`, then `blender -b -P <plugin>/blender/previz.py -- <shot.json>` |
| 09-11 | `fp prompt <film> <ID> [--build]`, `fp payload <film> <IDs...>` (generation mode), `fp upload <film>` (human mode) |
| QA | `fp grid <film> <video> --step 0.5`: frame grid to Read and judge |
| 13 | `fp transcribe <film>` and `fp dailies <film>` |
| 14-17 | `fp beats <film> <song>`, `fp board-init`, `fp orderboard`, `fp editor <film>` (http://localhost:8765), `fp board-diff`, `fp render-cut` |
| 18 | `fp master` then `fp lookmatch <film>` (measure) and `fp lookmatch <film> --apply` (closed-loop grade fit on sampled frames; `--ref <film.mp4>` to match a reference), then re-master |
| 18-21 | `fp grade-preview <film> <clip>`, `blender -b -P <plugin>/blender/title.py -- --text WORD --font <otf> --out <path>`, `fp subs <film>` |
| 22-23 | `fp stems <film>`, `fp echo <film>`, `fp mix <film>` |
| 24 | `fp master <film>`, `fp verify <film> 12_master/<film>_final.mp4 --final`, `fp package <film>` |

## ImagineArt connector: what worked
- **Images.** `nano-banana-pro`, 16:9 (portraits 4:5), resolution 2K. `generate_image_batch` takes up to 8
  prompts, but they share one `image_url` list, so batch the plates and do per-character sheets one call each.
- **Video.** `seedance-2.5`, aspect "16:9", duration "10", resolution "1080p". `image_url` lists the asset URLs
  in exact prompt order: plates, then per person the face sheet and the full sheet. A single image means
  image-to-video (it animates that still), so give 2+ references for real reference-to-video. Local
  previz files need an ImagineArt URL first, and the upload tool only takes base64, so large previz videos are
  usually impractical. Use the text-driven "prompt without previz" path (step 09) when you can't upload.
- **Music.** `generate_music` with variation "instrumental". Describe the song form with timestamps (cold open,
  drop, breakdown, final hit) so the edit has landmarks.
- **Reliability.** A "server isn't responding" error does not mean the job failed. Before resubmitting,
  `list_assets` (service "video") and look for new clips. Prefer one `generate_video` per shot over big batches.
- **Moderation.** A 773x773 "Image generation failed" placeholder means the moderator blocked the prompt.
  `fp asset` refuses it. Reword the cause (for example swimwear words) instead of retrying the same text.
- `get_balance` can lag or jump (top-ups land mid-run), so measure cost around a single isolated job.

## Gotchas the pipeline already handles (don't undo them)
- Whisper hallucinates words on noise: transcription uses VAD and drops no-speech segments. When verifying
  a final mix, `verify` transcribes without VAD so speech under music is still heard.
- Whisper mishears homophones ("knight" for "night") and drops question marks. Before `fp subs`, correct
  `09_edit/transcripts.json` against the scripted lines in `scenes.json`.
- librosa finds no beats in quiet intros. Place drops by the RMS energy rise and extend the tempo grid back.
- Generated songs are far louder than AI-clip dialogue: `fp mix` gain-stages speech to -20 LUFS, puts the
  music 10 dB under dialogue, then limits to -14 LUFS / -1 dBTP. If verify hears no speech, fix the mix.
- Flawed takes: trim to the clean section in the edit before paying for a retake (log why in the brief).
- Grade by measurement, not by eye alone: a one-shot formula overshoots because halation, curves and saturation
  interact. `fp lookmatch --apply` searches the real grade chain on sampled frames and refuses to apply twice
  without a re-master in between.
- The style post only enforces the grid, palette and stepping. The style itself must come from generation, so
  reject sheets, plates and takes that drift out of the style rather than hoping post will fix them.
