"""Stored explanations of the demo profile (see app/exemplo.py)."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExplicacaoGuardada


async def ler(session: AsyncSession, perfil: str, vagas: list[int]) -> dict[int, dict]:
    linhas = (
        await session.scalars(select(ExplicacaoGuardada).where(ExplicacaoGuardada.perfil == perfil, ExplicacaoGuardada.vaga_id.in_(vagas)))
    ).all()
    return {e.vaga_id: e.dados for e in linhas}


async def guardar(session: AsyncSession, perfil: str, explicacoes: list[dict]) -> None:
    if not explicacoes:
        return
    stmt = insert(ExplicacaoGuardada).values([{"perfil": perfil, "vaga_id": e["vaga_id"], "dados": e} for e in explicacoes])
    await session.execute(stmt.on_conflict_do_update(index_elements=["perfil", "vaga_id"], set_={"dados": stmt.excluded.dados}))
    await session.commit()
