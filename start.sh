#!/bin/bash
# Start "Ask a large PDF" on http://127.0.0.1:7860.
# Stops every copy of this app that is already running first (only this app:
# python processes running app.py from this folder), so one version is running.
cd "$(dirname "$0")" || exit 1
HERE="$(pwd)"

running() {
  for pid in $(pgrep -f "app.py"); do
    cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"
    [ "$cwd" = "$HERE" ] && echo "$pid"
  done
}

old="$(running)"
if [ -n "$old" ]; then
  echo "Stopping running copies: $old"
  kill $old 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -z "$(running)" ] && break
    sleep 0.5
  done
  left="$(running)"
  [ -n "$left" ] && kill -9 $left 2>/dev/null
fi

echo "Starting on http://127.0.0.1:7860 (Ctrl+C to stop)"
GRADIO_SERVER_PORT=7860 exec .venv/bin/python app.py
