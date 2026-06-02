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
from fastapi.responses import FileResponse, PlainTextResponse
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


def _load_knowledge() -> str:
    """Concatenate every knowledge file, each under a clear header."""
    parts: list[str] = []
    for path in _knowledge_files():
        parts.append(f"### FILE: {path.name}\n{path.read_text()}")
    return "\n\n".join(parts) if parts else "(no knowledge files yet)"


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


@app.post("/api/ask")
async def ask(req: AskRequest) -> dict[str, str]:
    question = (req.question or "").strip()
    if not question:
        return {"answer": "Ask me how to do something — e.g. *undo my last commit*.", "ok": "false"}
    prompt = _build_prompt(question, _load_knowledge())
    try:
        answer = await gemma.generate(prompt)
    except gemma.ModelError as exc:
        return {"answer": f"⚠️ {exc}", "ok": "false"}
    return {"answer": answer or "(no response)", "ok": "true"}


@app.post("/api/rephrase")
async def rephrase(req: RephraseRequest) -> dict[str, str]:
    text = (req.text or "").strip()
    if not text:
        return {"result": "", "ok": "false"}
    instruction = REPHRASE_MODES.get(req.mode, REPHRASE_MODES["polish"])
    prompt = _build_rephrase_prompt(text, instruction)
    try:
        # A little more warmth than command lookup, so it reads naturally.
        result = await gemma.generate(prompt, temperature=0.4)
    except gemma.ModelError as exc:
        return {"result": f"⚠️ {exc}", "ok": "false"}
    return {"result": result or "(no response)", "ok": "true"}


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
def index():
    return FileResponse(INDEX_FILE)
