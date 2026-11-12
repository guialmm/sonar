"""Career pages hosted on Greenhouse and Ashby, both with public job-board APIs. A posting
here comes from the employer itself, so it also confirms (or not) the same opening seen on
an aggregator: one of the ghost-job detector's checks."""

import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from app.coleta.base import VagaColetada, pegar_json, texto_limpo
from app.models import Fonte, Modalidade

log = logging.getLogger(__name__)

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{token}"

BRASIL = re.compile(r"\bbra[sz]il\b|\bSP\b|s[aã]o paulo|rio de janeiro|belo horizonte|curitiba|florian[oó]polis|porto alegre|recife|campinas", re.I)


def data(iso: str | None) -> datetime | None:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None


def modalidade_do_texto(*textos: str) -> Modalidade:
    alvo = " ".join(textos)
    if re.search(r"\bh[ií]brid|\bhybrid", alvo, re.I):
        return Modalidade.hibrido
    if re.search(r"\bremot[oe]|\bremote\b", alvo, re.I):
        return Modalidade.remoto
    if re.search(r"\bpresencial\b|\bon-?site\b|\bin-office\b", alvo, re.I):
        return Modalidade.presencial
    return Modalidade.nao_informado


def ler_greenhouse(token: str, empresa: str, job: dict) -> VagaColetada:
    lugar = (job.get("location") or {}).get("name") or ""
    titulo = " ".join(job["title"].split())
    descricao = texto_limpo(job.get("content"))
    partes = [p.strip() for p in re.split(r"[,;|/]| - ", lugar) if p.strip()]
    no_brasil = bool(BRASIL.search(lugar))
    cidade = next((p for p in partes if not re.fullmatch(r"(?i)bra[sz]il|remot[oe]|remote|h[ií]brido|hybrid", p)), None)
    # Title and location first: the description often lists every mode the company offers.
    modo = modalidade_do_texto(titulo, lugar)
    if modo == Modalidade.nao_informado:
        modo = modalidade_do_texto(descricao[:1500])
    return VagaColetada(
        fonte=Fonte.greenhouse,
        id_externo=f"{token}:{job['id']}",
        url=job["absolute_url"],
        titulo=titulo,
        empresa=empresa,
        descricao=descricao,
        modalidade=modo,
        cidade=cidade,
        pais="Brasil" if no_brasil else (partes[-1] if partes else None),
        publicada_em=data(job.get("first_published") or job.get("updated_at")),
        prazo=data(job.get("application_deadline")),
        etiquetas=[m["value"] for m in job.get("metadata") or [] if isinstance(m.get("value"), str)],
        raw={k: job.get(k) for k in ("id", "title", "location", "updated_at", "first_published", "departments")} | {"token": token},
    )


ASHBY_MODO = {"Remote": Modalidade.remoto, "Hybrid": Modalidade.hibrido, "OnSite": Modalidade.presencial}


def ler_ashby(token: str, empresa: str, job: dict) -> VagaColetada:
    endereco = ((job.get("address") or {}).get("postalAddress")) or {}
    modo = ASHBY_MODO.get(job.get("workplaceType") or "", Modalidade.remoto if job.get("isRemote") else Modalidade.nao_informado)
    return VagaColetada(
        fonte=Fonte.ashby,
        id_externo=f"{token}:{job['id']}",
        url=job["jobUrl"],
        titulo=" ".join(job["title"].split()),
        empresa=empresa,
        descricao=texto_limpo(job.get("descriptionHtml")) or (job.get("descriptionPlain") or "").strip(),
        modalidade=modo,
        cidade=endereco.get("addressLocality") or job.get("location"),
        estado=endereco.get("addressRegion"),
        pais="Brasil" if BRASIL.search(endereco.get("addressCountry") or job.get("location") or "") else endereco.get("addressCountry"),
        publicada_em=data(job.get("publishedAt")),
        etiquetas=[e for e in (job.get("department"), job.get("team"), job.get("employmentType")) if e],
        raw={k: job.get(k) for k in ("id", "title", "location", "workplaceType", "isRemote", "publishedAt", "department")} | {"token": token},
    )


async def coletar_greenhouse(http: httpx.AsyncClient, empresas: dict[str, str], falhas: list[str] | None = None, **kw) -> AsyncIterator[VagaColetada]:
    for token, nome in empresas.items():
        try:
            corpo = await pegar_json(http, GREENHOUSE.format(token=token), params={"content": "true"}, **kw)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("greenhouse %s falhou: %s", token, exc)
            if falhas is not None:
                falhas.append(token)
            continue
        for job in corpo.get("jobs") or []:
            yield ler_greenhouse(token, nome, job)


async def coletar_ashby(http: httpx.AsyncClient, empresas: dict[str, str], falhas: list[str] | None = None, **kw) -> AsyncIterator[VagaColetada]:
    for token, nome in empresas.items():
        try:
            corpo = await pegar_json(http, ASHBY.format(token=token), **kw)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("ashby %s falhou: %s", token, exc)
            if falhas is not None:
                falhas.append(token)
            continue
        for job in corpo.get("jobs") or []:
            if job.get("isListed", True):
                yield ler_ashby(token, nome, job)
