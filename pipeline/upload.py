"""Step 09/11 — numbered upload folders (byte-for-byte copies) + an HTML copy page."""
from __future__ import annotations

import html
import shutil
from pathlib import Path

from .common import load_json


def build(proj: Path) -> int:
    root = proj / "07_upload"
    cards = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        pj, pt = d / "prompt.json", d / "prompt.txt"
        if not (pj.exists() and pt.exists()):
            print(f"skip {d.name}: needs prompt.json + linted prompt.txt (pipeline prompt --build)")
            continue
        p = load_json(pj)
        files_dir = d / "upload"
        if files_dir.exists():
            shutil.rmtree(files_dir)
        files_dir.mkdir()
        rows = []
        for i, r in enumerate(p["references"], 1):
            src = Path(r["file"])
            if not src.exists():
                print(f"  {d.name}: MISSING {src}")
                continue
            dst = files_dir / f"{i:02d}_{r['tag'].lstrip('@')}_{src.name}"
            shutil.copyfile(src, dst)  # byte-for-byte: never crop, resize or recompress a reference
            rows.append(f"<li><code>{html.escape(dst.name)}</code> &mdash; {html.escape(r['tag'])}: {html.escape(r['role'])}</li>")
        text = pt.read_text()
        cards.append(f"""
<section class="card">
  <h2>{html.escape(d.name)} <span>{'with previz' if p.get('previz') else 'no previz'}</span></h2>
  <p class="path">{html.escape(str(files_dir))}</p>
  <ol>{''.join(rows)}</ol>
  <button onclick="copyText('p-{d.name}', this)">Copy prompt</button>
  <pre id="p-{d.name}">{html.escape(text)}</pre>
  <p class="hint">Seedance 2.5 reference-to-video, 10 s, 16:9. Upload files in the numbered order. 2-4 takes.
  Save as <code>08_takes/{d.name}/{d.name}_t1.mp4</code>; rename rejects to <code>{d.name}_t1x.mp4</code>.</p>
</section>""")
        print(f"{d.name}: {len(rows)} files")
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Upload board — {html.escape(proj.name)}</title>
<style>
body{{font:14px -apple-system,Helvetica,sans-serif;background:#111;color:#eee;margin:0;padding:24px}}
h1{{font-size:22px}} .card{{background:#1c1c1f;border-radius:10px;padding:16px 20px;margin:0 0 18px}}
h2{{margin:0 0 6px}} h2 span{{font-size:12px;color:#9a9;font-weight:400;margin-left:8px}}
.path{{color:#888;font-size:12px}} pre{{white-space:pre-wrap;background:#0b0b0c;padding:12px;border-radius:8px;max-height:340px;overflow:auto}}
button{{background:#ff5c8a;border:0;color:#fff;padding:8px 14px;border-radius:6px;cursor:pointer;font-weight:600}}
.hint{{color:#aaa;font-size:12px}} code{{color:#ffd27a}}
</style></head><body>
<h1>{html.escape(proj.name)} — upload folders &amp; prompts</h1>
<p>Claude never runs video generation. You run each shot on ImagineArt, then drop takes into <code>08_takes/</code>.</p>
{''.join(cards) or '<p>No shots ready yet.</p>'}
<script>
function copyText(id, b){{navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>{{b.textContent='Copied';setTimeout(()=>b.textContent='Copy prompt',1200)}})}}
</script></body></html>"""
    (root / "index.html").write_text(page)
    print(f"wrote {root/'index.html'}")
    return 0
