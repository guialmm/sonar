"""Collect postings from the command line.

    python -m app.coleta gupy            # all configured terms
    python -m app.coleta gupy python     # just these terms
    python -m app.coleta github          # community boards (GITHUB_TOKEN raises the rate limit)
    python -m app.coleta status
"""

import asyncio
import sys

import httpx
from sqlalchemy import func, select

from app.coleta import github, gupy
from app.coleta.servico import coletar_fonte
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.models import Coleta, Fonte, Modalidade, Vaga


async def main() -> None:
    comando, *args = sys.argv[1:] or ["status"]
    async with SessionLocal() as session:
        if comando == "gupy":
            headers = {"User-Agent": settings.agente_http}
            async with httpx.AsyncClient(headers=headers, timeout=settings.coleta_timeout_s) as http:
                c = await coletar_fonte(session, Fonte.gupy, gupy.coletar(http, args or settings.gupy_termos))
            print(f"gupy: {c.vistas} vistas, {c.novas} novas em {(c.terminada_em - c.iniciada_em).seconds}s")
        elif comando == "github":
            headers = {"User-Agent": settings.agente_http, "Accept": "application/vnd.github+json"}
            if settings.github_token:
                headers["Authorization"] = f"Bearer {settings.github_token}"
            falhas: list[str] = []
            async with httpx.AsyncClient(headers=headers, timeout=github.TIMEOUT_S) as http:
                c = await coletar_fonte(session, Fonte.github, github.coletar(http, args or settings.github_repos, falhas))
            print(f"github: {c.vistas} vistas, {c.novas} novas" + (f" · falharam: {', '.join(falhas)}" if falhas else ""))
        elif comando == "status":
            por_fonte = (await session.execute(select(Vaga.fonte, func.count()).group_by(Vaga.fonte))).all()
            por_modalidade = (await session.execute(select(Vaga.modalidade, func.count()).group_by(Vaga.modalidade))).all()
            print("vagas por fonte:", {f.value: n for f, n in por_fonte})
            print("por modalidade:", {m.value: n for m, n in por_modalidade})
            ultimas = (await session.scalars(select(Coleta).order_by(Coleta.id.desc()).limit(5))).all()
            for c in ultimas:
                print(f"  {c.iniciada_em:%d/%m %H:%M} {c.fonte.value}: {c.vistas} vistas, {c.novas} novas{' · ERRO ' + c.erro if c.erro else ''}")
        else:
            sys.exit(f"comando desconhecido: {comando}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
