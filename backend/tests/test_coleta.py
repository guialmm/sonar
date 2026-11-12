from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.coleta import gupy
from app.coleta.base import VagaColetada, assinatura, pegar_json, texto_limpo
from app.coleta.servico import coletar_fonte, salvar
from app.models import Coleta, Fonte, Modalidade, Vaga
from tests.conftest import fixture, sem_espera


def test_le_vaga_real_da_gupy():
    item = fixture("gupy-python.json")["data"][0]
    v = gupy.ler(item)
    assert v.fonte == Fonte.gupy and v.id_externo == str(item["id"])
    assert v.url.startswith("https://") and "?" not in v.url  # tracking parameters dropped
    assert v.modalidade in set(Modalidade) and v.publicada_em.tzinfo is not None
    assert v.titulo == " ".join(item["name"].split())


def test_assinatura_ignora_caixa_acento_e_pontuacao():
    assert assinatura("Stefanini Group", "ANALISTA DESENVOLVEDOR PYTHON (Remoto)!") == assinatura(
        "stefanini  group", "Analista Desenvolvedor Python — remoto"
    )
    assert assinatura("Ação", "Programação") == "acao|programacao"


def test_texto_limpo_tira_html():
    assert texto_limpo("<p>Requisitos:</p><ul><li>Python</li><li>SQL &amp; dados</li></ul>") == "Requisitos:\n\n- Python\n- SQL & dados"


def gupy_falso(paginas_por_termo: dict[str, list[list[dict]]], chamadas: list):
    def responder(request: httpx.Request):
        termo = request.url.params["jobName"]
        offset = int(request.url.params["offset"])
        chamadas.append((termo, offset))
        paginas = paginas_por_termo[termo]
        pagina = paginas[offset // gupy.POR_PAGINA] if offset // gupy.POR_PAGINA < len(paginas) else []
        return httpx.Response(200, json={"data": pagina, "pagination": {"total": 100}})

    return httpx.MockTransport(responder)


def item(n: int) -> dict:
    base = fixture("gupy-python.json")["data"][0]
    return {**base, "id": n, "name": f"Vaga {n}"}


async def test_pagina_ate_vir_pagina_incompleta_e_nao_repete_entre_termos():
    cheia = [item(i) for i in range(gupy.POR_PAGINA)]
    chamadas: list = []
    transporte = gupy_falso({"python": [cheia, [item(500), item(501)]], "dados": [[item(501), item(900)]]}, chamadas)
    async with httpx.AsyncClient(transport=transporte) as http:
        vagas = [v async for v in gupy.coletar(http, ["python", "dados"], sleep=sem_espera)]
    # The capped "total" (100) is ignored: page 2 is fetched, page 3 is not (page 2 came back short).
    assert chamadas == [("python", 0), ("python", 100), ("dados", 0)]
    ids = [v.id_externo for v in vagas]
    assert len(ids) == len(set(ids)) == gupy.POR_PAGINA + 3  # 501 found by both terms, kept once


async def test_tenta_de_novo_em_429_e_conexao_caida():
    respostas = [httpx.Response(429), httpx.ReadError("caiu"), httpx.Response(200, json={"ok": True})]

    def responder(request):
        r = respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        assert await pegar_json(http, "https://x.test", sleep=sem_espera) == {"ok": True}


def vaga(n: int, titulo="Dev Python", empresa="Acme") -> VagaColetada:
    return VagaColetada(fonte=Fonte.gupy, id_externo=str(n), url=f"https://acme.gupy.io/job/{n}", titulo=titulo,
                        empresa=empresa, descricao="Python e SQL", raw={})


async def test_historico_de_vistas(session):
    ontem = datetime.now(UTC) - timedelta(days=1)
    assert await salvar(session, [vaga(1), vaga(2)], ontem) == 2
    await session.commit()
    hoje = datetime.now(UTC)
    # Posting 2 comes back edited; 3 is the same opening reposted under a new id.
    assert await salvar(session, [vaga(2, titulo="Dev Python Sênior"), vaga(3)], hoje) == 1
    await session.commit()

    linhas = {v.id_externo: v for v in (await session.scalars(select(Vaga))).all()}
    assert linhas["2"].vezes_vista == 2 and linhas["2"].titulo == "Dev Python Sênior"
    assert linhas["2"].vista_primeiro_em == ontem and linhas["2"].vista_ultimo_em == hoje
    assert linhas["1"].vista_ultimo_em == ontem  # not seen today
    assert linhas["3"].assinatura == linhas["1"].assinatura  # the repost is recognizable


async def test_coleta_registra_erro_e_guarda_o_que_ja_veio(session):
    async def fonte_que_cai():
        for n in range(250):  # more than one batch, then the network fails
            yield vaga(n)
        raise httpx.ConnectError("sem rede")

    with pytest.raises(httpx.ConnectError):
        await coletar_fonte(session, Fonte.gupy, fonte_que_cai())
    c = (await session.scalars(select(Coleta))).one()
    assert c.erro.startswith("ConnectError") and c.terminada_em is not None
    assert c.vistas == 200 and c.novas == 200  # the first full batch was committed before the failure


async def test_mesma_vaga_duas_vezes_no_lote(session):
    assert await salvar(session, [vaga(7), vaga(7, titulo="Dev Python Pleno")], datetime.now(UTC)) == 1
    await session.commit()
    assert (await session.scalars(select(Vaga))).one().titulo == "Dev Python Pleno"
