#!/bin/sh
# ai-film-pipeline tool runner. Usage: fp <command> <film> [...]   (fp --help)
# Films live in ./films of the folder you run it from (override with FILM_PROJECTS).
# The Python environment lives outside the plugin so plugin updates never wipe it.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="${FILM_VENV:-$HOME/.ai-film-pipeline/venv}"
STAMP="$VENV/.requirements.sha"
WANT="$(shasum "$ROOT/requirements.txt" | cut -d' ' -f1)"
if [ ! -x "$VENV/bin/python" ] || [ "$(cat "$STAMP" 2>/dev/null)" != "$WANT" ]; then
  echo "[ai-film-pipeline] setting up Python environment in $VENV (first run or updated requirements)..." >&2
  "$ROOT/setup.sh" >&2
fi
PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" exec "$VENV/bin/python" -m pipeline "$@"
