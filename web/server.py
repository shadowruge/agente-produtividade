import os
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config  # noqa: F401  (carrega o .env)
from config.google_auth import token_file

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Agente de produtividade")
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        from agents.productivity_agent import ProductivityAgent

        _agent = ProductivityAgent()
    return _agent


class ChatIn(BaseModel):
    sessao: str = Field(min_length=1, max_length=64)
    mensagem: str = Field(min_length=1, max_length=4000)


class ResetIn(BaseModel):
    sessao: str = Field(min_length=1, max_length=64)


def _ollama_ok() -> bool:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=1.5):
            return True
    except Exception:
        return False


@app.get("/api/status")
def status():
    return {
        "modelo": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        "ollama": _ollama_ok(),
        "google": token_file().exists(),
        "notion": bool(os.getenv("NOTION_TOKEN") and os.getenv("NOTION_DATABASE_ID")),
    }


@app.post("/api/chat")
async def chat(dados: ChatIn):
    try:
        return await run_in_threadpool(get_agent().perguntar, dados.sessao, dados.mensagem)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@app.post("/api/reset")
def reset(dados: ResetIn):
    get_agent().limpar(dados.sessao)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
