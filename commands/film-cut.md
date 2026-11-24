---
description: Steps 14-17 — cut on the music, order board, editor round-trip, render after sign-off
argument-hint: <film> [song path]
---
Invoke `editor` for `$1` (song: $2). If `09_edit/requests/` has a new request from the web editor,
start at the board-diff step. Always ask before rendering. After rendering, invoke
`continuity-critic` to re-check `${CLAUDE_PLUGIN_ROOT}/fp verify` numbers.
