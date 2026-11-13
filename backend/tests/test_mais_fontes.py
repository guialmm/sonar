import httpx

from app.coleta import empresas, remotos
from app.models import Fonte, Modalidade
from tests.conftest import fixture, sem_espera


def test_lever_real_so_brasil():
    jobs = fixture("lever-ciandt.json")
    vagas = [empresas.ler_lever("ciandt", "CI&T", j) for j in jobs]
    assert vagas[2] is None  # the London opening
    v = vagas[0]
    assert v.fonte == Fonte.lever and v.id_externo.startswith("ciandt:") and v.pais == "Brasil"
    assert v.url.startswith("https://jobs.lever.co/ciandt/") and len(v.descricao) > 200 and "<" not in v.descricao
    assert v.publicada_em.tzinfo is not None


def test_smartrecruiters_real():
    v = empresas.ler_smartrecruiters("BoschGroup", "Bosch", fixture("smartrecruiters-bosch.json"))
    assert v.fonte == Fonte.smartrecruiters and v.pais == "Brasil" and v.cidade and v.estado
    assert v.url.startswith("https://jobs.smartrecruiters.com/BoschGroup/") and len(v.descricao) > 200
    assert v.modalidade in set(Modalidade)


async def test_smartrecruiters_lista_e_detalha():
    detalhe = fixture("smartrecruiters-bosch.json")

    def responder(request: httpx.Request):
        if request.url.path.endswith("/postings"):
            assert request.url.params["country"] == "br"
            return httpx.Response(200, json={"totalFound": 2, "content": [{"id": "1"}, {"id": "2"}]})
        return httpx.Response(200, json=detalhe | {"id": request.url.path.rsplit("/", 1)[1]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        vagas = [v async for v in empresas.coletar_smartrecruiters(http, {"BoschGroup": "Bosch"}, [], sleep=sem_espera)]
    assert [v.id_externo for v in vagas] == ["BoschGroup:1", "BoschGroup:2"]


async def test_lever_sem_quadro_conta_como_falha():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": False}))) as http:
        falhas: list[str] = []
        assert [v async for v in empresas.coletar_lever(http, {"naoexiste": "X"}, falhas, sleep=sem_espera)] == []
    assert falhas == ["naoexiste"]


def test_himalayas_real():
    vagas = [remotos.ler_himalayas(j) for j in fixture("himalayas-br.json")["jobs"]]
    assert all(v.fonte == Fonte.himalayas and v.modalidade == Modalidade.remoto for v in vagas)
    assert all(v.url.startswith("https://himalayas.app/companies/") and "?" not in v.url for v in vagas)
    assert all(v.publicada_em and v.prazo and v.prazo > v.publicada_em for v in vagas)


async def test_himalayas_para_na_ultima_pagina():
    paginas = {1: fixture("himalayas-br.json")["jobs"] * 7, 2: fixture("himalayas-br.json")["jobs"][:1]}  # 21, then 1

    def responder(request: httpx.Request):
        return httpx.Response(200, json={"jobs": paginas.get(int(request.url.params["page"]), [])[:20]})

    async def sem_pausa(_):
        pass

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        vagas = [v async for v in remotos.coletar_himalayas(http, 10, pausa=sem_pausa, sleep=sem_espera)]
    assert len(vagas) == 21


def test_remotive_so_quem_aceita_brasil():
    vagas = [remotos.ler_remotive(j) for j in fixture("remotive.json")["jobs"]]
    aceitas = [v for v in vagas if v]
    assert len(aceitas) == 5 and vagas[2] is None  # "USA" only
    assert all(v.url.startswith("https://remotive.com/") for v in aceitas)


def test_adzuna():
    job = {
        "id": "123", "title": "<strong>Desenvolvedor</strong> Python Remoto", "redirect_url": "https://www.adzuna.com.br/land/ad/123",
        "description": "Vaga para desenvolvedor Python com FastAPI.", "company": {"display_name": "Acme"},
        "location": {"area": ["Brasil", "São Paulo", "Campinas"]}, "created": "2026-11-10T12:00:00Z",
        "category": {"label": "Vagas em TI"},
    }
    v = remotos.ler_adzuna(job)
    assert v.titulo == "Desenvolvedor Python Remoto" and v.estado == "São Paulo" and v.cidade == "Campinas"
    assert v.modalidade == Modalidade.remoto and v.fonte == Fonte.adzuna
