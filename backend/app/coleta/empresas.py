"""Career pages hosted on Greenhouse, Ashby, Lever and SmartRecruiters, all with public
job-board APIs. A posting
here comes from the employer itself, so it also confirms (or not) the same opening seen on
an aggregator: one of the ghost-job detector's checks."""

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx

from app.coleta.base import VagaColetada, pegar_json, texto_limpo
from app.models import Fonte, Modalidade

log = logging.getLogger(__name__)

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{token}"
LEVER = "https://api.lever.co/v0/postings/{token}"
SMARTRECRUITERS = "https://api.smartrecruiters.com/v1/companies/{token}/postings"

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


LEVER_MODO = {"remote": Modalidade.remoto, "hybrid": Modalidade.hibrido, "on-site": Modalidade.presencial}


def ler_lever(token: str, empresa: str, job: dict) -> VagaColetada | None:
    """None for an opening outside Brazil: Lever boards of global companies list every office."""
    cat = job.get("categories") or {}
    lugares = cat.get("allLocations") or [cat.get("location") or ""]
    lugar = " / ".join(lugares)
    pais = job.get("country")
    no_brasil = pais == "BR" or bool(BRASIL.search(lugar))
    if pais and pais != "BR" and not no_brasil:
        return None
    titulo = " ".join(job["text"].split())
    listas = "\n\n".join(f"{x.get('text', '')}\n{texto_limpo(x.get('content'))}" for x in job.get("lists") or [])
    descricao = "\n\n".join(t for t in (job.get("descriptionPlain"), listas, job.get("additionalPlain")) if t).strip()
    modo = LEVER_MODO.get(job.get("workplaceType") or "", Modalidade.nao_informado)
    if modo == Modalidade.nao_informado:
        modo = modalidade_do_texto(titulo, lugar)
    cidade = next((p.strip() for p in re.split(r"[,/]", lugar) if p.strip() and not re.fullmatch(r"(?i)\s*(bra[sz]il|remot[oe]|remote|sp)\s*", p)), None)
    return VagaColetada(
        fonte=Fonte.lever,
        id_externo=f"{token}:{job['id']}",
        url=job["hostedUrl"],
        titulo=titulo,
        empresa=empresa,
        descricao=texto_limpo(descricao),
        modalidade=modo,
        cidade=cidade,
        pais="Brasil" if no_brasil else None,
        publicada_em=datetime.fromtimestamp(job["createdAt"] / 1000, UTC) if job.get("createdAt") else None,
        etiquetas=[e for e in (cat.get("team"), cat.get("department"), cat.get("commitment")) if e],
        raw={k: job.get(k) for k in ("id", "text", "categories", "createdAt", "workplaceType", "country")} | {"token": token},
    )


def ler_smartrecruiters(token: str, empresa: str, job: dict) -> VagaColetada:
    """`job` is the full posting (the list only has the header)."""
    lugar = job.get("location") or {}
    secoes = (job.get("jobAd") or {}).get("sections") or {}
    # The company blurb and the legal small print are the same in every posting: left out.
    descricao = "\n\n".join(texto_limpo((secoes.get(k) or {}).get("text")) for k in ("jobDescription", "qualifications"))
    modo = Modalidade.remoto if lugar.get("remote") else Modalidade.hibrido if lugar.get("hybrid") else Modalidade.presencial if lugar.get("city") else Modalidade.nao_informado
    return VagaColetada(
        fonte=Fonte.smartrecruiters,
        id_externo=f"{token}:{job['id']}",
        url=job.get("postingUrl") or job.get("applyUrl") or f"https://jobs.smartrecruiters.com/{token}/{job['id']}",
        titulo=" ".join(job["name"].split()),
        empresa=empresa,
        descricao=descricao.strip(),
        modalidade=modo,
        cidade=lugar.get("city"),
        estado=lugar.get("region"),
        pais="Brasil" if (lugar.get("country") or "").lower() == "br" else lugar.get("country"),
        publicada_em=data(job.get("releasedDate")),
        etiquetas=[x["label"] for x in (job.get("function"), job.get("experienceLevel"), job.get("typeOfEmployment")) if x and x.get("label")],
        raw={k: job.get(k) for k in ("id", "name", "location", "releasedDate", "function", "experienceLevel")} | {"token": token},
    )


async def coletar_lever(http: httpx.AsyncClient, empresas: dict[str, str], falhas: list[str] | None = None, **kw) -> AsyncIterator[VagaColetada]:
    for token, nome in empresas.items():
        try:
            corpo = await pegar_json(http, LEVER.format(token=token), params={"mode": "json"}, **kw)
            if not isinstance(corpo, list):
                raise ValueError("resposta sem lista de vagas")
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("lever %s falhou: %s", token, exc)
            if falhas is not None:
                falhas.append(token)
            continue
        for job in corpo:
            if (v := ler_lever(token, nome, job)) is not None:
                yield v


SR_POR_PAGINA = 100
SR_PARALELAS = 6


async def coletar_smartrecruiters(http: httpx.AsyncClient, empresas: dict[str, str], falhas: list[str] | None = None, **kw) -> AsyncIterator[VagaColetada]:
    """Brazilian openings only (the API filters by country), then each posting's full text."""
    limite = asyncio.Semaphore(SR_PARALELAS)

    async def detalhe(token: str, id_: str):
        async with limite:
            return await pegar_json(http, f"{SMARTRECRUITERS.format(token=token)}/{id_}", **kw)

    for token, nome in empresas.items():
        try:
            ids: list[str] = []
            while True:
                corpo = await pegar_json(http, SMARTRECRUITERS.format(token=token), params={"country": "br", "limit": SR_POR_PAGINA, "offset": len(ids)}, **kw)
                pagina = [j["id"] for j in corpo.get("content") or []]
                ids += pagina
                if len(pagina) < SR_POR_PAGINA or len(ids) >= (corpo.get("totalFound") or 0):
                    break
            for job in await asyncio.gather(*(detalhe(token, i) for i in ids)):
                yield ler_smartrecruiters(token, nome, job)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("smartrecruiters %s falhou: %s", token, exc)
            if falhas is not None:
                falhas.append(token)
