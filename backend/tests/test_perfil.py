import pytest

from app.llm import Resposta, Uso
from app.perfil.schemas import Perfil
from app.perfil.servico import CurriculoInvalido, extrair_perfil, ler_pdf
from tests.conftest import make_pdf

CV = (
    "Desenvolvedor Back-End Python\n"
    "Experiencia com FastAPI, PostgreSQL e React em projetos completos.\n"
    "Estagiario na Huawei de 2025-08 a 2026-01, em equipe multidisciplinar.\n"
    "Python (avancado), Docker e GitHub Actions no dia a dia.\n"
) * 3


def ev(trecho, pagina=1):
    return {"pagina": pagina, "trecho": trecho}


class LLMFalso:
    def __init__(self, dados):
        self.dados = dados
        self.conteudo = None

    async def estruturado(self, *, sistema, conteudo, esquema):
        self.conteudo = conteudo
        return Resposta(esquema.model_validate(self.dados), Uso("falso", 10, 5, 0.1))


PERFIL = {
    "titulo": "Desenvolvedor back-end Python",
    "senioridade": "junior",
    "areas": ["back-end"],
    "resumo": "Faz APIs.",
    "habilidades": [
        {"nome": "Python", "categoria": "linguagem", "nivel": "avancado", "evidencia": ev("Python (avancado), Docker e GitHub Actions")},
        {"nome": "FastAPI", "categoria": "framework", "nivel": "nao_informado", "evidencia": ev("Experiencia com FastAPI, PostgreSQL e React", pagina=7)},
        {"nome": "python", "categoria": "linguagem", "nivel": "avancado", "evidencia": ev("Python (avancado)")},  # repeated
        {"nome": "Kubernetes", "categoria": "infra", "nivel": "avancado", "evidencia": ev("Kubernetes em producao com Helm")},  # invented
    ],
    "experiencias": [
        {"cargo": "Estagiario", "organizacao": "Huawei", "tipo": "estagio", "inicio": "2025-08", "fim": "2026-01",
         "evidencia": ev("Estagiario na Huawei de 2025-08 a 2026-01")},
    ],
    "cidade": "Santa Rita do Sapucai",
    "estado": "MG",
    "idiomas": ["Ingles avancado"],
    "procura": [],
}


async def test_habilidade_sem_evidencia_no_curriculo_e_descartada():
    paginas = ler_pdf(make_pdf([CV]))
    llm = LLMFalso(PERFIL)
    r = await extrair_perfil(llm, paginas)
    assert [h["nome"] for h in r.perfil["habilidades"]] == ["Python", "FastAPI"]
    assert r.habilidades_descartadas == ["Kubernetes"]
    # Right quote, wrong page number: kept and pointed at the right page.
    fastapi = r.perfil["habilidades"][1]["evidencia"]
    assert fastapi["status"] == "corrigida" and fastapi["pagina"] == 1
    assert r.perfil["experiencias"][0]["evidencia"]["status"] == "verificada"
    assert (r.evidencias_conferidas, r.evidencias_total) == (3, 4)
    assert "[p. 1]" in llm.conteudo


def test_esquema_nao_tem_dados_pessoais():
    campos = set(Perfil.model_fields)
    assert not campos & {"nome", "email", "telefone", "endereco", "linkedin"}


def test_pdf_invalido_grande_ou_escaneado():
    with pytest.raises(CurriculoInvalido, match="ler o PDF"):
        ler_pdf(b"isto nao e um pdf")
    with pytest.raises(CurriculoInvalido, match="5 MB"):
        ler_pdf(b"0" * (5 * 1024 * 1024 + 1))
    with pytest.raises(CurriculoInvalido, match="escaneada"):
        ler_pdf(make_pdf(["   "]))
