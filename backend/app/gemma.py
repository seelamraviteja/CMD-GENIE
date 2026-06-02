"""Thin client for a locally-running Ollama Gemma model.

We use the plain ``/api/generate`` endpoint (non-streaming) to keep things
simple: one request in, one answer out. Host and model are env-configurable so
you can point at a remote Ollama or swap ``gemma3`` for any pulled model.
"""
from __future__ import annotations

import os

import httpx

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3")


class ModelError(Exception):
    """Raised when the model can't be reached or errors out."""


async def generate(prompt: str) -> str:
    url = f"{OLLAMA_HOST.rstrip('/')}/api/generate"
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise ModelError(
            f"Couldn't reach Ollama at {OLLAMA_HOST}. Is it running? "
            f"Try `ollama serve` and `ollama pull {OLLAMA_MODEL}`."
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200]
        raise ModelError(
            f"Ollama returned {exc.response.status_code}. "
            f"Is the model '{OLLAMA_MODEL}' pulled? ({detail})"
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelError(f"Request to Ollama failed: {exc}") from exc

    return (resp.json().get("response") or "").strip()
