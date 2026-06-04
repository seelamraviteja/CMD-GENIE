# cmd-genie — single-container image (UI + API).
# The model itself (Ollama) runs on the HOST, not in here; the container reaches
# it at host.docker.internal. Your data/ directory is bind-mounted, so edits and
# cheat-sheets persist across start/stop.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 1) Install deps first so this layer caches unless dependencies change.
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --frozen --no-dev

# 2) App code. Real data/ is git-ignored (it holds secrets) and is bind-mounted
#    at runtime; we only bake the safe example as a fallback seed.
COPY backend ./backend
COPY frontend ./frontend
COPY data.example ./data

ENV CMD_GENIE_DATA=/app/data \
    OLLAMA_HOST=http://host.docker.internal:11434 \
    OLLAMA_MODEL=gemma4:e4b \
    OLLAMA_NUM_CTX=16384 \
    OLLAMA_KEEP_ALIVE=10m \
    PORT=8090

EXPOSE 8090
WORKDIR /app/backend
CMD ["sh", "-c", "uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
