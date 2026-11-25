---
description: Start a new film (step 01) - choose the visual style first, then the brief
argument-hint: <film-name> [one-line idea]
---
1. Run `${CLAUDE_PLUGIN_ROOT}/fp styles` and ask me with AskUserQuestion which VISUAL STYLE the film should be,
   each option with its one-line summary: Realistic cinematic, Claymation, Pixel art, Paper cutout,
   Stylized 3D, Anime. "Other" means a custom style: write it from `${CLAUDE_PLUGIN_ROOT}/styles/_template.json`
   with me, save it to `films/$1/00_brief/custom_style.json` and use `--custom`.
2. In the same question set, ask: length in seconds, genre and tone, the song (generate one or bring one),
   and who generates the video clips (me by hand, or you through ImagineArt after a cost check).
3. Create the film: `${CLAUDE_PLUGIN_ROOT}/fp new $1 --style <id> --duration <seconds>`. It freezes the style
   pack into the film and prints the coverage targets (setups, shot length, dialogue share, title timing).
4. Write `films/$1/00_brief/brief.md`: GOAL, STYLE (label, and why it suits the idea), targets, STACK, and the
   STANDING RULES from the ai-film-pipeline skill copied verbatim, including my generation-mode choice.
5. Show me the brief and wait for approval. Every later stage follows this style. Idea: $ARGUMENTS
