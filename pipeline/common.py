"""Shared paths and helpers."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # the installed plugin / repo
# Films live in the user's working folder, never inside the plugin (plugin updates replace it).
PROJECTS = Path(os.environ.get("FILM_PROJECTS", Path.cwd() / "films")).resolve()
FPS = 24
W, H = 1920, 1080

FOLDERS = [
    "00_brief", "01_refs", "02_research", "03_scenes", "04_sheets", "05_plates",
    "06_previz", "07_upload", "08_takes", "09_edit/requests", "09_edit/cuts",
    "09_edit/proxies", "10_finish/titles", "10_finish/subs", "11_sound", "12_master",
]


def die(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def project(name: str) -> Path:
    p = PROJECTS / name
    if not p.exists():
        die(f"no project '{name}' (run: python -m pipeline new {name})")
    return p


def load_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        die(f"missing {path}")
    return json.loads(path.read_text())


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [str(c) for c in cmd]
    return subprocess.run(cmd, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def ffmpeg(*args, quiet=True) -> None:
    base = ["ffmpeg", "-y", "-hide_banner"] + (["-loglevel", "error"] if quiet else [])
    run(base + list(args))


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
               "-show_streams", path], capture=True).stdout
    return json.loads(out)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def has_audio(path: Path) -> bool:
    return any(s["codec_type"] == "audio" for s in probe(path)["streams"])


def is_reject(path: Path) -> bool:
    """Step 11: rejects are marked by suffixing the filename stem with 'x'."""
    return path.stem.endswith("x")


TAKE_RE = re.compile(r"^(?P<id>[A-Za-z]+\d+)_t(?P<n>\d+)$")


def takes(proj: Path, include_rejects: bool = False) -> list[Path]:
    """All takes under 08_takes, newest folder first. Skips *x rejects."""
    out = []
    for f in sorted((proj / "08_takes").rglob("*.mp4")) + sorted((proj / "08_takes").rglob("*.mov")):
        if not include_rejects and is_reject(f):
            continue
        out.append(f)
    return out


def take_id(path: Path) -> str:
    return path.stem


def clip_path(proj: Path, clip: str) -> Path:
    for f in takes(proj, include_rejects=True):
        if f.stem == clip:
            return f
    die(f"clip '{clip}' not found under 08_takes")


def need(tool: str) -> str:
    p = shutil.which(tool)
    if not p:
        die(f"'{tool}' not on PATH")
    return p


def frames(sec: float) -> int:
    return int(round(sec * FPS))


def tc(sec: float) -> str:
    m, s = divmod(max(sec, 0), 60)
    f = int(round((s - int(s)) * FPS))
    return f"{int(m):02d}:{int(s):02d}:{f:02d}"
