"""The demo profile: the author's own CV without name or contacts (approved by him), so
anyone can see Sonar work without uploading a CV."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

ARQUIVO = Path(__file__).with_name("exemplo.json")


@lru_cache
def exemplo() -> dict | None:
    return json.loads(ARQUIVO.read_text()) if ARQUIVO.exists() else None


MAX_PAGINA = 8000


def normalizar(perfil: dict, paginas: list[str]) -> tuple[dict, list[str]]:
    """What the API works with: the profile as validated, each page cut to size."""
    from app.perfil.schemas import Perfil

    return Perfil.model_validate(perfil).model_dump(), [p[:MAX_PAGINA] for p in paginas]


def chave(perfil: dict, paginas: list[str]) -> str:
    """Identifies a (profile, CV text) pair without keeping either."""
    perfil, paginas = normalizar(perfil, paginas)
    return hashlib.sha256(json.dumps([perfil, paginas], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@lru_cache
def chave_do_exemplo() -> str | None:
    e = exemplo()
    return chave(e["perfil"], e["paginas"]) if e else None
