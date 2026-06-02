#!/usr/bin/env bash
# Start cmd-genie: sync deps and serve the UI + API on one port.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8090}"
MODEL="${OLLAMA_MODEL:-gemma3:4b}"

# Friendly nudge if Ollama isn't reachable (the app still starts).
if ! curl -fsS "${OLLAMA_HOST:-http://localhost:11434}/api/tags" >/dev/null 2>&1; then
  echo "⚠️  Ollama doesn't seem to be running."
  echo "    Start it with:  ollama serve"
  echo "    Pull the model: ollama pull ${MODEL}"
fi

echo "▸ Syncing backend deps…"
( cd backend && unset VIRTUAL_ENV && uv sync )

echo "▸ cmd-genie on http://localhost:${PORT}   (model: ${MODEL})"
cd backend
unset VIRTUAL_ENV
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
