"""Thin client for a locally-running Ollama model (Gemma, Llama, …).

We use the plain ``/api/generate`` endpoint (non-streaming) to keep things
simple: one request in, one answer out. Host and model are env-configurable so
you can point at a remote Ollama or swap the model.

Why ``num_ctx`` matters: Ollama defaults to a tiny ~2048-token context window.
cmd-genie stuffs your whole cheat-sheet into the prompt, which is easily larger
than that — so the default silently truncates your file and the model answers
from fragments. We raise the window (``OLLAMA_NUM_CTX``) so the full knowledge
base is actually read, and keep the temperature low so commands come back
deterministic instead of creative.
"""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

import httpx

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
# Big enough for a sizable cheat-sheet + the question. Override if your file grows.
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "16384"))
OLLAMA_TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.1"))
# Keep the model resident between questions so only the FIRST call pays the
# multi-GB load cost; later answers start streaming almost immediately.
OLLAMA_KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "10m")


class ModelError(Exception):
    """Raised when the model can't be reached or errors out."""


def _payload(prompt: str, temperature: float | None, stream: bool) -> dict:
    return {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": stream,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "temperature": OLLAMA_TEMPERATURE if temperature is None else temperature,
        },
    }


# Generous read timeout: the big model can take a while to load on the first
# call, and we hold the connection open while it streams.
_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


async def generate_stream(
    prompt: str, *, temperature: float | None = None
) -> AsyncIterator[str]:
    """Yield the model's answer token-by-token from Ollama's streaming API."""
    url = f"{OLLAMA_HOST.rstrip('/')}/api/generate"
    payload = _payload(prompt, temperature, stream=True)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode(errors="replace")[:200]
                    raise ModelError(
                        f"Ollama returned {resp.status_code}. "
                        f"Is the model '{OLLAMA_MODEL}' pulled? ({detail})"
                    )
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    chunk = obj.get("response")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        break
    except httpx.ConnectError as exc:
        raise ModelError(
            f"Couldn't reach Ollama at {OLLAMA_HOST}. Is it running? "
            f"Try `ollama serve` and `ollama pull {OLLAMA_MODEL}`."
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelError(f"Request to Ollama failed: {exc}") from exc


async def generate(prompt: str, *, temperature: float | None = None) -> str:
    """Non-streaming convenience wrapper: collect the full answer."""
    parts = [chunk async for chunk in generate_stream(prompt, temperature=temperature)]
    return "".join(parts).strip()


async def warm() -> None:
    """Preload the model into memory (empty prompt) so the first real question
    doesn't pay the multi-GB load cost. Blocks until the model is resident."""
    url = f"{OLLAMA_HOST.rstrip('/')}/api/generate"
    payload = {"model": OLLAMA_MODEL, "prompt": "", "keep_alive": OLLAMA_KEEP_ALIVE}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise ModelError(
                    f"Ollama returned {resp.status_code} loading '{OLLAMA_MODEL}'. "
                    f"Is it pulled? ({resp.text[:200]})"
                )
    except httpx.ConnectError as exc:
        raise ModelError(
            f"Couldn't reach Ollama at {OLLAMA_HOST}. Is it running?"
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelError(f"Request to Ollama failed: {exc}") from exc


async def is_loaded() -> bool:
    """Whether OLLAMA_MODEL is currently resident in Ollama (via /api/ps)."""
    url = f"{OLLAMA_HOST.rstrip('/')}/api/ps"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return any(
                m.get("name") == OLLAMA_MODEL or m.get("model") == OLLAMA_MODEL
                for m in models
            )
    except httpx.HTTPError:
        return False
