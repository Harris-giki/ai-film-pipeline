# Working on the ai-film-pipeline plugin (contributor notes)

This repo IS the Claude Code plugin (`.claude-plugin/plugin.json`) and its own marketplace
(`.claude-plugin/marketplace.json`, source `./`). The director playbook that users get is
`skills/ai-film-pipeline/SKILL.md`. Do not put film-making rules here; put them in the skill.

- Load your working copy: `claude --plugin-dir .` and check it with `claude plugin validate .`.
- Path rules:
  - Agents and commands reference bundled files as `${CLAUDE_PLUGIN_ROOT}/...`.
  - SKILL.md references them as `${CLAUDE_SKILL_DIR}/../../...`.
  - Never write state inside the plugin. The installed copy is replaced on every update.
  - Films go to `./films` (or `$FILM_PROJECTS`); the venv goes to `~/.ai-film-pipeline/venv` (or `$FILM_VENV`).
- Python runs only through `./fp`. It sets `PYTHONPATH` to the plugin root and builds the venv when
  `requirements.txt` changes.
- Test changes end to end on the synthetic film: `./fp demo`, then the stages in README order.
- Never commit films, renders, generated media, asset URLs or ImagineArt org ids (`.gitignore` covers them).
- Release: bump `version` in `.claude-plugin/plugin.json`, then commit and push to `Harris-giki/ai-film-pipeline`.
  Without a version bump, installed users do not receive the update.
- When a real production teaches a new lesson, add it to the skill's "what worked" and "gotchas" sections
  and to the owning agent, and encode it in the tool if possible (that's how `fp asset`, the moderation
  placeholder check, mix gain staging and the true-peak limiter came about).
