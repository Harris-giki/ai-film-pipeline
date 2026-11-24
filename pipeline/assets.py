"""ImagineArt asset registry: local file <-> asset URL.

Seedance reference-to-video only accepts ImagineArt asset URLs (from a generation or an upload),
never local files. Every image/video generated through the connector is downloaded byte-for-byte
into the film folder AND registered in <film>/assets.json, so prompts can be sent with the right URLs.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .common import die, load_json, save_json

ASSET_BASE = "https://asset.imagine.art/processed/"


def registry(proj: Path) -> dict:
    return load_json(proj / "assets.json", {})


def add(proj: Path, rel: str, ref: str) -> int:
    """Download an asset (id or URL) to <film>/<rel> and register it. Refuses moderation placeholders."""
    url = ref if ref.startswith("http") else ASSET_BASE + ref
    dst = proj / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-sfL", url, "-o", str(dst)])
    if r.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        die(f"download failed (not ready yet?): {url}")
    if dst.suffix.lower() == ".png":
        from PIL import Image
        if Image.open(dst).size == (773, 773):  # ImagineArt "generation failed / moderator" placeholder
            dst.unlink()
            die("this is the ImagineArt moderation placeholder, not an image. Reword the prompt (fix the cause).")
    reg = registry(proj)
    reg[rel] = url
    save_json(proj / "assets.json", reg)
    print(f"{rel} <- {url}")
    return 0


def payload(proj: Path, ids: list[str]) -> int:
    """Print the Seedance payload per shot: built prompt text + reference URLs in upload order."""
    from .prompts import cmd as prompt_cmd
    reg = registry(proj)
    out = []
    for sid in ids:
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = prompt_cmd(proj, sid, build=True, lint_only=False)
        if rc != 0:
            print(buf.getvalue())
            die(f"{sid}: prompt lint failed")
        p = load_json(proj / "07_upload" / sid / "prompt.json")
        urls = []
        for ref in p["references"]:
            rel = str(Path(ref["file"]).relative_to(proj))
            if rel not in reg:
                die(f"{sid}: no asset URL registered for {rel} (run: fp asset <film> {rel} <asset-id>)")
            urls.append(reg[rel])
        out.append({"id": sid, "image_url": urls,
                    "prompt": (proj / "07_upload" / sid / "prompt.txt").read_text().strip()})
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0
