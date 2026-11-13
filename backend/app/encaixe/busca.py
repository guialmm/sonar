"""From thousands of postings to the few worth the model's time.

Cheap, explainable steps first: semantic similarity (pgvector) for "what this person does",
skill overlap for the exact tools, then the hard rules (seniority, place, trust). Only the
top of this list goes to the model, which writes the reasons (app/encaixe/explicar.py)."""

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.coleta.base import sem_acento
from app.encaixe.nivel import nivel_da_vaga, penalidade
from app.models import Modalidade, Vaga

CANDIDATAS = 400  # nearest postings by meaning, before the rules
CONFIANCA_MINIMA = 40

UF = {
    "AC": "acre", "AL": "alagoas", "AP": "amapa", "AM": "amazonas", "BA": "bahia", "CE": "ceara", "DF": "distrito federal",
    "ES": "espirito santo", "GO": "goias", "MA": "maranhao", "MT": "mato grosso", "MS": "mato grosso do sul",
    "MG": "minas gerais", "PA": "para", "PB": "paraiba", "PR": "parana", "PE": "pernambuco", "PI": "piaui",
    "RJ": "rio de janeiro", "RN": "rio grande do norte", "RS": "rio grande do sul", "RO": "rondonia", "RR": "roraima",
    "SC": "santa catarina", "SP": "sao paulo", "SE": "sergipe", "TO": "tocantins",
}


def texto_perfil(p: dict) -> str:
    """What the profile is, as a query: who the person is and what they use."""
    habilidades = ", ".join(h["nome"] for h in p.get("habilidades", []))
    return "\n".join(
        x for x in (p.get("titulo"), f"Nível: {p.get('senioridade')}", f"Áreas: {', '.join(p.get('areas', []))}",
                    f"Procura: {', '.join(p.get('procura', []))}", f"Habilidades: {habilidades}", p.get("resumo")) if x
    )


def mesmo_estado(perfil_uf: str | None, estado_vaga: str | None, cidade_vaga: str | None) -> bool:
    if not perfil_uf:
        return False
    nome = UF.get(perfil_uf.upper(), perfil_uf.lower())
    alvo = sem_acento(f"{estado_vaga or ''} {cidade_vaga or ''}").lower()
    return nome in alvo or re.search(rf"\b{perfil_uf.lower()}\b", alvo) is not None


def habilidades_na_vaga(habilidades: list[str], texto: str) -> list[str]:
    alvo = sem_acento(texto).lower()
    achadas = []
    for h in habilidades:
        termo = re.escape(sem_acento(h).lower())
        # Word boundaries that also work for "C++", "Node.js", "CI/CD".
        if re.search(rf"(?<![a-z0-9]){termo}(?![a-z0-9])", alvo):
            achadas.append(h)
    return achadas


@dataclass
class Candidata:
    vaga: Vaga
    similaridade: float
    nivel: str
    habilidades: list[str] = field(default_factory=list)
    pontos: float = 0.0
    motivos_descarte: list[str] = field(default_factory=list)


def pontuar(perfil: dict, vaga: Vaga, similaridade: float) -> Candidata:
    nivel = nivel_da_vaga(vaga.titulo, vaga.etiquetas)
    c = Candidata(vaga, similaridade, nivel)
    distancia = penalidade(perfil.get("senioridade", "junior"), nivel)
    if distancia is None:
        c.motivos_descarte.append(f"nível {nivel}")
    if vaga.modalidade in (Modalidade.presencial, Modalidade.hibrido) and not mesmo_estado(perfil.get("estado"), vaga.estado, vaga.cidade):
        c.motivos_descarte.append("fora do estado")
    if (vaga.confianca or 0) < CONFIANCA_MINIMA:
        c.motivos_descarte.append("confiança baixa")
    nomes = [h["nome"] for h in perfil.get("habilidades", [])]
    c.habilidades = habilidades_na_vaga(nomes, f"{vaga.titulo}\n{vaga.descricao}\n{' '.join(vaga.etiquetas)}")
    # Meaning dominates; each exact tool adds a little, capped; level gap and doubt subtract.
    c.pontos = (
        100 * similaridade
        + min(len(c.habilidades), 8) * 2.5
        - (distancia or 0)
        - (10 if vaga.modalidade == Modalidade.nao_informado else 0)
        + ((vaga.confianca or 0) - 70) / 5
    )
    return c


async def candidatas(session: AsyncSession, perfil: dict, vetor: list[float], limite: int = 25) -> list[Candidata]:
    distancia = Vaga.embedding.cosine_distance(vetor)
    linhas = (
        await session.execute(
            select(Vaga, distancia).where(Vaga.ativa, Vaga.embedding.is_not(None)).order_by(distancia).limit(CANDIDATAS)
        )
    ).all()
    pontuadas = [pontuar(perfil, v, 1 - float(d)) for v, d in linhas]
    validas = [c for c in pontuadas if not c.motivos_descarte]
    validas.sort(key=lambda c: c.pontos, reverse=True)
    return validas[:limite]
