"""HTTP API: what the site calls. Collection, scoring and embeddings run as commands.

    fastapi dev app/main.py --port 8004
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rotas import router
from app.core.config import settings

# Our own logs (model fallbacks, quota) next to uvicorn's.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s %(message)s")
for barulhento in ("httpx", "google_genai"):
    logging.getLogger(barulhento).setLevel(logging.WARNING)

app = FastAPI(title="Sonar", description="Vagas que encaixam no seu currículo, com os motivos e o alerta de vaga fantasma")
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origens, allow_methods=["GET", "POST"], allow_headers=["Content-Type"]
)
app.include_router(router)
