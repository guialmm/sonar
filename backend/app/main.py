"""HTTP API: what the site calls. Collection, scoring and embeddings run as commands.

    fastapi dev app/main.py --port 8004
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.rotas import router
from app.core.config import settings

app = FastAPI(title="Sonar", description="Vagas que encaixam no seu currículo, com os motivos e o alerta de vaga fantasma")
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origens, allow_methods=["GET", "POST"], allow_headers=["Content-Type"]
)
app.include_router(router)
