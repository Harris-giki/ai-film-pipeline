"""Step 04: lock the look. The film's style pack supplies the LOOK block, used verbatim at the start of
every image and video prompt (see pipeline/style.py and styles/*.json)."""
from __future__ import annotations

from pathlib import Path

# The original playbook's single look. Kept for reference only: its blanket "gentle haze, volumetric
# light rays ... heavy grain" applied to every shot is what made SUNSHINE milky and samey. Styles replace it.
LEGACY_LOOK = (
    "A cinematic scene captured on ARRI ALEXA 35, renowned for its rich colour science, soft highlight "
    "roll-off, and deep dynamic range. Soft highlights bloom gently without clipping, shadows retain "
    "texture and depth. Film-like latitude with realistic exposure falloff, smooth tonal transitions, "
    "and refined colour fidelity. Shot with a cinematic lighting setup emphasising natural light "
    "behaviour, controlled highlights, and realistic shadow gradation. Atmospheric depth with gentle "
    "haze, volumetric light rays, and cinematic mood. Raw indie aesthetic. Heavy organic film grain. "
    "Unpolished realism."
)


def with_look(look: str, shot_line: str, body: str = "") -> str:
    """LOOK verbatim + one shot-specific line tying the grade to the plate (+ optional body)."""
    parts = [look, shot_line.strip()]
    if body.strip():
        parts.append(body.strip())
    return "\n\n".join(parts)


def check_file(path: Path, look: str) -> bool:
    text = path.read_text()
    ok = look in text
    print(f"{'OK  ' if ok else 'FAIL'} {path}" + ("" if ok else "  (style LOOK block missing or paraphrased)"))
    return ok
