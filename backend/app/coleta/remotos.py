"""Remote-work boards with open APIs: Himalayas (filtered to openings a person in Brazil can
take) and Remotive (worldwide or Latin America only). Plus Adzuna, a Brazilian job search
aggregator, when its free API key is set.

Aggregators repost what companies publish elsewhere: a posting here gets no "straight from
the company" bonus in the ghost-job detector."""

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

import httpx

from app.coleta.base import VagaColetada, pegar_json, texto_limpo
from app.coleta.empresas import modalidade_do_texto
from app.models import Fonte, Modalidade

log = logging.getLogger(__name__)

HIMALAYAS = "https://himalayas.app/jobs/api/search"
HIMALAYAS_POR_PAGINA = 20  # fixed by the API
REMOTIVE = "https://remotive.com/api/remote-jobs"
ADZUNA = "https://api.adzuna.com/v1/api/jobs/br/search/{pagina}"
ADZUNA_POR_PAGINA = 50

# Remotive's free-text "who can apply": what a person in Brazil can answer.
REMOTIVE_ABERTA = re.compile(r"worldwide|anywhere|latam|latin america|south america|americas|bra[sz]il", re.I)


def de_epoch(segundos: int | float | None) -> datetime | None:
    return datetime.fromtimestamp(segundos, UTC) if segundos else None


def ler_himalayas(job: dict) -> VagaColetada:
    restricoes = job.get("locationRestrictions") or []
    url = job.get("guid") or job["applicationLink"].split("?")[0]
    salario = ""
    if job.get("minSalary") and job.get("currency"):
        salario = f"Salário: {job['currency']} {job['minSalary']:,}" + (f" a {job['maxSalary']:,}" if job.get("maxSalary") else "")
    return VagaColetada(
        fonte=Fonte.himalayas,
        id_externo=url.removeprefix("https://himalayas.app/companies/"),
        url=url,
        titulo=" ".join(job["title"].split()),
        empresa=" ".join((job.get("companyName") or "").split()) or "Empresa não informada",
        descricao="\n\n".join(t for t in (texto_limpo(job.get("description")), salario) if t),
        modalidade=Modalidade.remoto,
        # Open to Brazil by the search filter: an empty list means anywhere.
        pais="Brasil" if restricoes == ["Brazil"] else None,
        publicada_em=de_epoch(job.get("pubDate")),
        prazo=de_epoch(job.get("expiryDate")),
        etiquetas=[*(job.get("seniority") or []), *(job.get("parentCategories") or [])[:3], job.get("employmentType") or ""][:8],
        raw={k: job.get(k) for k in ("guid", "title", "companyName", "companySlug", "locationRestrictions", "seniority", "pubDate", "employmentType")},
    )


async def coletar_himalayas(
    http: httpx.AsyncClient, max_paginas: int, *, pausa: Callable[[float], Awaitable[None]] = asyncio.sleep, **kw
) -> AsyncIterator[VagaColetada]:
    """Newest first; stops at `max_paginas` (20 each) or at the end of the list."""
    for pagina in range(1, max_paginas + 1):
        corpo = await pegar_json(http, HIMALAYAS, params={"country": "BR", "page": pagina}, **kw)
        jobs = corpo.get("jobs") or []
        for job in jobs:
            yield ler_himalayas(job)
        if len(jobs) < HIMALAYAS_POR_PAGINA:
            break
        await pausa(0.4)  # polite: a public API with no key


def ler_remotive(job: dict) -> VagaColetada | None:
    onde = job.get("candidate_required_location") or ""
    if not REMOTIVE_ABERTA.search(onde):
        return None
    return VagaColetada(
        fonte=Fonte.remotive,
        id_externo=str(job["id"]),
        url=job["url"],  # Remotive's terms: link back to the posting on Remotive
        titulo=" ".join(job["title"].split()),
        empresa=" ".join((job.get("company_name") or "").split()) or "Empresa não informada",
        descricao="\n\n".join(t for t in (texto_limpo(job.get("description")), f"Salário: {job['salary']}" if job.get("salary") else "") if t),
        modalidade=Modalidade.remoto,
        pais=None,
        publicada_em=datetime.fromisoformat(job["publication_date"]).replace(tzinfo=UTC) if job.get("publication_date") else None,
        etiquetas=[job.get("category") or "", *(job.get("tags") or [])[:7]],
        raw={k: job.get(k) for k in ("id", "title", "company_name", "category", "candidate_required_location", "publication_date", "job_type")},
    )


async def coletar_remotive(http: httpx.AsyncClient, **kw) -> AsyncIterator[VagaColetada]:
    corpo = await pegar_json(http, REMOTIVE, **kw)
    for job in corpo.get("jobs") or []:
        if (v := ler_remotive(job)) is not None:
            yield v


def ler_adzuna(job: dict) -> VagaColetada:
    lugar = job.get("location") or {}
    areas = lugar.get("area") or []  # ["Brasil", "São Paulo", "Campinas"]
    titulo = " ".join(texto_limpo(job["title"]).split())
    descricao = texto_limpo(job.get("description"))
    return VagaColetada(
        fonte=Fonte.adzuna,
        id_externo=str(job["id"]),
        url=job["redirect_url"],
        titulo=titulo,
        empresa=" ".join(((job.get("company") or {}).get("display_name") or "").split()) or "Empresa não informada",
        descricao=descricao,
        modalidade=modalidade_do_texto(titulo, descricao[:600]),
        estado=areas[1] if len(areas) > 1 else None,
        cidade=areas[-1] if len(areas) > 2 else None,
        pais="Brasil",
        publicada_em=datetime.fromisoformat(job["created"].replace("Z", "+00:00")) if job.get("created") else None,
        etiquetas=[e for e in ((job.get("category") or {}).get("label"), job.get("contract_time"), job.get("contract_type")) if e],
        raw={k: job.get(k) for k in ("id", "title", "company", "location", "category", "created", "salary_min", "salary_max")},
    )


async def coletar_adzuna(
    http: httpx.AsyncClient, app_id: str, app_key: str, termos: list[str], max_paginas: int, **kw
) -> AsyncIterator[VagaColetada]:
    """Adzuna's free tier allows ~250 calls a day: few terms, a few pages each."""
    vistas: set[str] = set()
    for termo in termos:
        for pagina in range(1, max_paginas + 1):
            corpo = await pegar_json(
                http, ADZUNA.format(pagina=pagina),
                params={"app_id": app_id, "app_key": app_key, "what": termo, "results_per_page": ADZUNA_POR_PAGINA, "max_days_old": 30},
                **kw,
            )
            jobs = corpo.get("results") or []
            for job in jobs:
                if str(job["id"]) not in vistas:
                    vistas.add(str(job["id"]))
                    yield ler_adzuna(job)
            if len(jobs) < ADZUNA_POR_PAGINA:
                break
