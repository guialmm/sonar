import httpx

from app.coleta import github
from app.models import Fonte, Modalidade
from tests.conftest import fixture, sem_espera


def test_cargo_e_empresa_dos_formatos_comuns():
    assert github.cargo_e_empresa("[Remoto] Desenvolvedor(a) Backend Pleno - White Label e Plataforma - Mimix AI") == (
        "Desenvolvedor(a) Backend Pleno - White Label e Plataforma",
        "Mimix AI",
    )
    assert github.cargo_e_empresa("[Belo Horizonte, Brasil] Senior Software Engineer, Full Stack na Google") == (
        "Senior Software Engineer, Full Stack",
        "Google",
    )
    assert github.cargo_e_empresa("[Remoto] It Jobs (Strider/ Micro 1)") == ("It Jobs (Strider/ Micro 1)", "Empresa não informada")


def test_modalidade_e_local():
    assert github.modalidade("[Híbrido] Sr Software Engineer - Stealth", []) == Modalidade.hibrido
    assert github.modalidade("Dev Python - Acme", ["PJ", "Remoto"]) == Modalidade.remoto
    assert github.local("[Belo Horizonte, Brasil] Engineer - Google") == "Belo Horizonte, Brasil"
    assert github.local("[Remoto] Dev - Acme") is None


def test_le_issues_reais_e_ignora_pull_requests_e_dependabot():
    issues = fixture("github-backend-br.json")
    vagas = [v for i in issues if (v := github.ler("backend-br/vagas", i))]
    assert len(vagas) == len(issues)
    v = vagas[0]
    assert v.fonte == Fonte.github and v.id_externo == f"backend-br/vagas#{issues[0]['number']}"
    assert v.url.startswith("https://github.com/backend-br/vagas/issues/") and v.etiquetas
    assert github.ler("soujava/vagas-java", {"number": 1, "title": "chore(deps): bump node-forge", "labels": [], "html_url": "x"}) is None
    assert github.ler("x/vagas", {**issues[0], "pull_request": {"url": "y"}}) is None


async def test_pagina_por_repositorio():
    chamadas = []

    def responder(request: httpx.Request):
        chamadas.append((request.url.path, request.url.params["page"]))
        base = fixture("github-backend-br.json")[0]
        n = github.POR_PAGINA if request.url.params["page"] == "1" and "backend" in request.url.path else 2
        return httpx.Response(200, json=[{**base, "number": i} for i in range(n)])

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        vagas = [v async for v in github.coletar(http, ["backend-br/vagas", "frontendbr/vagas"], sleep=sem_espera)]
    assert chamadas == [("/repos/backend-br/vagas/issues", "1"), ("/repos/backend-br/vagas/issues", "2"), ("/repos/frontendbr/vagas/issues", "1")]
    assert len(vagas) == github.POR_PAGINA + 2 + 2


async def test_repositorio_que_falha_nao_derruba_os_outros():
    def responder(request: httpx.Request):
        if "travado" in request.url.path:
            raise httpx.ReadTimeout("travou")
        return httpx.Response(200, json=[{**fixture("github-backend-br.json")[0], "number": 1}])

    falhas: list[str] = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        vagas = [v async for v in github.coletar(http, ["x/travado", "y/vagas"], falhas, sleep=sem_espera)]
    assert falhas == ["x/travado"] and [v.id_externo for v in vagas] == ["y/vagas#1"]
