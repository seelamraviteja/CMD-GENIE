"""cmd-genie — ask in plain English, get the command.

A tiny FastAPI app that:
1. serves a single-page chat UI at ``/``,
2. exposes ``POST /api/ask`` which feeds your ``commands.md`` cheat-sheet plus
   the question to a local Gemma model (via Ollama) and returns the answer.

The whole cheat-sheet is stuffed into the prompt as context — no database, no
vector search. For a personal file that's all you need, and it keeps the model
grounded in *your* commands.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from . import gemma

ROOT = Path(__file__).resolve().parent.parent.parent
COMMANDS_FILE = ROOT / "commands.md"
NOTES_FILE = ROOT / "notes.md"
INDEX_FILE = ROOT / "frontend" / "index.html"

app = FastAPI(title="cmd-genie")


def _read(path: Path, fallback: str) -> str:
    return path.read_text() if path.exists() else fallback


def _load_commands() -> str:
    return _read(COMMANDS_FILE, "(no commands.md found)")


def _load_notes() -> str:
    return _read(NOTES_FILE, "(no notes yet)")


def _build_prompt(question: str, cheatsheet: str, notes: str) -> str:
    return f"""You are cmd-genie, a concise command-line assistant.

You have two sources of truth about THIS user:
1. A command cheat-sheet (how to do things).
2. Personal NOTES (their own facts: IPs, hostnames, URLs, accounts).

How to answer:
- COMMAND / how-to questions: prefer a command from the cheat-sheet; otherwise
  use general knowledge. Return the single best command in a fenced code block
  (```), one command per line if multiple steps, then ONE short line explaining
  it.
- FACT questions about the user's own environment (e.g. "what is the jumpbox
  IP", "staging url", "db host"): answer ONLY from the NOTES below. Quote the
  exact value. If the specific fact is NOT in the NOTES, reply EXACTLY:
  "Not available — add it in your notes." Do NOT guess or invent IPs, hosts,
  URLs, or credentials.

End every answer with a final line that is exactly one of:
- "Source: notes"             (fact came from the NOTES)
- "Source: cheat-sheet"       (command came from the cheat-sheet)
- "Source: general knowledge" (command came from your own knowledge)
Add nothing else. No preamble.

--- BEGIN CHEAT-SHEET ---
{cheatsheet}
--- END CHEAT-SHEET ---

--- BEGIN NOTES ---
{notes}
--- END NOTES ---

User question: {question}
"""


class AskRequest(BaseModel):
    question: str


class NotesRequest(BaseModel):
    content: str


@app.post("/api/ask")
async def ask(req: AskRequest) -> dict[str, str]:
    question = (req.question or "").strip()
    if not question:
        return {"answer": "Ask me how to do something — e.g. *undo my last commit*.", "ok": "false"}
    prompt = _build_prompt(question, _load_commands(), _load_notes())
    try:
        answer = await gemma.generate(prompt)
    except gemma.ModelError as exc:
        return {"answer": f"⚠️ {exc}", "ok": "false"}
    return {"answer": answer or "(no response)", "ok": "true"}


@app.get("/api/commands", response_class=PlainTextResponse)
def commands() -> str:
    """Return the raw cheat-sheet (the UI shows it in a side panel)."""
    return _load_commands()


@app.get("/api/notes", response_class=PlainTextResponse)
def get_notes() -> str:
    """Return the user's personal facts so the editor panel can load them."""
    return _load_notes()


@app.put("/api/notes")
def save_notes(req: NotesRequest) -> dict[str, bool]:
    """Persist edits from the 'My data' panel back to notes.md."""
    NOTES_FILE.write_text(req.content)
    return {"saved": True}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": gemma.OLLAMA_MODEL}


@app.get("/")
def index():
    return FileResponse(INDEX_FILE)
