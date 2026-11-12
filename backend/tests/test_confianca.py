from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.coleta.base import VagaColetada
from app.coleta.servico import salvar
from app.confianca import Contexto, avaliar, recalcular
from app.models import Coleta, Fonte, Vaga

AGORA = datetime(2026, 11, 12, 12, tzinfo=UTC)
DESCRICAO = "Responsabilidades: desenvolver APIs em Python e FastAPI, revisar código, escrever testes. " * 6


def nova(**kw) -> Vaga:
    base = dict(fonte=Fonte.gupy, titulo="Desenvolvedor Python", empresa="Acme", descricao=DESCRICAO, etiquetas=[],
                publicada_em=AGORA - timedelta(days=20), prazo=None)
    return Vaga(**(base | kw))


def codigos(sinais):
    return {s.codigo for s in sinais}


def test_vaga_normal_fica_na_base():
    nota, sinais = avaliar(nova(), Contexto(), AGORA)
    assert nota == 70 and sinais == []


def test_banco_de_talentos_antiga_e_republicada_desaba():
    v = nova(titulo="Banco de Talentos - Desenvolvedor", publicada_em=AGORA - timedelta(days=400))
    nota, sinais = avaliar(v, Contexto(republicacoes=5), AGORA)
    assert codigos(sinais) == {"banco_de_talentos", "antiga", "republicada"}
    assert nota == 0
    assert any("400 dias" in s.motivo for s in sinais) and any("6 vezes" in s.motivo for s in sinais)


def test_sinais_a_favor():
    v = nova(fonte=Fonte.greenhouse, publicada_em=AGORA - timedelta(days=3), descricao=DESCRICAO + " Salário: R$ 6.000")
    nota, sinais = avaliar(v, Contexto(), AGORA)
    assert codigos(sinais) == {"recente", "direto_da_empresa", "salario"} and nota == 90
    verificada = nova(fonte=Fonte.github, etiquetas=["PJ", "Verificada"])
    assert "verificada" in codigos(avaliar(verificada, Contexto(), AGORA)[1])


def test_prazo_vencido_descricao_curta_e_texto_padrao():
    v = nova(prazo=AGORA - timedelta(days=1), descricao="Venha fazer parte do nosso time!")
    nota, sinais = avaliar(v, Contexto(textos_iguais=12), AGORA)
    assert codigos(sinais) == {"prazo_vencido", "descricao_curta", "texto_padrao"} and nota == 15


def coletada(n: int, titulo="Dev Python") -> VagaColetada:
    return VagaColetada(fonte=Fonte.gupy, id_externo=str(n), url=f"https://x/{n}", titulo=titulo, empresa="Acme",
                        descricao=DESCRICAO + str(n), publicada_em=AGORA - timedelta(days=10))


async def test_recalcular_republicacao_e_vaga_que_saiu_da_fonte(session):
    ontem, hoje = AGORA - timedelta(days=1), AGORA
    await salvar(session, [coletada(1), coletada(2), coletada(3), coletada(4, "QA")], ontem)
    await salvar(session, [coletada(1), coletada(2), coletada(4, "QA")], hoje)  # 3 was taken down
    session.add_all([
        Coleta(fonte=Fonte.gupy, iniciada_em=hoje, vistas=3, novas=0, completa=True),
        Coleta(fonte=Fonte.gupy, iniciada_em=hoje + timedelta(hours=1), vistas=1, novas=0, completa=False),  # partial: ignored
    ])
    await session.commit()

    resumo = await recalcular(session, AGORA)
    vagas = {v.id_externo: v for v in (await session.scalars(select(Vaga))).all()}
    assert resumo["avaliadas"] == 4 and resumo["encerradas"] == 1
    assert vagas["3"].ativa is False and vagas["1"].ativa and vagas["4"].ativa
    # 1, 2 and 3 are the same opening posted three times; QA is unique.
    assert "republicada" in {s["codigo"] for s in vagas["1"].sinais}
    assert vagas["4"].sinais == [] and vagas["4"].confianca == 70
