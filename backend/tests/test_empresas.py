import httpx

from app.coleta import empresas
from app.models import Fonte, Modalidade
from tests.conftest import fixture, sem_espera


def test_greenhouse_real_com_html_escapado():
    job = fixture("greenhouse-quintoandar.json")["jobs"][0]
    v = empresas.ler_greenhouse("quintoandar", "QuintoAndar", job)
    assert v.fonte == Fonte.greenhouse and v.id_externo == f"quintoandar:{job['id']}"
    assert v.empresa == "QuintoAndar" and v.url.startswith("https://job-boards.greenhouse.io/")
    assert "<" not in v.descricao and "&lt;" not in v.descricao and len(v.descricao) > 100
    assert v.pais == "Brasil" and v.publicada_em.tzinfo is not None


def test_ashby_real_separa_pais():
    jobs = fixture("ashby-nubank.json")["jobs"]
    vagas = [empresas.ler_ashby("nubank", "Nubank", j) for j in jobs]
    assert vagas[0].pais == "Brasil"
    assert all(v.url.startswith("https://jobs.ashbyhq.com/nubank/") for v in vagas)
    assert all(v.modalidade in set(Modalidade) for v in vagas)


def test_modalidade_pelo_texto():
    assert empresas.modalidade_do_texto("Engenheiro(a) de Software Sênior | Híbrido") == Modalidade.hibrido
    assert empresas.modalidade_do_texto("Remote - Brazil") == Modalidade.remoto
    assert empresas.modalidade_do_texto("São Paulo") == Modalidade.nao_informado


async def test_empresa_que_falha_nao_derruba_as_outras():
    def responder(request: httpx.Request):
        if "/quebrada/" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, json=fixture("greenhouse-quintoandar.json"))

    falhas: list[str] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        vagas = [v async for v in empresas.coletar_greenhouse(http, {"quebrada": "X", "quintoandar": "QuintoAndar"}, falhas, sleep=sem_espera)]
    assert falhas == ["quebrada"] and len(vagas) == 2 and {v.empresa for v in vagas} == {"QuintoAndar"}
