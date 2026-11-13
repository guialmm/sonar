"""Embeddings of the postings, recomputed only when the text changes."""

import hashlib
import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.encaixe.busca import CONFIANCA_MINIMA
from app.llm import CotaDiaria
from app.models import Modalidade, Vaga

log = logging.getLogger(__name__)

MAX_DESCRICAO = 1000  # the opening says what the job is; the rest is mostly benefits and boilerplate
LOTE = 100

MODALIDADE = {Modalidade.remoto: "remoto", Modalidade.hibrido: "híbrido", Modalidade.presencial: "presencial"}


def texto_da_vaga(v: Vaga) -> str:
    lugar = ", ".join(p for p in (v.cidade, v.estado) if p)
    cabecalho = " · ".join(p for p in (v.titulo, v.empresa, MODALIDADE.get(v.modalidade, ""), lugar, ", ".join(v.etiquetas[:12])) if p)
    return f"{cabecalho}\n{v.descricao[:MAX_DESCRICAO]}"


def hash_de(texto: str) -> str:
    return hashlib.sha1(texto.encode()).hexdigest()


async def atualizar(session: AsyncSession, llm, limite: int | None = None) -> int:
    """Embeds active postings that have no vector yet or whose text changed. Low-trust ones are
    left out: the search drops them anyway, and the free tier counts every token."""
    vagas = (
        await session.scalars(
            select(Vaga)
            .where(Vaga.ativa, Vaga.confianca >= CONFIANCA_MINIMA, or_(Vaga.embedding.is_(None), Vaga.embedding_hash.is_(None)))
            # The free tier embeds ~1,000 texts a day: the freshest, most trustworthy first.
            .order_by(Vaga.publicada_em.desc().nulls_last(), Vaga.confianca.desc())
            .limit(limite)
        )
    ).all()
    # Edited postings: same row, new text.
    vagas += [
        v
        for v in (await session.scalars(select(Vaga).where(Vaga.ativa, Vaga.confianca >= CONFIANCA_MINIMA, Vaga.embedding_hash.is_not(None)))).all()
        if v.embedding_hash != hash_de(texto_da_vaga(v))
    ]
    feitas = 0
    for i in range(0, len(vagas), LOTE):
        lote = vagas[i : i + LOTE]  # the LLM layer paces the calls; this only spaces the commits
        textos = [texto_da_vaga(v) for v in lote]
        try:
            vetores = await llm.embeddings(textos, tipo="RETRIEVAL_DOCUMENT")
        except CotaDiaria:
            log.warning("vetores: cota diária acabou depois de %d; o resto fica para amanhã", feitas)
            break
        for v, t, vetor in zip(lote, textos, vetores, strict=True):
            v.embedding, v.embedding_hash = vetor, hash_de(t)
        await session.commit()  # progress survives a quota error halfway
        feitas += len(lote)
        log.info("vetores: %d de %d", feitas, len(vagas))
    return feitas
