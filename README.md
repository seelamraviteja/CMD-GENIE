<div align="center">

# ⌘ cmd-genie

### _Ask in plain English — get the command._

A tiny web app that keeps all your commands in a plain text file and puts a
**local Gemma chatbot** in front of it. Ask *"how do I undo my last commit?"* and
it hands you the exact command — checking **your** cheat-sheet first, then
general knowledge.

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab)
![Model: Gemma via Ollama](https://img.shields.io/badge/model-Gemma%20(Ollama)-6e7bff)

</div>

---

## Why

You already know *what* you want to do — you just forget the exact flags. Instead
of googling "tar extract gz" for the hundredth time, keep your commands in one
file and ask in your own words. Runs **fully local** via [Ollama](https://ollama.com),
so nothing leaves your machine.

```
 You: "compress a folder into a tar.gz"
 ┌──────────────────────────────────────────────┐
 │  tar -czf out.tar.gz <dir>          [📋 copy] │
 │  Compress a folder to a .tar.gz archive.      │
 │  Source: cheat-sheet                          │
 └──────────────────────────────────────────────┘
```

## How it works

No database, no embeddings. On each question the backend reads two files and
stuffs them into the prompt as context, then asks Gemma to answer:

- [`commands.md`](commands.md) — your **how-to** cheat-sheet.
- [`notes.md`](notes.md) — your **personal facts** (jumpbox IP, hostnames, URLs,
  accounts). Ask *"what's the jumpbox IP?"* and it quotes the exact value.
  **If a fact isn't in your notes, it replies "Not available" — it never guesses
  an IP, host, or credential.**

```
commands.md ─┐
notes.md ────┴▶ FastAPI /api/ask ─▶ Ollama (Gemma) ─▶ answer + copy button
                                                       (tagged: notes / cheat-sheet / general)
```

Edit your facts straight from the **📝 My data** panel in the app — no restart.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — Python 3.10+ environment manager
- [Ollama](https://ollama.com) with a Gemma model pulled:

```bash
ollama pull gemma3        # or gemma2 / any model you like
```

## Run

```bash
git clone <your-repo-url> cmd-genie && cd cmd-genie
./run.sh                  # serves UI + API on http://localhost:8090
```

Open **<http://localhost:8090>** and start asking.

## Make it yours

Edit [`commands.md`](commands.md) — it's just markdown bullets:

```markdown
## git
- `git switch -c <branch>` — create and switch to a new branch
```

Changes are picked up on the next question; no restart needed.

## Configuration

| Variable | Default | What it does |
|----------|---------|--------------|
| `PORT` | `8090` | Port the web app listens on |
| `OLLAMA_HOST` | `http://localhost:11434` | Where Ollama is running |
| `OLLAMA_MODEL` | `gemma3` | Which pulled model to use |

```bash
OLLAMA_MODEL=gemma2 PORT=9000 ./run.sh
```

## Project layout

```
commands.md            your editable command cheat-sheet (how-to)
notes.md               your personal facts (IPs, hosts, URLs, accounts)
backend/app/main.py    FastAPI: /api/ask, /api/commands, /api/notes, serves UI
backend/app/gemma.py   Ollama client (non-streaming /api/generate)
frontend/index.html    single-page chat UI + "My data" editor (no build step)
run.sh                 launcher
```

## Ideas / roadmap

- `genie "..."` CLI that prints the command straight to your terminal
- An "Add this command" button that appends to `commands.md`
- Keyword fallback search when the model is offline
- Per-category filter chips

## License

MIT — see [LICENSE](LICENSE).
