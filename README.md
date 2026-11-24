# AI Film Pipeline for Claude Code

Make generative-AI short films, trailers and ads end to end inside Claude Code.

Claude acts as the **director** and runs a crew of 11 specialist agents through a 24-step production
pipeline. Each agent hands its work to the next, a critic agent reviews every hand-off, and you sign off at
every creative gate. Images, video clips and music come from the **ImagineArt** connector (Nano Banana Pro,
Seedance 2.5, ElevenLabs Music). Previz and 3D titles come from **Blender**. Editing, grading, subtitles,
the mix and the master are done by Claude with ffmpeg, faster-whisper and librosa. There's also a local web
editor where you can move clips yourself and send the timeline back to Claude.

```
brief -> research -> scene board [you sign off] -> character sheets + location plates (ImagineArt)
      -> Blender previz -> Seedance prompts -> takes [you or Claude generate] -> critic fix loop
      -> dailies (whisper) -> beat-locked cut -> order board [you sign off] <-> web editor round-trips
      -> grade -> titles -> subtitles -> 3-layer sound -> one-pass master -> machine verification
```

It was built and proven by making **SUNSHINE**, a 60-second original game-trailer-style short: 16 shots, 3
characters, a generated score, a beat-locked montage, -14 LUFS, and every line verified in the final mix.

---

## Install (2 minutes)

In Claude Code:

```
/plugin marketplace add Harris-giki/ai-film-pipeline
/plugin install ai-film-pipeline@ai-film-pipeline
```

Or from a terminal:

```bash
claude plugin marketplace add Harris-giki/ai-film-pipeline
```

```bash
claude plugin install ai-film-pipeline@ai-film-pipeline
```

Then make sure these are available:

| Requirement | Why | How |
|---|---|---|
| **ImagineArt connector** | Character sheets, plates, video clips and music | claude.ai -> Settings -> Connectors -> ImagineArt (use the same account you sign in to Claude Code with), then restart Claude Code |
| **ffmpeg** | All editing, grading and audio | `brew install ffmpeg` (Linux: `apt install ffmpeg`) |
| **uv** (or Python 3.10-3.12) | Python environment for whisper and librosa, built automatically on first run in `~/.ai-film-pipeline/venv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Blender 4.2+** (optional) | Grey previz and 3D title renders | `brew install --cask blender` |

You don't need to configure anything else. The skill tells Claude how to check all of this the first time
you use it.

## Use it

Open Claude Code in any folder where you want your films to live, and just ask:

> Make me a 30-second trailer for an original heist comedy set in a sunny coastal city.

Claude loads the `ai-film-pipeline` skill, checks the setup, writes the brief and asks a few questions (tone,
length, song, **who generates the clips: you or Claude**). Then it walks the phases. Each phase also has a
slash command:

| Command | Steps |
|---|---|
| `/ai-film-pipeline:film-new <film> <idea>` | 01 brief |
| `/ai-film-pipeline:film-research <film>` | 02 study reference trailers (put them in `films/<film>/01_refs/`) |
| `/ai-film-pipeline:film-scenes <film>` | 03 scene board, your sign-off |
| `/ai-film-pipeline:film-art <film>` | 04-06 look, character sheets, plates |
| `/ai-film-pipeline:film-previz <film>` | 07-08 Blender previz |
| `/ai-film-pipeline:film-prompts <film>` | 09-11 Seedance prompts, upload page or generation |
| `/ai-film-pipeline:film-fix <film> <take> <problem>` | 12 diagnose a broken take |
| `/ai-film-pipeline:film-dailies <film>` | 13 transcribe and pick takes |
| `/ai-film-pipeline:film-cut <film> <song>` | 14-17 cut on the music, web editor round-trips |
| `/ai-film-pipeline:film-finish <film>` | 18-23 grade, titles, subtitles, sound |
| `/ai-film-pipeline:film-master <film>` | 24 master, verify, package |
| `/ai-film-pipeline:film-status <film>` | where a film stands |

Films are written to `./films/<film>/` in your current folder. Plugin updates never touch them.

**Try it for free first.** Ask Claude to "run the film pipeline demo", or run the `fp demo` tool. It builds a
synthetic film so every stage (cut, editor, grade, subtitles, mix, master) can run without spending credits.

## Two ways to generate clips

- **You generate (default, as in the original method).** Claude prepares numbered upload folders, full
  prompts and an HTML page with copy buttons. You run Seedance on ImagineArt and drop the takes into
  `films/<film>/08_takes/<ID>/<ID>_t1.mp4`.
- **Claude generates (opt-in).** Say "you generate the clips". Claude makes clip 1 alone, measures its credit
  cost, tells you, and only then makes the rest. It makes one take per shot and retakes only what the critic
  rejects. For reference, Seedance 2.5 at 1080p for 10 s was about 2,700 credits per clip in late 2026, and
  a 60 s, 16-shot film used about 55k credits including all stills and music.

## What's inside

```
.claude-plugin/      plugin.json + marketplace.json
skills/ai-film-pipeline/SKILL.md   the director's playbook Claude loads (rules, phases, commands, gotchas)
agents/              researcher, scene-designer, art-department, previz-director, prompt-writer,
                     continuity-critic, dailies, editor, finishing, sound, mastering
commands/            the /ai-film-pipeline:film-* slash commands
pipeline/            the Python toolchain behind `fp` (scenes, prompts, assets, dailies, beats, board,
                     render, grade, titles, subtitles, mix, master, verify)
editor/              local web editor (Python server with range requests, single-page timeline UI)
blender/             previz.py (shot.json -> grey Workbench previz, refuses rule-breaking shots), title.py
docs/                PIPELINE_24_STEPS.md (the method, step by step) and FIX_TABLE.md
fp, setup.sh         tool runner; builds ~/.ai-film-pipeline/venv on first run
tools/make_demo.py   synthetic demo film
```

## Known limits
- **Previz as a video reference.** It needs the previz uploaded to ImagineArt, and the connector's upload
  only takes base64, so large videos are impractical. Shots fall back to detailed text prompts (step 09).
- **Custom title font.** The method generates its own font in code. `title.py` uses any `.otf` or `.ttf` you
  give it.
- **Tracked titles.** Compositing is built (overlay frame 0 = clip frame 0, matched head trims). Camera
  tracking the overlay is still manual in Blender.
- **Dialogue stem.** It's the clip audio gated to the spoken words, not true source separation.
- **Mac-first.** Tested on macOS with Blender 5.3. `tools/make_demo.py` uses the macOS `say` command.

## Developing / releasing
Work on a clone with `claude --plugin-dir .` to load your local copy. Check the plugin with
`claude plugin validate .`. **Bump `version` in `.claude-plugin/plugin.json` for every release**, because
installed users only get updates when the version changes. Contributor notes are in `CLAUDE.md`.

## License
MIT. See [LICENSE](LICENSE).
