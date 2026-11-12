"""Collect postings from the command line.

    python -m app.coleta gupy            # all configured terms
    python -m app.coleta gupy python     # just these terms
    python -m app.coleta github          # community boards (GITHUB_TOKEN raises the rate limit)
    python -m app.coleta empresas        # career pages on Greenhouse and Ashby
    python -m app.coleta todas
    python -m app.coleta status
"""

import asyncio
import sys

import httpx
from sqlalchemy import func, select, update

from app.coleta import empresas, github, gupy
from app.coleta.servico import coletar_fonte
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.models import Coleta, Fonte, Modalidade, Vaga


async def marcar_incompleta(session, coleta: Coleta, falhas: list[str]) -> None:
    """A board that failed wasn't read: its postings must not look taken down."""
    if falhas:
        await session.execute(update(Coleta).where(Coleta.id == coleta.id).values(completa=False))
        await session.commit()


async def main() -> None:
    comando, *args = sys.argv[1:] or ["status"]
    headers = {"User-Agent": settings.agente_http}
    async with SessionLocal() as session:
        if comando in ("gupy", "todas"):
            async with httpx.AsyncClient(headers=headers, timeout=settings.coleta_timeout_s) as http:
                c = await coletar_fonte(session, Fonte.gupy, gupy.coletar(http, (comando == "gupy" and args) or settings.gupy_termos), completa=not args)
            print(f"gupy: {c.vistas} vistas, {c.novas} novas")
        if comando in ("github", "todas"):
            h = headers | {"Accept": "application/vnd.github+json"}
            if settings.github_token:
                h["Authorization"] = f"Bearer {settings.github_token}"
            falhas: list[str] = []
            async with httpx.AsyncClient(headers=h, timeout=github.TIMEOUT_S) as http:
                c = await coletar_fonte(session, Fonte.github, github.coletar(http, (comando == "github" and args) or settings.github_repos, falhas), completa=not args)
            await marcar_incompleta(session, c, falhas)
            print(f"github: {c.vistas} vistas, {c.novas} novas" + (f" · falharam: {', '.join(falhas)}" if falhas else ""))
        if comando in ("empresas", "todas"):
            async with httpx.AsyncClient(headers=headers, timeout=settings.coleta_timeout_s) as http:
                for fonte, coletor, lista in (
                    (Fonte.greenhouse, empresas.coletar_greenhouse, settings.greenhouse_empresas),
                    (Fonte.ashby, empresas.coletar_ashby, settings.ashby_empresas),
                ):
                    falhas = []
                    c = await coletar_fonte(session, fonte, coletor(http, lista, falhas))
                    await marcar_incompleta(session, c, falhas)
                    print(f"{fonte.value}: {c.vistas} vistas, {c.novas} novas" + (f" · falharam: {', '.join(falhas)}" if falhas else ""))
        if comando not in ("gupy", "github", "empresas", "todas", "status"):
            sys.exit(f"comando desconhecido: {comando}")
        if comando == "status":
            por_fonte = (await session.execute(select(Vaga.fonte, func.count()).group_by(Vaga.fonte))).all()
            por_modalidade = (await session.execute(select(Vaga.modalidade, func.count()).group_by(Vaga.modalidade))).all()
            print("vagas por fonte:", {f.value: n for f, n in por_fonte})
            print("por modalidade:", {m.value: n for m, n in por_modalidade})
            ultimas = (await session.scalars(select(Coleta).order_by(Coleta.id.desc()).limit(5))).all()
            for c in ultimas:
                print(f"  {c.iniciada_em:%d/%m %H:%M} {c.fonte.value}: {c.vistas} vistas, {c.novas} novas{' · ERRO ' + c.erro if c.erro else ''}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
