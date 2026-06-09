"""Tests for cmd-genie's FastAPI layer.

These cover the parts that don't need a running model: file safety (the
path-traversal guard that protects read/write), prompt building, the knowledge
cache, and the file API. Endpoints that call Ollama are exercised only on their
empty-input shortcut, so the suite runs offline.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point the app at a throwaway data dir with one sample file."""
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "_knowledge_cache", None)
    (tmp_path / "commands.md").write_text("# cmds\n- `ls` — list files\n")
    return tmp_path


@pytest.fixture
def client():
    return TestClient(main.app)


# ── path-traversal safety (guards file read/write) ───────────────────────────
@pytest.mark.parametrize(
    "bad",
    ["../secret.md", "..%2f.md", "sub/dir.md", "back\\slash.md", ".hidden.md", "notes.txt"],
)
def test_safe_data_path_rejects(bad, data_dir):
    with pytest.raises(HTTPException) as exc:
        main._safe_data_path(bad)
    assert exc.value.status_code == 400


def test_safe_data_path_accepts_plain_md(data_dir):
    assert main._safe_data_path("notes.md") == (data_dir / "notes.md")


def test_file_api_blocks_traversal(client, data_dir):
    assert client.get("/api/files/..%2f..%2frun.sh").status_code in (400, 404)


# ── prompt + knowledge ───────────────────────────────────────────────────────
def test_build_prompt_includes_question_and_knowledge():
    prompt = main._build_prompt("how do I X?", "KB-CONTENT")
    assert "how do I X?" in prompt
    assert "KB-CONTENT" in prompt
    assert "Source: your files" in prompt  # the grounding instruction is present


def test_load_knowledge_reads_and_caches(data_dir):
    out = main._load_knowledge()
    assert "ls" in out and "FILE: commands.md" in out
    # second call hits the cache for the same file set
    assert main._load_knowledge() == out


def test_rephrase_modes_have_default():
    assert "polish" in main.REPHRASE_MODES


# ── endpoints that don't need the model ──────────────────────────────────────
def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and "model" in body


def test_files_list_get_put_roundtrip(client, data_dir):
    assert "commands.md" in client.get("/api/files").json()["files"]
    client.put("/api/files/notes.md", json={"content": "hello"})
    assert client.get("/api/files/notes.md").text == "hello"
    assert (data_dir / "notes.md").read_text() == "hello"


def test_ask_empty_returns_hint(client):
    # empty question short-circuits before any model call
    assert "undo my last commit" in client.post("/api/ask", json={"question": "  "}).text


def test_rephrase_empty_returns_empty(client):
    assert client.post("/api/rephrase", json={"text": ""}).text == ""


def test_spa_routes_serve_index(client):
    for path in ("/", "/ask", "/rephrase"):
        r = client.get(path)
        assert r.status_code == 200 and "cmd" in r.text.lower()
