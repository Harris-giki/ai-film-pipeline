---
description: Start a new film project (step 01 brief + standing rules)
argument-hint: <film-name> [one-line idea]
---
Create the project with `${CLAUDE_PLUGIN_ROOT}/fp new $1`. Then interview me briefly (AskUserQuestion,
max 4 questions) for: genre/tone, length + clip count, the song, and reference trailers I will drop in
`films/$1/01_refs/`. Write `films/$1/00_brief/brief.md` with GOAL, STACK and the STANDING RULES
from the ai-film-pipeline skill copied verbatim. Show me the brief and wait for approval. Idea: $ARGUMENTS
