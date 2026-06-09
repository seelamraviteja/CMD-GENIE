"""cmd-genie — ask in plain English, get the command.

A tiny FastAPI app that:
1. serves a single-page chat UI at ``/``,
2. exposes ``POST /api/ask`` which feeds your personal knowledge base (every
   ``*.md`` file in the ``data/`` directory — cheat-sheets *and* notes) plus the
   question to a local model (via Ollama) and returns the answer.

The whole knowledge base is stuffed into the prompt as context — no database, no
vector search. For a personal file that's all you need, and it keeps the model
grounded in *your* commands and facts. The ``data/`` directory is the single
source of truth, so it survives restarts (and is the natural Docker volume).
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import gemma

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("CMD_GENIE_DATA", ROOT / "data")).resolve()
FRONTEND_DIR = ROOT / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"
ASSETS_DIR = FRONTEND_DIR / "assets"

app = FastAPI(title="cmd-genie")

# Logo, favicon and any other static art live in frontend/assets.
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


def _knowledge_files() -> list[Path]:
    """Every markdown file in the data dir — your cheat-sheets and notes."""
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.glob("*.md"))


def _safe_data_path(name: str) -> Path:
    """Resolve ``name`` to a ``*.md`` file inside DATA_DIR (no path traversal)."""
    if not name.endswith(".md") or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid file name.")
    path = (DATA_DIR / name).resolve()
    if path.parent != DATA_DIR:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    return path


_knowledge_cache: tuple[tuple, str] | None = None


def _load_knowledge() -> str:
    """Concatenate every knowledge file, each under a clear header.

    Cached on the (path, mtime) of the files, so we only re-read from disk when
    something actually changed — edits in the 'My data' panel invalidate it.
    """
    global _knowledge_cache
    files = _knowledge_files()
    fingerprint = tuple((str(p), p.stat().st_mtime_ns) for p in files)
    if _knowledge_cache and _knowledge_cache[0] == fingerprint:
        return _knowledge_cache[1]
    parts = [f"### FILE: {p.name}\n{p.read_text()}" for p in files]
    text = "\n\n".join(parts) if parts else "(no knowledge files yet)"
    _knowledge_cache = (fingerprint, text)
    return text


def _build_prompt(question: str, knowledge: str) -> str:
    return f"""You are cmd-genie, a concise command-line assistant for ONE user.

You are given that user's personal KNOWLEDGE BASE: their command cheat-sheets
and notes (IPs, hostnames, URLs, ports, accounts, passwords). Treat it as the
source of truth about their environment.

How to answer:
- COMMAND / how-to questions ("how do I…", "command to…"): if the knowledge
  base contains a matching command, return THAT command verbatim in a single
  fenced code block (```), one command per line for multi-step. Otherwise fall
  back to general knowledge. Follow the block with ONE short line explaining it.
- FACT / lookup questions ("what is the postgres password for platform", "kong
  admin api key", "jumpbox IP", "staging url"): answer ONLY from the knowledge
  base. Find the exact value and quote it verbatim. If that specific fact is NOT
  written down anywhere below, reply EXACTLY:
  "Not available — add it to your files." NEVER invent or guess a password, IP,
  host, URL, or credential.

Be direct. No preamble. Do NOT summarize or list the contents of the files.
Answer only the question asked.

End every answer with a final line that is EXACTLY one of:
- "Source: your files"        (the answer came from the knowledge base)
- "Source: general knowledge" (a command came from your own knowledge)

--- BEGIN KNOWLEDGE BASE ---
{knowledge}
--- END KNOWLEDGE BASE ---

User question: {question}
"""


class AskRequest(BaseModel):
    question: str


class FileRequest(BaseModel):
    content: str


class RephraseRequest(BaseModel):
    text: str
    mode: str = "polish"


# Each mode is one instruction handed to the model. Keep them short and concrete.
REPHRASE_MODES: dict[str, str] = {
    "polish": "Fix grammar, spelling and punctuation, and improve the sentence "
    "structure and flow. Keep the original meaning and roughly the same length.",
    "concise": "Make it clearer and more concise. Cut redundancy and filler while "
    "keeping every important point.",
    "professional": "Rewrite in a polished, professional tone suitable for a work "
    "email or message. Fix any grammar issues.",
    "friendly": "Rewrite in a warm, friendly, conversational tone. Fix any grammar "
    "issues.",
    "formal": "Rewrite in a formal, precise tone. Fix any grammar issues.",
    "bullets": "Restructure the content into clear, well-organized bullet points, "
    "fixing grammar as you go.",
}


def _build_rephrase_prompt(text: str, instruction: str) -> str:
    return f"""You are a careful writing editor. Rewrite the text below.

Task: {instruction}

Rules:
- Output ONLY the rewritten text — no preamble, no commentary, no surrounding
  quotes, and no code fences.
- Keep the original language and intended meaning. Do NOT invent new facts.

--- TEXT ---
{text}
--- END TEXT ---

Rewritten text:"""


def _stream(prompt: str, temperature: float | None = None) -> StreamingResponse:
    """Stream a model answer to the client as plain UTF-8 text, token by token.

    Errors surface as text in the body: the stream is already a 200 by the time
    the model is reached, so the UI just shows the ⚠️ message inline.
    """

    async def gen():
        try:
            async for chunk in gemma.generate_stream(prompt, temperature=temperature):
                yield chunk
        except gemma.ModelError as exc:
            yield f"\n⚠️ {exc}"

    # X-Accel-Buffering off keeps any intermediary from buffering the stream.
    return StreamingResponse(
        gen(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


def _text(message: str) -> StreamingResponse:
    async def one():
        yield message

    return StreamingResponse(one(), media_type="text/plain; charset=utf-8")


@app.post("/api/ask")
async def ask(req: AskRequest) -> StreamingResponse:
    question = (req.question or "").strip()
    if not question:
        return _text("Ask me how to do something — e.g. *undo my last commit*.")
    return _stream(_build_prompt(question, _load_knowledge()))


@app.post("/api/rephrase")
async def rephrase(req: RephraseRequest) -> StreamingResponse:
    text = (req.text or "").strip()
    if not text:
        return _text("")
    instruction = REPHRASE_MODES.get(req.mode, REPHRASE_MODES["polish"])
    # A little more warmth than command lookup, so it reads naturally.
    return _stream(_build_rephrase_prompt(text, instruction), temperature=0.4)


@app.get("/api/warm")
async def warm_status() -> dict[str, object]:
    """Is the model already resident? (for the 'Load model' button state)"""
    return {"loaded": await gemma.is_loaded(), "model": gemma.OLLAMA_MODEL}


@app.post("/api/warm")
async def warm() -> dict[str, object]:
    """Preload the model so the first question is instant."""
    try:
        await gemma.warm()
    except gemma.ModelError as exc:
        return {"ok": False, "error": str(exc), "model": gemma.OLLAMA_MODEL}
    return {"ok": True, "model": gemma.OLLAMA_MODEL}


@app.get("/api/files")
def list_files() -> dict[str, list[str]]:
    """Names of the editable knowledge files, for the 'My data' tabs."""
    return {"files": [p.name for p in _knowledge_files()]}


@app.get("/api/files/{name}", response_class=PlainTextResponse)
def get_file(name: str) -> str:
    path = _safe_data_path(name)
    return path.read_text() if path.exists() else ""


@app.put("/api/files/{name}")
def save_file(name: str, req: FileRequest) -> dict[str, bool]:
    """Persist edits from the 'My data' panel back to the data file."""
    path = _safe_data_path(name)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content)
    return {"saved": True}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": gemma.OLLAMA_MODEL}


@app.get("/")
@app.get("/ask")
@app.get("/rephrase")
def index():
    """The SPA. The same page serves every client-side route, so /rephrase and
    /ask are directly loadable / refreshable / shareable.

    no-cache: always revalidate the HTML so a UI update is picked up on reload
    (the browser still uses its copy if unchanged, but never serves it stale).
    """
    return FileResponse(INDEX_FILE, headers={"Cache-Control": "no-cache"})
