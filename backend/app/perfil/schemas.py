"""What the model extracts from a CV. Every skill and experience carries the passage of the
CV that proves it, checked against the text before the profile is used."""

from typing import Literal

from pydantic import BaseModel, Field


class Evidencia(BaseModel):
    pagina: int = Field(description="Página do currículo, como marcada em [p. N]")
    trecho: str = Field(description="Cópia literal, de 3 a 20 palavras, do trecho do currículo que comprova")


class Habilidade(BaseModel):
    nome: str = Field(description="Nome canônico e curto: 'Python', 'PostgreSQL', 'React', 'Excel', 'Atendimento ao cliente'")
    categoria: Literal["linguagem", "framework", "banco_de_dados", "infra", "ia_dados", "ferramenta", "competencia", "outra"]
    nivel: Literal["basico", "intermediario", "avancado", "nao_informado"] = Field(
        description="Só o que o currículo diz ou mostra (ex.: 'avançado' escrito, ou anos de uso); na dúvida, nao_informado"
    )
    evidencia: Evidencia


class Experiencia(BaseModel):
    cargo: str
    organizacao: str
    tipo: Literal["emprego", "estagio", "freelance", "pesquisa", "voluntario", "outro"]
    inicio: str | None = Field(description="AAAA-MM, ou null se não informado")
    fim: str | None = Field(description="AAAA-MM, ou null se for o atual")
    evidencia: Evidencia


class Perfil(BaseModel):
    titulo: str = Field(description="Como a pessoa se apresentaria numa linha, ex.: 'Desenvolvedor back-end Python'")
    senioridade: Literal["estagio", "junior", "pleno", "senior", "especialista"] = Field(
        description="Pelo tempo e tipo de experiência profissional, não pelos projetos pessoais; quem ainda estuda e "
        "pede estágio ou júnior é 'estagio' ou 'junior'"
    )
    areas: list[str] = Field(description="1 a 4 áreas de atuação, ex.: 'back-end', 'dados', 'suporte', 'vendas'")
    resumo: str = Field(description="Duas frases sobre o que a pessoa faz e o que tem de mais forte")
    habilidades: list[Habilidade]
    experiencias: list[Experiencia]
    cidade: str | None
    estado: str | None = Field(description="Sigla da UF, se houver")
    idiomas: list[str] = Field(description="Ex.: 'Inglês avançado'")
    procura: list[str] = Field(description="Cargos ou tipos de vaga que a pessoa diz buscar; vazio se não disser")
