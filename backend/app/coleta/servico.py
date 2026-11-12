"""Stores what a source returned and keeps the history the ghost-job detector reads."""

from collections.abc import AsyncIterable
from datetime import UTC, datetime

from sqlalchemy import literal_column, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.coleta.base import VagaColetada, assinatura
from app.models import Coleta, Fonte, Vaga

LOTE = 200


def _linha(v: VagaColetada, agora: datetime) -> dict:
    return {
        "fonte": v.fonte,
        "id_externo": v.id_externo,
        "url": v.url,
        "titulo": v.titulo[:300],
        "empresa": v.empresa[:300],
        "cidade": v.cidade,
        "estado": v.estado,
        "pais": v.pais,
        "modalidade": v.modalidade,
        "descricao": v.descricao,
        "etiquetas": v.etiquetas,
        "publicada_em": v.publicada_em,
        "prazo": v.prazo,
        "vista_primeiro_em": agora,
        "vista_ultimo_em": agora,
        "vezes_vista": 1,
        "assinatura": assinatura(v.empresa, v.titulo),
        "raw": v.raw,
    }


async def salvar(session: AsyncSession, vagas: list[VagaColetada], agora: datetime) -> int:
    """Upsert one batch; returns how many postings were new."""
    # One posting twice in a batch (pagination shifting under us) would make Postgres refuse
    # the whole upsert ("cannot affect row a second time"): keep the last copy.
    vagas = list({(v.fonte, v.id_externo): v for v in vagas}.values())
    if not vagas:
        return 0
    stmt = insert(Vaga).values([_linha(v, agora) for v in vagas])
    novo = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        index_elements=["fonte", "id_externo"],
        set_={
            # The source may edit a posting; what we observed first never changes.
            **{c: getattr(novo, c) for c in ("url", "titulo", "empresa", "cidade", "estado", "pais", "modalidade",
                                              "descricao", "etiquetas", "publicada_em", "prazo", "assinatura", "raw")},
            "vista_ultimo_em": novo.vista_ultimo_em,
            "vezes_vista": Vaga.vezes_vista + 1,
        },
    ).returning(literal_column("xmax = 0"))  # xmax = 0: the row was inserted, not updated
    resultado = await session.execute(stmt)
    return sum(1 for (inserida,) in resultado if inserida)


async def coletar_fonte(
    session: AsyncSession, fonte: Fonte, vagas: AsyncIterable[VagaColetada], completa: bool = True
) -> Coleta:
    """Runs one source to the end, in batches, and logs the run (with the error, if any)."""
    agora = datetime.now(UTC)
    coleta = Coleta(fonte=fonte, iniciada_em=agora, vistas=0, novas=0, completa=completa)
    session.add(coleta)
    await session.commit()
    coleta_id = coleta.id
    # Plain counters: after a rollback the ORM object is expired, and reading it in an
    # async session would try a lazy load (MissingGreenlet).
    vistas = novas = 0
    erro = None
    lote: list[VagaColetada] = []
    try:
        async for v in vagas:
            lote.append(v)
            if len(lote) >= LOTE:
                novas += await salvar(session, lote, agora)
                vistas += len(lote)
                await session.commit()
                lote = []
        novas += await salvar(session, lote, agora)
        vistas += len(lote)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        erro = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        await session.execute(
            update(Coleta)
            .where(Coleta.id == coleta_id)
            .values(vistas=vistas, novas=novas, erro=erro, terminada_em=datetime.now(UTC))
        )
        await session.commit()
    return await session.get(Coleta, coleta_id, populate_existing=True)
