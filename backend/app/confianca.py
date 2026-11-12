"""Ghost-job detector: how much a posting looks like a real, open opening.

Plain rules, no model: every point added or taken comes with the sentence the reader sees,
so the score can be explained and tested. The history the collector keeps (first and last
time seen, reposts under new ids) is what makes most signals possible.

    python -m app.confianca      # re-score every posting after a collection
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.coleta.base import sem_acento
from app.models import Coleta, Fonte, Vaga

BASE = 70
BANCO_DE_TALENTOS = re.compile(r"banco de talentos|talent pool|cadastro reserva|vagas? futuras|oportunidades futuras", re.I)
SALARIO = re.compile(r"R\$\s?\d|sal[aá]rio:?\s*(de\s*)?R?\$?\s?\d|faixa salarial|\d{1,3}(\.\d{3})+\s*(a|-|até)\s*\d", re.I)
DIRETO_DA_EMPRESA = {Fonte.greenhouse, Fonte.ashby, Fonte.lever}


@dataclass
class Sinal:
    codigo: str
    pontos: int
    motivo: str


@dataclass
class Contexto:
    """What a posting can't tell about itself: how the rest of the data looks around it."""

    republicacoes: int = 0  # other postings, same source, same company and title
    textos_iguais: int = 0  # other postings of the same company with this exact description


def hash_texto(texto: str) -> str:
    normal = " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento(texto).lower()).split())
    return hashlib.sha1(normal.encode()).hexdigest()


def avaliar(v: Vaga, ctx: Contexto, agora: datetime) -> tuple[int, list[Sinal]]:
    sinais: list[Sinal] = []
    texto = f"{v.titulo}\n{v.descricao}"

    if BANCO_DE_TALENTOS.search(v.titulo) or BANCO_DE_TALENTOS.search(v.descricao[:600]):
        sinais.append(Sinal("banco_de_talentos", -40, "É um banco de talentos, não uma vaga aberta agora"))

    if v.publicada_em:
        dias = (agora - v.publicada_em).days
        if dias > 120:
            sinais.append(Sinal("antiga", -35, f"Publicada há {dias} dias e ainda aberta"))
        elif dias > 60:
            sinais.append(Sinal("antiga", -20, f"Publicada há {dias} dias"))
        elif dias <= 7:
            sinais.append(Sinal("recente", 5, "Publicada nesta semana" if dias > 1 else "Publicada há menos de dois dias"))

    if v.prazo and v.prazo < agora:
        sinais.append(Sinal("prazo_vencido", -30, f"O prazo de inscrição acabou em {v.prazo:%d/%m/%Y}"))

    if ctx.republicacoes >= 2:
        sinais.append(Sinal("republicada", -min(15 + 5 * ctx.republicacoes, 30),
                            f"A mesma empresa publicou este cargo {ctx.republicacoes + 1} vezes"))
    elif ctx.republicacoes == 1:
        sinais.append(Sinal("republicada", -5, "Há outra publicação igual da mesma empresa"))

    if len(v.descricao) < 400:
        sinais.append(Sinal("descricao_curta", -15, "Descrição curta, sem responsabilidades concretas"))

    if ctx.textos_iguais >= 5:
        sinais.append(Sinal("texto_padrao", -10, f"Texto idêntico ao de outras {ctx.textos_iguais} vagas da empresa"))

    if v.fonte in DIRETO_DA_EMPRESA:
        sinais.append(Sinal("direto_da_empresa", 10, "Publicada na página de carreira da própria empresa"))

    if "verificada" in (e.lower() for e in v.etiquetas):
        sinais.append(Sinal("verificada", 15, "Verificada pelos mantenedores da comunidade"))

    if SALARIO.search(texto):
        sinais.append(Sinal("salario", 5, "Informa a faixa salarial"))

    nota = max(0, min(100, BASE + sum(s.pontos for s in sinais)))
    return nota, sinais


async def recalcular(session: AsyncSession, agora: datetime | None = None) -> dict:
    """Scores every posting and marks the ones that left their source as closed."""
    agora = agora or datetime.now(UTC)
    vagas = (await session.scalars(select(Vaga))).all()

    por_assinatura: dict[tuple, int] = {}
    por_texto: dict[tuple, int] = {}
    hashes = {}
    for v in vagas:
        por_assinatura[(v.fonte, v.assinatura)] = por_assinatura.get((v.fonte, v.assinatura), 0) + 1
        h = hash_texto(v.descricao)
        hashes[v.id] = h
        por_texto[(v.empresa.lower(), h)] = por_texto.get((v.empresa.lower(), h), 0) + 1

    # A posting the last complete, successful run of its source didn't see has been taken down.
    # (A partial run, e.g. Gupy for one term, proves nothing about the rest.)
    ultima_ok = dict(
        (await session.execute(select(Coleta.fonte, func.max(Coleta.iniciada_em)).where(Coleta.erro.is_(None), Coleta.completa).group_by(Coleta.fonte))).all()
    )

    resumo = {"avaliadas": 0, "encerradas": 0, "baixa": 0}
    for v in vagas:
        ctx = Contexto(
            republicacoes=por_assinatura[(v.fonte, v.assinatura)] - 1,
            textos_iguais=por_texto[(v.empresa.lower(), hashes[v.id])] - 1,
        )
        nota, sinais = avaliar(v, ctx, agora)
        v.confianca = nota
        v.sinais = [s.__dict__ for s in sinais]
        corte = ultima_ok.get(v.fonte)
        v.ativa = not (corte and v.vista_ultimo_em < corte - timedelta(minutes=5))
        resumo["avaliadas"] += 1
        resumo["encerradas"] += not v.ativa
        resumo["baixa"] += nota < 40
    await session.commit()
    return resumo


if __name__ == "__main__":
    import asyncio

    from app.core.db import SessionLocal, engine

    async def main():
        async with SessionLocal() as s:
            print(await recalcular(s))
        await engine.dispose()

    asyncio.run(main())
