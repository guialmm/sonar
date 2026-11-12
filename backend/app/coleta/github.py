"""Community job boards on GitHub (backend-br/vagas, frontendbr/vagas…): each opening is an
issue, usually posted by whoever is hiring, titled "[Remoto] Cargo - Empresa" and labeled with
work mode, level, contract and stack. backend-br also labels the ones its maintainers checked
("verificada"), a trust signal the ghost-job detector uses."""

import logging
import re
from collections.abc import AsyncIterator
from datetime import datetime

import httpx

from app.coleta.base import VagaColetada, pegar_json, texto_limpo
from app.models import Fonte, Modalidade

log = logging.getLogger(__name__)

API = "https://api.github.com"
# The API sometimes stalls for minutes on one request and then answers in 0.5 s: give up
# fast and retry rather than wait.
TIMEOUT_S = 15
POR_PAGINA = 100
MAX_PAGINAS = 10

MODALIDADES = [
    (re.compile(r"\bremot[oa]\b|\bremote\b|home ?office|anywhere", re.I), Modalidade.remoto),
    (re.compile(r"\bh[ií]brid[oa]\b|\bhybrid\b", re.I), Modalidade.hibrido),
    (re.compile(r"\bpresencial\b|\bon-?site\b", re.I), Modalidade.presencial),
]
# Dependabot and maintenance issues share some of these repositories with the openings.
NAO_E_VAGA = re.compile(r"^(chore|fix|feat|docs|build|ci)(\(.+\))?:|\bbump\b|dependabot", re.I)


def data(iso: str | None) -> datetime | None:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None


def modalidade(titulo: str, etiquetas: list[str]) -> Modalidade:
    alvo = " ".join([titulo, *etiquetas])
    for padrao, m in MODALIDADES:
        if padrao.search(alvo):
            return m
    return Modalidade.nao_informado


def cargo_e_empresa(titulo: str) -> tuple[str, str]:
    """"[Remoto] Desenvolvedor(a) Backend Pleno - White Label - Mimix AI" → (cargo, "Mimix AI").
    "Senior Engineer na Google" and "Dev @ Acme" work too; otherwise the company is unknown."""
    sem_local = re.sub(r"^\s*(\[[^\]]*\]\s*)+", "", titulo).strip()
    partes = [p.strip() for p in re.split(r"\s+[-–—|]\s+", sem_local) if p.strip()]
    if len(partes) >= 2:
        return " - ".join(partes[:-1]), partes[-1]
    m = re.match(r"(.+?)\s+(?:na|no|at|@)\s+(.+)$", sem_local, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return sem_local, "Empresa não informada"


def local(titulo: str) -> str | None:
    """The bracketed place in "[São Paulo, SP] …", unless it is just the work mode."""
    m = re.match(r"^\s*\[([^\]]+)\]", titulo)
    if not m or modalidade(m.group(1), []) == Modalidade.remoto:
        return None
    return m.group(1).strip()


def ler(repo: str, issue: dict) -> VagaColetada | None:
    titulo = " ".join((issue.get("title") or "").split())
    etiquetas = [e["name"] for e in issue.get("labels") or [] if e.get("name")]
    if issue.get("pull_request") or not titulo or NAO_E_VAGA.search(titulo) or "dependencies" in etiquetas:
        return None
    cargo, empresa = cargo_e_empresa(titulo)
    lugar = local(titulo)
    return VagaColetada(
        fonte=Fonte.github,
        id_externo=f"{repo}#{issue['number']}",
        url=issue["html_url"],
        titulo=cargo,
        empresa=empresa,
        descricao=texto_limpo(issue.get("body")),
        modalidade=modalidade(titulo, etiquetas),
        cidade=lugar.split(",")[0].strip() if lugar else None,
        pais="Brasil",
        publicada_em=data(issue.get("created_at")),
        etiquetas=etiquetas,
        raw={k: issue.get(k) for k in ("number", "title", "created_at", "updated_at", "comments")}
        | {"repo": repo, "autor": (issue.get("user") or {}).get("login")},
    )


async def coletar(http: httpx.AsyncClient, repos: list[str], falhas: list[str] | None = None, **kw) -> AsyncIterator[VagaColetada]:
    """Every open posting of every board. A board that keeps failing is skipped (and listed
    in `falhas`): one stalled repository must not cost the other eleven."""
    for repo in repos:
        try:
            for pagina in range(1, MAX_PAGINAS + 1):
                issues = await pegar_json(
                    http, f"{API}/repos/{repo}/issues", params={"state": "open", "per_page": POR_PAGINA, "page": pagina}, **kw
                )
                for issue in issues:
                    if v := ler(repo, issue):
                        yield v
                if len(issues) < POR_PAGINA:
                    break
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("github %s falhou: %s", repo, exc)
            if falhas is not None:
                falhas.append(repo)
