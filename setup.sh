#!/bin/sh
# One-time setup (fp runs this automatically). Creates a Python 3.12 environment with the
# pipeline's dependencies and checks the external tools.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="${FILM_VENV:-$HOME/.ai-film-pipeline/venv}"
command -v ffmpeg >/dev/null || { echo "ffmpeg is required: brew install ffmpeg  (Linux: apt install ffmpeg)"; exit 1; }
mkdir -p "$(dirname "$VENV")"
if command -v uv >/dev/null; then
  uv venv --quiet --allow-existing --python 3.12 "$VENV"
  uv pip install --quiet --python "$VENV/bin/python" -r "$ROOT/requirements.txt"
else
  PY="$(command -v python3.12 || command -v python3.11 || command -v python3.10 || true)"
  [ -n "$PY" ] || { echo "Need uv (recommended: curl -LsSf https://astral.sh/uv/install.sh | sh) or Python 3.10-3.12"; exit 1; }
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install --quiet -r "$ROOT/requirements.txt"
fi
shasum "$ROOT/requirements.txt" | cut -d' ' -f1 > "$VENV/.requirements.sha"
command -v blender >/dev/null || echo "NOTE: Blender 4.2+ not on PATH (only needed for previz and titles): brew install --cask blender"
echo "ai-film-pipeline ready ($VENV)"
