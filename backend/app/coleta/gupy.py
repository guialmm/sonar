"""Gupy: the job board most Brazilian companies use. Its portal search is a public JSON API
(the one portal.gupy.io calls). It searches by term, 100 per page; the `total` it returns
is capped at 100, so paging goes on until a page comes back short."""

from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from app.coleta.base import VagaColetada, pegar_json, texto_limpo
from app.models import Fonte, Modalidade

URL = "https://portal.gupy.io/api/job-search/jobs"
POR_PAGINA = 100
MAX_PAGINAS = 20  # 2,000 postings per term is far beyond any real search

MODALIDADE = {"remote": Modalidade.remoto, "hybrid": Modalidade.hibrido, "on-site": Modalidade.presencial}


def data(iso: str | None) -> datetime | None:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None


def ler(item: dict) -> VagaColetada:
    return VagaColetada(
        fonte=Fonte.gupy,
        id_externo=str(item["id"]),
        url=item["jobUrl"].split("?")[0],
        titulo=" ".join(item["name"].split()),
        empresa=" ".join((item.get("careerPageName") or "").split()) or "Empresa não informada",
        descricao=texto_limpo(item.get("description")),
        modalidade=MODALIDADE.get(item.get("workplaceType"), Modalidade.nao_informado),
        cidade=item.get("city") or None,
        estado=item.get("state") or None,
        pais="Brasil",
        publicada_em=data(item.get("publishedDate")),
        prazo=data(item.get("applicationDeadline")),
        raw=item,
    )


async def coletar(http: httpx.AsyncClient, termos: list[str], **kw) -> AsyncIterator[VagaColetada]:
    """Every posting for every term, each one once even when several terms find it."""
    vistas: set[str] = set()
    for termo in termos:
        for pagina in range(MAX_PAGINAS):
            corpo = await pegar_json(
                http, URL, params={"jobName": termo, "limit": POR_PAGINA, "offset": pagina * POR_PAGINA}, **kw
            )
            itens = corpo.get("data") or []
            for item in itens:
                if str(item.get("id")) not in vistas:
                    vistas.add(str(item.get("id")))
                    yield ler(item)
            if len(itens) < POR_PAGINA:
                break
