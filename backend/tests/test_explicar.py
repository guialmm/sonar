from app.citacoes.verificador import PaginaRef
from app.encaixe.busca import Candidata
from app.encaixe.explicar import explicar
from app.llm import Resposta, Uso
from app.models import Fonte, Modalidade, Vaga

CV = [PaginaRef(1, 0, "Currículo", 1, None, 1, "Experiência com FastAPI, PostgreSQL e React em projetos completos. Python avançado.")]


def candidata(id_, descricao):
    v = Vaga(id=id_, fonte=Fonte.gupy, titulo="Dev Python Júnior", empresa="Acme", descricao=descricao,
             modalidade=Modalidade.remoto, etiquetas=[])
    return Candidata(v, 0.8, "junior")


class LLMFalso:
    def __init__(self, dados):
        self.dados = dados

    async def estruturado(self, *, sistema, conteudo, esquema):
        self.conteudo = conteudo
        return Resposta(esquema.model_validate(self.dados), Uso("falso", 1, 1, 0.1))


def ponto(texto, vaga, cv=None):
    return {"texto": texto, "trecho_vaga": vaga, "trecho_curriculo": cv}


async def test_pontos_sem_citacao_conferida_sao_descartados():
    a = candidata(1, "Requisitos: experiência com FastAPI e PostgreSQL. Desejável conhecimento em Kubernetes e AWS.")
    b = candidata(2, "Buscamos pessoa desenvolvedora com React e testes automatizados.")
    llm = LLMFalso({"avaliacoes": [
        {"vaga": 1, "nota": 85, "resumo": "Encaixa bem.",
         "fortes": [ponto("Usa FastAPI", "experiência com FastAPI e PostgreSQL", "Experiência com FastAPI, PostgreSQL"),
                    ponto("Sabe Go", "experiência com Go em produção", "Go avançado")],  # invented on both sides
         "lacunas": [ponto("Não mostra Kubernetes", "Desejável conhecimento em Kubernetes e AWS")]},
        {"vaga": 2, "nota": 60, "resumo": "Parcial.", "fortes": [ponto("React", "desenvolvedora com React", "PostgreSQL e React")], "lacunas": []},
        {"vaga": 2, "nota": 99, "resumo": "repetida", "fortes": [], "lacunas": []},
        {"vaga": 999, "nota": 100, "resumo": "vaga que não existe", "fortes": [], "lacunas": []},
    ]})
    encaixes = await explicar(llm, CV, [a, b])
    assert [e.candidata.vaga.id for e in encaixes] == [1, 2]  # ordered by score, duplicate and unknown ignored
    assert [p["texto"] for p in encaixes[0].fortes] == ["Usa FastAPI"] and encaixes[0].descartados == 1
    assert encaixes[0].lacunas[0]["trecho_curriculo"] is None
    assert encaixes[1].nota == 60
    assert "[vaga 1]" in llm.conteudo and "[p. 1]" in llm.conteudo


async def test_sem_candidatas_nao_chama_o_modelo():
    assert await explicar(None, CV, []) == []
