"""Build projects/demo with synthetic takes (test pattern + macOS `say` dialogue) and a click-track song,
so every pipeline stage can be exercised without spending generation credits.

  filmfp demo   (or: python tools/make_demo.py)
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.__main__ import main as cli  # noqa: E402
from pipeline.common import PROJECTS  # noqa: E402

P = PROJECTS / "demo"


def sh(*a):
    subprocess.run([str(x) for x in a], check=True)


def ff(*a):
    sh("ffmpeg", "-y", "-loglevel", "error", *a)


if P.exists():
    shutil.rmtree(P)
try:
    cli(["new", "demo"])
except SystemExit:
    pass

characters = {
    "MIRA": {"height": 1.68, "build": "slim", "build_class": "slim", "hair": "long dark ponytail", "hair_shape": "ponytail",
             "face": "sharp cheekbones, freckles", "base_outfit": "street",
             "outfits": {"street": "black bomber jacket, white tee, grey cargo trousers, white trainers",
                         "beach": "orange swim top, denim shorts, sandals, round sunglasses"}},
    "DEV": {"height": 1.82, "build": "athletic", "build_class": "athletic", "hair": "short fade", "hair_shape": "short",
            "face": "stubble, scar on chin", "base_outfit": "default",
            "outfits": {"default": "red football jersey number 19, black jeans, boots",
                        "suit": "navy suit, open collar white shirt, brown loafers"}},
    "OTTO": {"height": 1.74, "build": "heavy", "build_class": "heavy", "hair": "bald", "hair_shape": "bald",
             "face": "thick beard", "base_outfit": "default",
             "outfits": {"default": "hawaiian shirt, khaki shorts, flip flops"}},
}
locations = {
    "MARINA": {"desc": "sunlit marina boardwalk with palm trees and yachts", "camera_height_m": 1.6, "tods": ["day", "night"]},
    "HIGHWAY": {"desc": "coastal highway at dusk lined with lamp posts", "camera_height_m": 4.0, "tods": ["dusk"]},
}
scenes = [
    {"id": "N01", "kind": "dialogue", "cast": ["MIRA", "DEV"], "speaking": ["MIRA", "DEV"],
     "outfit": {"MIRA": "street", "DEV": "default"}, "location": "MARINA", "tod": "day",
     "action": "Mira hands Dev a car key", "lines": [{"who": "MIRA", "text": "You drive. I talk."},
                                                      {"who": "DEV", "text": "That never ends well."}],
     "camera": "slow push in, two-shot", "duration": 10, "previz": True},
    {"id": "G02", "kind": "gameplay", "cast": ["OTTO"], "speaking": [], "outfit": {"OTTO": "default"},
     "location": "HIGHWAY", "tod": "dusk", "action": "a car speeds past lamp posts", "lines": [],
     "camera": "chase cam behind car", "duration": 10, "previz": False},
    {"id": "E03", "kind": "emote", "cast": ["MIRA", "OTTO"], "speaking": [], "outfit": {"MIRA": "beach", "OTTO": "default"},
     "location": "MARINA", "tod": "night", "action": "Otto raises a glass", "lines": [], "camera": "low angle orbit",
     "duration": 10, "previz": False, "accessory_change": "OTTO gold chain"},
    {"id": "N04", "kind": "dialogue", "cast": ["DEV"], "speaking": ["DEV"], "outfit": {"DEV": "suit"},
     "location": "MARINA", "tod": "night", "action": "Dev adjusts his cuffs", "lines": [{"who": "DEV", "text": "Tonight, we get paid."}],
     "camera": "static medium close", "duration": 10, "previz": False},
]
d = P / "03_scenes"
for n, v in (("characters.json", characters), ("locations.json", locations), ("scenes.json", scenes)):
    (d / n).write_text(json.dumps(v, indent=2))

# synthetic takes: coloured test pattern + spoken lines at known times + background noise
colors = {"N01": "0x1f5f8b", "G02": "0x8b5f1f", "E03": "0x5f1f8b", "N04": "0x1f8b5f"}
tmp = P / "_tmp"
tmp.mkdir()
for s in scenes:
    for take in (1, 2):
        out = P / "08_takes" / s["id"] / f"{s['id']}_t{take}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        text = "  ".join(l["text"] for l in s["lines"])
        speech = tmp / f"{s['id']}_{take}.aiff"
        inputs = ["-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=24:d=10,drawbox=c={colors[s['id']]}@0.5:t=fill,"
                  f"drawtext=text='{s['id']} take {take}':fontsize=64:fontcolor=white:x=40:y=40",
                  "-f", "lavfi", "-i", "anoisesrc=d=10:c=pink:a=0.02:r=48000"]
        if text:
            sh("say", "-v", "Samantha" if take == 1 else "Daniel", "-o", speech, text)
            inputs += ["-i", speech]
            fc = "[2:a]adelay=1500:all=1,aresample=48000,apad[sp];[1:a][sp]amix=inputs=2:normalize=0,atrim=0:10[a]"
        else:
            fc = "[1:a]anull[a]"
        ff(*inputs, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-t", "10", out)
# mark one reject (step 11 naming rule)
(P / "08_takes" / "G02" / "G02_t2.mp4").rename(P / "08_takes" / "G02" / "G02_t2x.mp4")

# a 120 BPM song with a sung-ish spoken lyric so beats + lyric landmarks exist
song = P / "01_refs" / "song.wav"
click = tmp / "click.wav"
ff("-f", "lavfi", "-i", "sine=f=1000:d=0.04:r=48000", "-af", "apad=whole_dur=0.5", click)
ff("-stream_loop", "59", "-i", click, "-t", "30", tmp / "beat.wav")
sh("say", "-v", "Samantha", "-o", tmp / "lyric.aiff", "Midnight run. We never stop. Midnight run.")
ff("-i", tmp / "beat.wav", "-f", "lavfi", "-i", "sine=f=110:d=30:r=48000", "-i", tmp / "lyric.aiff",
   "-filter_complex", "[1:a]volume=0.15[bass];[2:a]adelay=2000:all=1,aresample=48000[ly];"
   "[0:a][bass][ly]amix=inputs=3:normalize=0,atrim=0:30[a]", "-map", "[a]", song)
(P / "09_edit" / "_song_path.txt").write_text(str(song))
shutil.rmtree(tmp)
print(f"demo project ready: {P}")
