#!/bin/bash
# Launch wrapper for the always-on Jarvis service (run by launchd).
# Sources the API keys from ~/swechats/.env at runtime — they are never copied elsewhere.
set -a
[ -f "$HOME/swechats/.env" ] && . "$HOME/swechats/.env"
set +a
cd "$HOME/mentat" || exit 1
exec "$HOME/swechats/.venv/bin/python" -m mentat.jarvis
