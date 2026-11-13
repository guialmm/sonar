"""Why a posting fits (or doesn't), in the model's words but on the record: every point quotes
the posting, and every strength also quotes the CV. Both quotes are checked against the real
texts; a point whose quote isn't there is dropped before anyone reads it."""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.citacoes.verificador import PaginaRef, Verificador
from app.encaixe.busca import Candidata
from app.llm import LLM

VALIDAS = {"verificada", "corrigida", "aproximada"}
MAX_DESCRICAO = 1500  # requirements come early in a posting; shorter prompts answer much faster on the free tier


class Ponto(BaseModel):
    texto: str = Field(description="Uma frase curta, em português")
    trecho_vaga: str = Field(description="Cópia literal de 3 a 20 palavras do texto da vaga")
    trecho_curriculo: str | None = Field(description="Cópia literal de 3 a 20 palavras do currículo; null nas lacunas")


class Avaliacao(BaseModel):
    vaga: int = Field(description="O número da vaga, como em [vaga N]")
    nota: int = Field(description="0 a 100: quanto a pessoa atende ao que a vaga pede hoje")
    resumo: str = Field(description="Uma frase: por que vale (ou não) se candidatar")
    fortes: list[Ponto] = Field(description="2 a 4 requisitos da vaga que o currículo comprova")
    lacunas: list[Ponto] = Field(description="0 a 3 requisitos importantes que o currículo não mostra")


class Avaliacoes(BaseModel):
    avaliacoes: list[Avaliacao]


SISTEMA = """Você compara um currículo com vagas de emprego, como um recrutador honesto que ajuda
o candidato a escolher onde se candidatar.

Para cada vaga:
- nota: quanto a pessoa atende ao que a vaga pede HOJE. Requisitos obrigatórios pesam mais que
  desejáveis. Não dê nota alta por empolgação: 80+ só se quase tudo que é obrigatório estiver
  comprovado no currículo.
- fortes: requisitos da vaga que o currículo comprova. Cada um cita a vaga E o currículo, copiando
  os trechos literalmente.
- lacunas: requisitos importantes que o currículo não mostra. Cite só a vaga.
- Não invente: se não está escrito no currículo, é lacuna, não ponto forte.
Escreva em português do Brasil, direto, sem floreio."""


@dataclass
class Encaixe:
    candidata: Candidata
    nota: int
    resumo: str
    fortes: list[dict]
    lacunas: list[dict]
    descartados: int  # points dropped because a quote wasn't found


def montar_conteudo(curriculo: list[PaginaRef], cands: list[Candidata]) -> str:
    partes = ["CURRÍCULO", *(f"[p. {p.global_n}]\n{p.texto}" for p in curriculo), "", "VAGAS"]
    for c in cands:
        v = c.vaga
        partes.append(f"\n[vaga {v.id}] {v.titulo} · {v.empresa} · {v.modalidade.value}\n{v.descricao[:MAX_DESCRICAO]}")
    return "\n".join(partes)


async def explicar(llm: LLM, curriculo: list[PaginaRef], cands: list[Candidata]) -> list[Encaixe]:
    if not cands:
        return []
    r = await llm.estruturado(sistema=SISTEMA, conteudo=montar_conteudo(curriculo, cands), esquema=Avaliacoes)
    por_id = {c.vaga.id: c for c in cands}
    cv = Verificador(curriculo)
    encaixes: list[Encaixe] = []
    for a in r.dados.avaliacoes:
        c = por_id.get(a.vaga)
        if c is None or any(e.candidata is c for e in encaixes):
            continue  # a posting it wasn't given, or one it rated twice
        texto_vaga = f"{c.vaga.titulo}\n{c.vaga.descricao[:MAX_DESCRICAO]}"
        vaga = Verificador([PaginaRef(1, c.vaga.id, c.vaga.titulo, 1, None, 1, texto_vaga)])
        fortes, lacunas, descartados = [], [], 0
        for p in a.fortes:
            ok_vaga = vaga.verificar(1, p.trecho_vaga).status in VALIDAS
            ok_cv = bool(p.trecho_curriculo) and cv.verificar(1, p.trecho_curriculo).status in VALIDAS
            if ok_vaga and ok_cv:
                fortes.append(p.model_dump())
            else:
                descartados += 1
        for p in a.lacunas:
            if vaga.verificar(1, p.trecho_vaga).status in VALIDAS:
                lacunas.append(p.model_dump() | {"trecho_curriculo": None})
            else:
                descartados += 1
        encaixes.append(Encaixe(c, max(0, min(100, a.nota)), a.resumo, fortes, lacunas, descartados))
    encaixes.sort(key=lambda e: e.nota, reverse=True)
    return encaixes
