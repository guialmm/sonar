from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import update

from app.api import rotas
from app.coleta.base import VagaColetada
from app.coleta.servico import salvar
from app.llm import Resposta, Uso, get_llm
from app.main import app
from app.models import Fonte, Modalidade, Vaga
from tests.conftest import make_pdf
from tests.test_perfil import CV, PERFIL

PAGINAS = [CV]


class LLMFalso:
    """Profile extraction, embeddings and explanations, all canned; counts the calls."""

    def __init__(self):
        self.chamadas = {"estruturado": 0, "embeddings": 0}

    async def estruturado(self, *, sistema, conteudo, esquema):
        self.chamadas["estruturado"] += 1
        if esquema.__name__ == "Perfil":
            return Resposta(esquema.model_validate(PERFIL), Uso("falso", 1, 1, 0.1))
        ids = [int(x.split("]")[0]) for x in conteudo.split("[vaga ")[1:]]
        dados = {"avaliacoes": [
            {"vaga": i, "nota": 80, "resumo": "Encaixa.",
             "fortes": [{"texto": "Python", "trecho_vaga": "Precisamos de Python e FastAPI", "trecho_curriculo": "Experiencia com FastAPI, PostgreSQL e React"}],
             "lacunas": []}
            for i in ids
        ]}
        return Resposta(esquema.model_validate(dados), Uso("falso", 1, 1, 0.1))

    async def embeddings(self, textos, *, tipo):
        self.chamadas["embeddings"] += 1
        return [[0.1] * 768 for _ in textos]


@pytest.fixture
def llm():
    falso = LLMFalso()
    app.dependency_overrides[get_llm] = lambda: falso
    rotas.cache_explicacoes.clear()
    rotas.limite_curriculo = rotas.Limite(3, janela_s=600)
    rotas.limite_explicar = rotas.Limite(8, janela_s=600)
    yield falso
    app.dependency_overrides.clear()


@pytest.fixture
async def api():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def vagas(session, n=3):
    lista = [
        VagaColetada(fonte=Fonte.gupy, id_externo=str(i), url=f"https://x/{i}", titulo=f"Desenvolvedor Python Júnior {i}",
                     empresa="Acme", descricao="Precisamos de Python e FastAPI. " * 20, modalidade=Modalidade.remoto)
        for i in range(n)
    ]
    await salvar(session, lista, datetime.now(UTC))
    await session.execute(update(Vaga).values(confianca=80, embedding=[0.1] * 768))
    await session.execute(update(Vaga).where(Vaga.id_externo == "2").values(confianca=10))  # a ghost
    await session.commit()


async def test_curriculo_devolve_perfil_e_texto_sem_guardar(api, llm, session):
    r = await api.post("/api/curriculo", files={"arquivo": ("cv.pdf", make_pdf([CV]), "application/pdf")})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["perfil"]["titulo"] == PERFIL["titulo"] and corpo["habilidades_descartadas"] == ["Kubernetes"]
    assert "FastAPI" in corpo["paginas"][0]
    assert (await api.post("/api/curriculo", files={"arquivo": ("x.pdf", b"nada", "application/pdf")})).status_code == 422


async def test_encaixe_explicar_com_cache_e_vaga(api, llm, session):
    await vagas(session)
    perfil = {**PERFIL, "senioridade": "junior", "estado": "MG"}
    r = await api.post("/api/encaixe", json={"perfil": perfil})
    assert r.status_code == 200, r.text
    cands = r.json()
    assert len(cands) == 2  # the ghost (trust 10) never shows up
    assert cands[0]["afinidade"] == 100 and "Python" in cands[0]["habilidades"]

    ids = [c["vaga"]["id"] for c in cands]
    corpo = {"perfil": perfil, "paginas": PAGINAS, "vagas": ids}
    r = await api.post("/api/encaixe/explicar", json=corpo)
    assert r.status_code == 200, r.text
    assert [e["vaga_id"] for e in r.json()] == ids and r.json()[0]["fortes"][0]["texto"] == "Python"
    antes = llm.chamadas["estruturado"]
    assert (await api.post("/api/encaixe/explicar", json=corpo)).json() == r.json()
    assert llm.chamadas["estruturado"] == antes  # second time from cache

    v = (await api.get(f"/api/vagas/{ids[0]}")).json()
    assert v["descricao"].startswith("Precisamos") and v["confianca"] == 80
    assert (await api.get("/api/vagas/99999")).status_code == 404


async def test_resumo_e_limite_por_ip(api, llm, session):
    await vagas(session)
    r = (await api.get("/api/resumo")).json()
    assert r["lidas"] == 3 and r["escondidas"] == 1 and r["fontes"] == {"gupy": 3}
    for _ in range(3):
        await api.post("/api/curriculo", files={"arquivo": ("x.pdf", b"nada", "application/pdf")})
    r = await api.post("/api/curriculo", files={"arquivo": ("x.pdf", b"nada", "application/pdf")})
    assert r.status_code == 429


async def test_cors_so_para_o_site(api):
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = await api.options("/api/health", headers={"Origin": "http://localhost:3003", **pre})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3003"
    assert "access-control-allow-origin" not in (await api.options("/api/health", headers={"Origin": "https://x.example", **pre})).headers


async def test_encaixe_sem_cota_de_embeddings_usa_palavras_chave(api, llm, session):
    from app.llm import CotaDiaria

    await vagas(session)
    await session.execute(update(Vaga).values(embedding=None))  # nothing embedded yet
    await session.commit()

    async def sem_cota(textos, *, tipo):
        raise CotaDiaria("acabou")

    llm.embeddings = sem_cota
    r = await api.post("/api/encaixe", json={"perfil": {**PERFIL, "senioridade": "junior"}})
    assert r.status_code == 200 and len(r.json()) == 2  # found by "python", the ghost still out


async def test_explicacao_em_andamento_nao_e_paga_duas_vezes(api, llm, session):
    import asyncio

    await vagas(session)
    perfil = {**PERFIL, "senioridade": "junior"}
    ids = [c["vaga"]["id"] for c in (await api.post("/api/encaixe", json={"perfil": perfil})).json()]
    original = llm.estruturado

    async def devagar(**kw):
        await asyncio.sleep(0.05)
        return await original(**kw)

    llm.estruturado = devagar
    corpo = {"perfil": perfil, "paginas": PAGINAS, "vagas": ids}
    r1, r2 = await asyncio.gather(api.post("/api/encaixe/explicar", json=corpo), api.post("/api/encaixe/explicar", json=corpo))
    assert r1.json() == r2.json() and llm.chamadas["estruturado"] == 1
