"""What every source turns its postings into, and the HTTP plumbing they share."""

import asyncio
import random
import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from app.models import Fonte, Modalidade


@dataclass
class VagaColetada:
    fonte: Fonte
    id_externo: str
    url: str
    titulo: str
    empresa: str
    descricao: str
    modalidade: Modalidade = Modalidade.nao_informado
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = None
    publicada_em: datetime | None = None
    prazo: datetime | None = None
    etiquetas: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def assinatura(empresa: str, titulo: str) -> str:
    """"Stefanini Group" + "ANALISTA DESENVOLVEDOR PYTHON (Remoto)!" → "stefanini group|analista desenvolvedor python remoto".
    Ids change when a company reposts an opening; company and title usually don't."""

    def limpo(s: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento(s).lower()).split())

    return f"{limpo(empresa)}|{limpo(titulo)}"[:400]


def texto_limpo(texto: str | None) -> str:
    """Plain text from what sources send: HTML, entities, runs of blank lines."""
    t = re.sub(r"<(br|/p|/ul|/ol|/h\d)\s*/?>", "\n", texto or "", flags=re.I)
    t = re.sub(r"<li[^>]*>", "\n- ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    for de, para in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        t = t.replace(de, para)
    t = "\n".join(" ".join(linha.split()) for linha in t.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", t).strip()


TRANSITORIOS = {429, 500, 502, 503, 504}


async def pegar_json(
    http: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    tentativas: int = 4,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
):
    """GET with backoff on rate limits, server errors and dropped connections."""
    ultimo: Exception | None = None
    for i in range(tentativas):
        try:
            r = await http.get(url, params=params)
            if r.status_code not in TRANSITORIOS:
                r.raise_for_status()
                return r.json()
            ultimo = httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
        except httpx.TransportError as exc:
            ultimo = exc
        if i + 1 < tentativas:
            await sleep(min(2 * 2**i, 30) + random.uniform(0, 1))
    raise ultimo or RuntimeError(url)
