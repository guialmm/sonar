from app.encaixe import busca
from app.encaixe.busca import habilidades_na_vaga, mesmo_estado, pontuar
from app.encaixe.nivel import nivel_da_vaga, penalidade
from app.models import Fonte, Modalidade, Vaga


def test_nivel_pelo_titulo_e_etiquetas():
    casos = {
        "Desenvolvedor Python Sênior (Foco em IA)": "senior",
        "Estágio em Desenvolvimento de Software": "estagio",
        "Analista Desenvolvedor Java PL": "pleno",
        "Engenheiro de Software III": "senior",
        "Tech Lead Pleno - Backend": "lideranca",
        "Desenvolvedor(a) Back-end Júnior - Python": "junior",
        "Staff Software Engineer": "especialista",
        "DESENVOLVEDOR PYTHON": "nao_informado",
    }
    for titulo, nivel in casos.items():
        assert nivel_da_vaga(titulo) == nivel, titulo
    assert nivel_da_vaga("Backend Developer", ["PJ", "Júnior", "Remoto"]) == "junior"


def test_estagio_nao_ve_senior_mas_ve_junior_com_desconto():
    assert penalidade("estagio", "estagio") == 0
    assert penalidade("estagio", "junior") == 10
    assert penalidade("estagio", "senior") is None and penalidade("junior", "lideranca") is None


def test_estado_por_sigla_ou_nome():
    assert mesmo_estado("MG", "Minas Gerais", "Belo Horizonte")
    assert mesmo_estado("SP", None, "São Paulo, SP")
    assert not mesmo_estado("MG", "São Paulo", "Campinas")
    assert not mesmo_estado(None, "Minas Gerais", None)


def test_habilidades_com_simbolos():
    texto = "Buscamos experiência com C++, Node.js, CI/CD e PostgreSQL. Desejável React Native."
    assert habilidades_na_vaga(["C++", "Node.js", "CI/CD", "Postgres", "React", "Java"], texto) == ["C++", "Node.js", "CI/CD", "React"]
    assert habilidades_na_vaga(["Java"], "Vaga para JavaScript") == []


def vaga(**kw):
    base = dict(fonte=Fonte.gupy, titulo="Desenvolvedor Python Júnior", empresa="Acme", descricao="Python, FastAPI e SQL",
                etiquetas=[], modalidade=Modalidade.remoto, confianca=70, cidade=None, estado=None)
    return Vaga(**(base | kw))


PERFIL = {"senioridade": "estagio", "estado": "MG", "habilidades": [{"nome": "Python"}, {"nome": "FastAPI"}]}


def test_regras_descartam_e_pontuam():
    ok = pontuar(PERFIL, vaga(), 0.8)
    assert ok.motivos_descarte == [] and ok.habilidades == ["Python", "FastAPI"]
    assert pontuar(PERFIL, vaga(titulo="Desenvolvedor Python Sênior"), 0.9).motivos_descarte == ["nível senior"]
    longe = pontuar(PERFIL, vaga(modalidade=Modalidade.presencial, estado="São Paulo"), 0.9)
    assert longe.motivos_descarte == ["fora do estado"]
    assert pontuar(PERFIL, vaga(modalidade=Modalidade.hibrido, estado="Minas Gerais"), 0.9).motivos_descarte == []
    assert pontuar(PERFIL, vaga(confianca=20), 0.9).motivos_descarte == ["confiança baixa"]
    # Same meaning, more trust: ranks higher.
    assert pontuar(PERFIL, vaga(confianca=90), 0.8).pontos > ok.pontos


def test_consulta_de_texto_do_perfil():
    perfil = {"titulo": "Desenvolvedor back-end Python", "habilidades": [{"nome": "C++"}, {"nome": "Node.js"}, {"nome": "FastAPI"}]}
    # "C++" becomes "c": one letter would match nearly everything, so it is left to the semantic side.
    assert busca.consulta_texto(perfil) == "fastapi | nodejs"
    assert busca.consulta_texto({"habilidades": []}) is None
