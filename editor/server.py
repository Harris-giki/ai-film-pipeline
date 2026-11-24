"""Step 16 — local editor server: range requests, 640x360 proxies, waveforms, save + send to Claude.

It is a communicator, not an NLE: the human moves things, Claude reads exactly what changed.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from pipeline.common import duration, has_audio, load_json, save_json, takes

STATIC = Path(__file__).parent / "static"
PEAKS_PER_SEC = 50


def make_proxy(src: Path, dst: Path) -> None:
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    print(f"proxy {src.name}", flush=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf",
                    "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,fps=24",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-g", "6", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(dst)], check=True)


def make_peaks(src: Path, dst: Path) -> list[float]:
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return json.loads(dst.read_text())
    import numpy as np
    if not has_audio(src):
        peaks = []
    else:
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "8000",
                              "-f", "f32le", "-"], capture_output=True).stdout
        x = np.abs(np.frombuffer(raw, dtype=np.float32))
        hop = 8000 // PEAKS_PER_SEC
        n = len(x) // hop
        peaks = [round(float(v), 3) for v in x[: n * hop].reshape(n, hop).max(axis=1)] if n else []
    dst.write_text(json.dumps(peaks))
    return peaks


def build_index(proj: Path) -> dict:
    prox = proj / "09_edit" / "proxies"
    prox.mkdir(parents=True, exist_ok=True)
    tr = load_json(proj / "09_edit" / "transcripts.json", {})
    clips = []
    for f in takes(proj):
        p = prox / f"{f.stem}.mp4"
        make_proxy(f, p)
        clips.append({"clip": f.stem, "folder": f.parent.name, "duration": round(duration(f), 3),
                      "url": f"/media/{f.stem}.mp4", "peaks": make_peaks(f, prox / f"{f.stem}.peaks.json"),
                      "lines": tr.get(f.stem, {}).get("lines", [])})
    return {"film": proj.name, "fps": 24, "peaks_per_sec": PEAKS_PER_SEC, "clips": clips}


def serve(proj: Path, port: int = 8765) -> int:
    index = build_index(proj)
    board_file = proj / "09_edit" / "board.json"
    req_dir = proj / "09_edit" / "requests"
    req_dir.mkdir(parents=True, exist_ok=True)

    class H(SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if "/media/" not in (args[0] if args else ""):
                super().log_message(fmt, *args)

        def _json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path == "/api/project":
                return self._json({**index, "board": load_json(board_file, {"fps": 24, "version": 1, "items": []})})
            if path.startswith("/media/"):
                name = Path(path).name
                f = proj / "09_edit" / "proxies" / name
                if not f.exists() or not re.fullmatch(r"[\w.-]+\.mp4", name):
                    return self.send_error(404)
                return self._range(f)
            f = STATIC / ("index.html" if path == "/" else path.lstrip("/"))
            if not f.resolve().is_relative_to(STATIC.resolve()) or not f.exists():
                return self.send_error(404)
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(f))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _range(self, f: Path):
            size = f.stat().st_size
            rng = self.headers.get("Range")
            start, end = 0, size - 1
            if rng:
                m = re.match(r"bytes=(\d*)-(\d*)", rng)
                if m:
                    if m.group(1):
                        start = int(m.group(1))
                        end = int(m.group(2)) if m.group(2) else size - 1
                    else:
                        start = size - int(m.group(2))
                end = min(end, size - 1)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with open(f, "rb") as fh:
                fh.seek(start)
                left = end - start + 1
                try:
                    while left > 0:
                        chunk = fh.read(min(1 << 16, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            path = urlparse(self.path).path
            if path == "/api/save":
                save_json(board_file, body["board"])
                return self._json({"ok": True, "saved": str(board_file)})
            if path == "/api/send":
                save_json(board_file, body["board"])
                ts = time.strftime("%Y%m%d_%H%M%S")
                f = req_dir / f"request_{ts}.json"
                save_json(f, {"sent_at": ts, "message": body.get("message", ""), "board": body["board"]})
                print(f"\n>>> SENT TO CLAUDE: {f}\n    Ask Claude: /film-cut {proj.name}\n", flush=True)
                return self._json({"ok": True, "request": str(f)})
            self.send_error(404)

    print(f"Editor for '{proj.name}': http://localhost:{port}  ({len(index['clips'])} clips)  Ctrl+C to stop")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
    return 0
