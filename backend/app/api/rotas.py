import asyncio
import hashlib
import json
from collections import OrderedDict
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.limite import Limite, ip
from app.api.schemas import Candidata, CurriculoOut, EncaixeIn, Explicacao, ExplicarIn, Resumo, VagaOut, VagaResumo
from app.citacoes.verificador import PaginaRef
from app.core.db import get_session
from app.encaixe import busca
from app.encaixe.explicar import explicar
from app.encaixe.nivel import nivel_da_vaga
from app.llm import LLMErro, LLMIndisponivel, get_llm
from app.models import Coleta, Vaga
from app.perfil.servico import CurriculoInvalido, extrair_perfil, ler_pdf

router = APIRouter(prefix="/api")
Sessao = Annotated[AsyncSession, Depends(get_session)]

# Free-tier LLM: a few dozen calls a day for everyone together.
limite_curriculo = Limite(3, janela_s=600)
limite_explicar = Limite(8, janela_s=600)
MAX_PAGINA = 8000


class Cache(OrderedDict):
    """Explanations already paid for: the same profile asking about the same posting again
    costs nothing. In memory, keyed by a hash: no profile is stored as such."""

    def __init__(self, maximo: int = 2000):
        super().__init__()
        self.maximo = maximo

    def guardar(self, chave, valor):
        self[chave] = valor
        self.move_to_end(chave)
        while len(self) > self.maximo:
            self.popitem(last=False)


cache_explicacoes = Cache()
# The same explanation already being computed (a page reload, a double click): wait for it
# instead of paying for a second model call.
em_andamento: dict[tuple, asyncio.Task] = {}


def chave_perfil(perfil: dict, paginas: list[str]) -> str:
    return hashlib.sha256(json.dumps([perfil, paginas], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def falha_llm(exc: Exception) -> HTTPException:
    if isinstance(exc, LLMIndisponivel):
        return HTTPException(503, "A IA gratuita está sobrecarregada agora. Tente de novo em instantes.")
    return HTTPException(502, "A IA não conseguiu responder. Tente de novo.")


@router.get("/health")
async def health() -> dict:
    return {"ok": True}


@router.get("/resumo", response_model=Resumo)
async def resumo(session: Sessao):
    ativas = Vaga.ativa.is_(True)
    lidas = await session.scalar(select(func.count()).select_from(Vaga).where(ativas))
    escondidas = await session.scalar(
        select(func.count()).select_from(Vaga).where(ativas, Vaga.confianca < busca.CONFIANCA_MINIMA)
    )
    fontes = dict((await session.execute(select(Vaga.fonte, func.count()).where(ativas).group_by(Vaga.fonte))).all())
    atualizada = await session.scalar(select(func.max(Coleta.terminada_em)).where(Coleta.erro.is_(None)))
    return Resumo(lidas=lidas, escondidas=escondidas, fontes={f.value: n for f, n in fontes.items()}, atualizada_em=atualizada)


@router.post("/curriculo", response_model=CurriculoOut)
async def curriculo(request: Request, arquivo: Annotated[UploadFile, File()], llm=Depends(get_llm)):
    """Reads the PDF in memory, returns the profile and the CV text, and forgets both."""
    if not limite_curriculo.permitir(ip(request)):
        raise HTTPException(429, "Muitos currículos seguidos. Espere alguns minutos.")
    conteudo = await arquivo.read()
    try:
        paginas = ler_pdf(conteudo)
        r = await extrair_perfil(llm, paginas)
    except CurriculoInvalido as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMErro as exc:
        raise falha_llm(exc) from exc
    return CurriculoOut(
        perfil=r.perfil,
        paginas=[p.texto for p in paginas],
        habilidades_descartadas=r.habilidades_descartadas,
        evidencias_conferidas=r.evidencias_conferidas,
        evidencias_total=r.evidencias_total,
    )


@router.post("/encaixe", response_model=list[Candidata])
async def encaixe(corpo: EncaixeIn, session: Sessao, llm=Depends(get_llm)):
    """Postings worth explaining for this profile, best first (rules and meaning, no model text)."""
    perfil = corpo.perfil.model_dump()
    try:
        [vetor] = await llm.embeddings([busca.texto_perfil(perfil)], tipo="RETRIEVAL_QUERY")
    except LLMIndisponivel:
        vetor = None  # keyword search alone still works when the embedding quota is gone
    cands = await busca.candidatas(session, perfil, vetor, limite=corpo.limite)
    return [
        Candidata(vaga=VagaResumo.model_validate(c.vaga), afinidade=round(100 * c.similaridade), nivel=c.nivel, habilidades=c.habilidades)
        for c in cands
    ]


@router.post("/encaixe/explicar", response_model=list[Explicacao])
async def explicar_vagas(corpo: ExplicarIn, request: Request, session: Sessao, llm=Depends(get_llm)):
    """Score and quoted reasons for a few postings. Cached per profile and posting."""
    perfil = corpo.perfil.model_dump()
    paginas_txt = [p[:MAX_PAGINA] for p in corpo.paginas]
    base = chave_perfil(perfil, paginas_txt)
    prontas = {i: cache_explicacoes[(base, i)] for i in corpo.vagas if (base, i) in cache_explicacoes}
    faltam = [i for i in corpo.vagas if i not in prontas]
    if faltam:
        vagas = (await session.scalars(select(Vaga).where(Vaga.id.in_(faltam)))).all()
        cands = [busca.Candidata(v, 0.0, nivel_da_vaga(v.titulo, v.etiquetas)) for v in vagas]
        curriculo = [PaginaRef(i, 0, "Currículo", i, None, i, t) for i, t in enumerate(paginas_txt, start=1)]
        chave = (base, tuple(sorted(faltam)))
        tarefa = em_andamento.get(chave)
        if tarefa is None:
            if not limite_explicar.permitir(ip(request)):
                raise HTTPException(429, "Muitas explicações seguidas. Espere alguns minutos.")
            tarefa = em_andamento[chave] = asyncio.create_task(explicar(llm, curriculo, cands))
            tarefa.add_done_callback(lambda _: em_andamento.pop(chave, None))
        try:
            encaixes = await asyncio.shield(tarefa)  # a client that leaves doesn't cancel it for the others
        except LLMErro as exc:
            raise falha_llm(exc) from exc
        for e in encaixes:
            ex = Explicacao(vaga_id=e.candidata.vaga.id, nota=e.nota, resumo=e.resumo, fortes=e.fortes, lacunas=e.lacunas)
            cache_explicacoes.guardar((base, ex.vaga_id), ex)
            prontas[ex.vaga_id] = ex
    return [prontas[i] for i in corpo.vagas if i in prontas]


@router.get("/vagas/{vaga_id}", response_model=VagaOut)
async def vaga(vaga_id: int, session: Sessao):
    v = await session.get(Vaga, vaga_id)
    if v is None:
        raise HTTPException(404, "vaga não encontrada")
    return v
