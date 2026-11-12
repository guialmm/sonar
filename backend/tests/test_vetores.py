from datetime import UTC, datetime

from sqlalchemy import select

from app.coleta.base import VagaColetada
from app.coleta.servico import salvar
from app.encaixe.vetores import atualizar, texto_da_vaga
from app.models import Fonte, Modalidade, Vaga


class LLMVetores:
    def __init__(self):
        self.lotes = []

    async def embeddings(self, textos, *, tipo):
        self.lotes.append((len(textos), tipo))
        return [[float(len(t) % 7)] * 768 for t in textos]


def coletada(n, descricao="Python e SQL"):
    return VagaColetada(fonte=Fonte.gupy, id_externo=str(n), url="u", titulo="Dev", empresa="Acme", descricao=descricao,
                        modalidade=Modalidade.remoto, etiquetas=["Python"])


async def test_so_recalcula_o_que_mudou(session):
    agora = datetime.now(UTC)
    await salvar(session, [coletada(1), coletada(2)], agora)
    await session.commit()
    llm = LLMVetores()
    assert await atualizar(session, llm) == 2
    assert await atualizar(session, llm) == 0  # nothing new
    await salvar(session, [coletada(2, "Python, SQL e Kubernetes")], agora)  # edited posting
    await session.commit()
    session.expire_all()
    assert await atualizar(session, llm) == 1
    assert llm.lotes == [(2, "RETRIEVAL_DOCUMENT"), (1, "RETRIEVAL_DOCUMENT")]
    v = (await session.scalars(select(Vaga).where(Vaga.id_externo == "1"))).one()
    assert len(v.embedding) == 768 and "remoto" in texto_da_vaga(v) and "Python" in texto_da_vaga(v)
