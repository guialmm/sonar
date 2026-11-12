"""Embeddings of the postings, recomputed only when the text changes."""

import hashlib

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Modalidade, Vaga

MAX_DESCRICAO = 1800  # the opening of a posting says what it is; the rest is benefits and boilerplate
LOTE = 100

MODALIDADE = {Modalidade.remoto: "remoto", Modalidade.hibrido: "híbrido", Modalidade.presencial: "presencial"}


def texto_da_vaga(v: Vaga) -> str:
    lugar = ", ".join(p for p in (v.cidade, v.estado) if p)
    cabecalho = " · ".join(p for p in (v.titulo, v.empresa, MODALIDADE.get(v.modalidade, ""), lugar, ", ".join(v.etiquetas[:12])) if p)
    return f"{cabecalho}\n{v.descricao[:MAX_DESCRICAO]}"


def hash_de(texto: str) -> str:
    return hashlib.sha1(texto.encode()).hexdigest()


async def atualizar(session: AsyncSession, llm, limite: int | None = None) -> int:
    """Embeds active postings that have no vector yet or whose text changed. Returns how many."""
    vagas = (
        await session.scalars(
            select(Vaga).where(Vaga.ativa, or_(Vaga.embedding.is_(None), Vaga.embedding_hash.is_(None))).order_by(Vaga.id).limit(limite)
        )
    ).all()
    # Edited postings: same row, new text.
    vagas += [
        v
        for v in (await session.scalars(select(Vaga).where(Vaga.ativa, Vaga.embedding_hash.is_not(None)))).all()
        if v.embedding_hash != hash_de(texto_da_vaga(v))
    ]
    feitas = 0
    for i in range(0, len(vagas), LOTE):
        lote = vagas[i : i + LOTE]
        textos = [texto_da_vaga(v) for v in lote]
        vetores = await llm.embeddings(textos, tipo="RETRIEVAL_DOCUMENT")
        for v, t, vetor in zip(lote, textos, vetores, strict=True):
            v.embedding, v.embedding_hash = vetor, hash_de(t)
        await session.commit()  # progress survives a quota error halfway
        feitas += len(lote)
    return feitas
