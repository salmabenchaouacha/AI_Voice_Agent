"""API de l'assistant vocal : exécute une commande texte sur cette machine."""
import asyncio
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import skills  # noqa: F401  (enregistre les commandes)
from config import LANGUAGE
from router import QuitAssistant, dispatch

# Sécurité : ce serveur pilote ton ordinateur. Seules ces origines peuvent l'appeler
# (les WebSockets ne sont PAS protégés par CORS, on vérifie donc l'en-tête Origin nous-mêmes).
ALLOWED_ORIGINS = set(os.getenv(
    "VA_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
).split(","))
MAX_TEXT_CHARS = 500


def origin_ok(origin) -> bool:
    return origin is None or origin in ALLOWED_ORIGINS   # None : client non-navigateur (curl, tests)


def require_origin(request: Request) -> None:
    if not origin_ok(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origine non autorisée")


app = FastAPI(title="Assistant vocal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def run_command(text: str) -> str:
    try:
        return dispatch(text)
    except QuitAssistant as e:
        return str(e)
    except Exception as e:  # une commande qui plante ne doit pas tuer le serveur
        return f"Une erreur est survenue : {e}"


class Command(BaseModel):
    text: str


@app.get("/api/config", dependencies=[Depends(require_origin)])
def get_config():
    return {"language": LANGUAGE}


@app.post("/api/command", dependencies=[Depends(require_origin)])
async def post_command(cmd: Command):
    text = cmd.text.strip()[:MAX_TEXT_CHARS]
    if not text:
        raise HTTPException(status_code=400, detail="Commande vide")
    return {"heard": text, "reply": await asyncio.to_thread(run_command, text)}