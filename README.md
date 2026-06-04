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
 │  Source: your files                           │
 └──────────────────────────────────────────────┘
```

## How it works

No database, no embeddings. On each question the backend reads **every `*.md`
file in [`data/`](data/)** and stuffs them into the prompt as context, then asks
the model to answer. Everything in `data/` is one knowledge base — commands
*and* facts:

- [`data/quick-access.md`](data/quick-access.md) — your real command stash (the
  imported *Quick Access*): how-tos **and** facts like passwords, IPs, hosts.
- [`data/commands.md`](data/commands.md) — a general how-to cheat-sheet.
- [`data/notes.md`](data/notes.md) — extra personal facts.

Ask *"what is the postgres password for platform?"* and it quotes the exact
value from your files. **If a fact isn't written down anywhere, it replies
"Not available" — it never guesses an IP, host, or credential.**

```
data/*.md ──▶ FastAPI /api/ask ──▶ Ollama ──▶ answer streamed token-by-token
                                              + copy button
                                              (tagged: your files / general knowledge)
```

Answers **stream in as they're generated** (the backend proxies Ollama's
streaming API and the UI renders tokens live), so you see text within moments
instead of staring at a blank box.

> **Why answers got better:** Ollama defaults to a tiny ~2048-token context
> window, which silently truncates a large cheat-sheet (and the model then
> answers from whatever fragments survive). cmd-genie sets `OLLAMA_NUM_CTX`
> (default `16384`) so your **whole** file is actually read, and runs at a low
> temperature so commands come back verbatim instead of invented.

Edit any file straight from the **My data** drawer in the app — pick a tab, edit,
Save. Changes hit disk in `data/` and are picked up on the next question (no
restart), and they persist across restarts.

## Rephrase

The app has a second view (**Rephrase** in the top nav): paste any text and the
same local model fixes its grammar and structure. Pick a style — *Polish,
Concise, Professional, Friendly, Formal,* or *Bullet points* — and copy the
result. `POST /api/rephrase` with `{ "text": "...", "mode": "polish" }`.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) — Python 3.10+ environment manager
- [Ollama](https://ollama.com) with a Gemma model pulled:

```bash
ollama pull gemma4:e4b     # the default; or any model you like
```

## Run

Ollama must be running on your machine either way (`ollama serve`).

Your knowledge lives in `data/`, which is **git-ignored** (it holds real hosts
and credentials). On a fresh clone, seed it from the tracked template first:

```bash
cp -r data.example data    # then edit data/*.md with your real stuff
```

**Local (uv):**

```bash
git clone <your-repo-url> cmd-genie && cd cmd-genie
cp -r data.example data
./run.sh                               # defaults to gemma4:e4b; override with OLLAMA_MODEL=…
```

**Docker** — the container talks to the Ollama on your host, and bind-mounts
`./data` so your cheat-sheets survive `down`/restarts:

```bash
cp .env.example .env       # set OLLAMA_MODEL to a model you've pulled
docker compose up --build
```

Either way, open **<http://localhost:8090>** and start asking.

## Make it yours

Edit the files in [`data/`](data/) — or use the **My data** drawer in the app.
`commands.md` is markdown bullets; `quick-access.md` / `notes.md` are free-form:

```markdown
## git
- `git switch -c <branch>` — create and switch to a new branch
```

Changes are picked up on the next question — no restart.

## Configuration

| Variable | Default | What it does |
|----------|---------|--------------|
| `PORT` | `8090` | Port the web app listens on |
| `OLLAMA_HOST` | `http://localhost:11434` | Where Ollama is running |
| `OLLAMA_MODEL` | `gemma4:e4b` | Which pulled model to use |
| `OLLAMA_NUM_CTX` | `16384` | Context window — raise it if your files grow large |
| `OLLAMA_KEEP_ALIVE` | `10m` | How long Ollama keeps the model loaded in RAM between questions |
| `CMD_GENIE_DATA` | `./data` | Directory of `*.md` knowledge files |

```bash
OLLAMA_MODEL=gemma2 PORT=9000 ./run.sh
```

## Project layout

```
data/*.md              your knowledge base — cheat-sheets + facts (git-ignored, the Docker volume)
data.example/*.md      safe tracked template — copy to data/ on a fresh clone
backend/app/main.py    FastAPI: /api/ask, /api/rephrase, /api/files, serves the UI
backend/app/gemma.py   Ollama client (sets num_ctx so the whole file is read)
frontend/index.html    single-page UI: Ask + Rephrase views, "My data" editor (no build step)
Dockerfile             single-container image (UI + API)
docker-compose.yml     run it with ./data bind-mounted for persistence
run.sh                 local launcher (uv)
```

## Performance

Responses stream, so you see tokens as soon as the model produces them. Two
things affect how fast that first token appears:

- **First call after idle is slow** — the model (a few GB) has to load into RAM.
  Click **Load model** in the header to preload it before you ask (the badge dot
  turns green when it's ready). cmd-genie also sets `OLLAMA_KEEP_ALIVE=10m`, so
  once loaded it stays resident for 10 minutes of inactivity and later questions
  start almost instantly. Bump it (e.g. `30m`) if you ask in bursts.
- **Model size** — `gemma4:e4b` is a good balance. For snappier replies on a
  modest machine, try a smaller model (`OLLAMA_MODEL=gemma4:e2b`); for better
  answers at the cost of speed, a larger one.

## Ideas / roadmap

- `genie "..."` CLI that prints the command straight to your terminal
- An "Add this command" button that appends to `commands.md`
- Keyword fallback search when the model is offline
- Per-category filter chips

## License

MIT — see [LICENSE](LICENSE).
