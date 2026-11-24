"""CLI: fp <command> <film> ...   Films live in ./films (or $FILM_PROJECTS)."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .common import FOLDERS, PROJECTS, ROOT, project, takes


def cmd_new(a):
    p = PROJECTS / a.film
    for f in FOLDERS:
        (p / f).mkdir(parents=True, exist_ok=True)
    brief = p / "00_brief" / "brief.md"
    if not brief.exists():
        brief.write_text(f"# {a.film} — brief\n\nGOAL: \n\nSTACK: Claude Code (director + editor), ImagineArt MCP "
                         "(Nano Banana Pro stills 4K 16:9, Seedance 2.5 reference-to-video), Blender 5 previz.\n\n"
                         "STANDING RULES: see CLAUDE.md (copied verbatim by /film-new)\n")
    for name, default in (("scenes.json", "[]"), ("characters.json", "{}"), ("locations.json", "{}")):
        f = p / "03_scenes" / name
        if not f.exists():
            f.write_text(default + "\n")
    print(f"created {p}")
    return 0


def cmd_status(a):
    p = project(a.film)
    def n(glob):
        return len(list(p.glob(glob)))
    checks = [
        ("01 brief", (p / "00_brief/brief.md").exists()),
        ("02 research docs", (p / "02_research/pacing.md").exists()),
        ("03 scenes", n("03_scenes/scenes_board.png") > 0),
        ("05 character sheets", n("04_sheets/**/sheet1_full.png")),
        ("06 plates", n("05_plates/*.png")),
        ("08 previz renders", n("06_previz/*/previz.mp4")),
        ("09 prompts built", n("07_upload/*/prompt.txt")),
        ("11 takes (non-reject)", len(takes(p))),
        ("13 transcripts", (p / "09_edit/transcripts.json").exists()),
        ("14 beats", (p / "09_edit/beats.json").exists()),
        ("17 board", (p / "09_edit/board.json").exists()),
        ("17 cuts", n("09_edit/cuts/cut_v*.mov")),
        ("17 pending editor requests", n("09_edit/requests/request_*.json")),
        ("21 subtitles", (p / "10_finish/subs/subs.srt").exists()),
        ("22 mix", (p / "11_sound/mix.wav").exists()),
        ("24 master", n("12_master/*_final.mp4")),
    ]
    for k, v in checks:
        print(f"{k:32s} {v}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pipeline", description=__doc__)
    sp = ap.add_subparsers(dest="cmd", required=True)
    def add(name, fn, *args, help=None):
        s = sp.add_parser(name, help=help)
        s.add_argument("film")
        for x in args:
            s.add_argument(*x[0], **x[1])
        s.set_defaults(fn=fn)
        return s

    add("new", cmd_new, help="01 create project folders")
    add("status", cmd_status, help="where the film is in the 24 steps")
    add("refs", lambda a: (__import__("pipeline.refs", fromlist=["x"]).study(project(a.film)), 0)[1], help="02 tile + measure refs")
    add("scenes", lambda a: __import__("pipeline.scenes", fromlist=["x"]).cmd(project(a.film)), help="03 validate, table, board")
    add("sheet-prompts", lambda a: __import__("pipeline.art", fromlist=["x"]).write_sheet_prompts(project(a.film)), help="05")
    add("plate-prompts", lambda a: __import__("pipeline.art", fromlist=["x"]).write_plate_prompts(project(a.film)), help="06")
    add("previz-brief", lambda a: __import__("pipeline.previz", fromlist=["x"]).write_brief(project(a.film), a.scene),
        (["scene"], {}), help="07 brief + shot.json")
    add("grid", lambda a: (print(__import__("pipeline.refs", fromlist=["x"]).frame_grid(
        project(a.film) / a.video, (project(a.film) / a.video).with_name(Path(a.video).stem + "_grid.jpg"), a.step)), 0)[1],
        (["video"], {}), (["--step"], {"type": float, "default": 0.5}), help="10 frame grid")
    add("prompt", lambda a: __import__("pipeline.prompts", fromlist=["x"]).cmd(project(a.film), a.scene, a.build, a.lint),
        (["scene"], {}), (["--build"], {"action": "store_true"}), (["--lint"], {"action": "store_true"}), help="09/10")
    add("upload", lambda a: __import__("pipeline.upload", fromlist=["x"]).build(project(a.film)), help="09/11 upload folders + HTML")
    add("takes", lambda a: ([print(t.relative_to(project(a.film))) for t in takes(project(a.film))], 0)[1], help="list non-reject takes")
    add("transcribe", lambda a: __import__("pipeline.dailies", fromlist=["x"]).transcribe(project(a.film), a.refs),
        (["--refs"], {"action": "store_true"}), help="13 faster-whisper")
    add("dailies", lambda a: __import__("pipeline.dailies", fromlist=["x"]).table(project(a.film), a.older_penalty),
        (["--older-penalty"], {"type": float, "default": 0.2}), help="13 take table")
    add("beats", lambda a: __import__("pipeline.music", fromlist=["x"]).beats(project(a.film), Path(a.song), not a.no_lyrics),
        (["song"], {}), (["--no-lyrics"], {"action": "store_true"}), help="14 librosa")
    add("board-init", lambda a: __import__("pipeline.board", fromlist=["x"]).init(project(a.film)), help="14 selects -> board")
    add("orderboard", lambda a: __import__("pipeline.board", fromlist=["x"]).orderboard(project(a.film)), help="15")
    add("board-diff", lambda a: __import__("pipeline.board", fromlist=["x"]).diff_cmd(project(a.film)), help="17")
    add("render-cut", lambda a: (__import__("pipeline.board", fromlist=["x"]).render(project(a.film)), 0)[1], help="17")
    add("editor", lambda a: __import__("editor.server", fromlist=["x"]).serve(project(a.film), a.port),
        (["--port"], {"type": int, "default": 8765}), help="16 web editor")
    add("grade-preview", lambda a: __import__("pipeline.finish", fromlist=["x"]).grade_preview(project(a.film), a.clip, a.at),
        (["clip"], {}), (["--at"], {"type": float, "default": 2.0}), help="18")
    add("subs", lambda a: __import__("pipeline.finish", fromlist=["x"]).write_subs(project(a.film)), help="21")
    add("stems", lambda a: __import__("pipeline.sound", fromlist=["x"]).stems(project(a.film)), help="22")
    add("echo", lambda a: __import__("pipeline.sound", fromlist=["x"]).echo(project(a.film), apply=a.apply),
        (["--apply"], {"action": "store_true"}), help="23")
    add("mix", lambda a: __import__("pipeline.sound", fromlist=["x"]).mix(project(a.film), a.clarity),
        (["--clarity"], {"action": "store_true"}), help="22/23")
    add("master", lambda a: (__import__("pipeline.master", fromlist=["x"]).master(project(a.film)), 0)[1], help="24")
    add("package", lambda a: __import__("pipeline.master", fromlist=["x"]).package(project(a.film)), help="24")
    add("verify", lambda a: __import__("pipeline.verify", fromlist=["x"]).verify(project(a.film), project(a.film) / a.file, a.final),
        (["file"], {}), (["--final"], {"action": "store_true"}), help="15/24")
    add("asset", lambda a: __import__("pipeline.assets", fromlist=["x"]).add(project(a.film), a.path, a.ref),
        (["path"], {"help": "path inside the film, e.g. 05_plates/MARINA_night.png"}), (["ref"], {"help": "ImagineArt asset id or URL"}),
        help="download an ImagineArt asset into the film and register its URL")
    add("payload", lambda a: __import__("pipeline.assets", fromlist=["x"]).payload(project(a.film), a.scenes),
        (["scenes"], {"nargs": "+"}), help="11 lint + print Seedance prompt and reference URLs per shot")
    dm = sp.add_parser("demo", help="build a synthetic demo film (no credits) to try every stage")
    dm.set_defaults(fn=lambda a: __import__("runpy").run_path(str(ROOT / "tools" / "make_demo.py"), run_name="__main__") and 0)
    lk = sp.add_parser("look", help="04 print LOOK or --check files")
    lk.add_argument("--check", nargs="*")
    lk.set_defaults(fn=lambda a: (0 if all([__import__("pipeline.look", fromlist=["x"]).check_file(Path(f)) for f in a.check]) else 1)
                    if a.check else (print(__import__("pipeline.look", fromlist=["x"]).LOOK), 0)[1])
    a = ap.parse_args(argv)
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
