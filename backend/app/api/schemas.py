"""What the API takes and returns. The server keeps no visitor data: the CV text and the
profile live in the browser, which sends them back with each request."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.perfil.schemas import Perfil


class Modelo(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CurriculoOut(BaseModel):
    perfil: dict
    paginas: list[str]  # the CV's own text, so later requests can check quotes against it
    habilidades_descartadas: list[str]
    evidencias_conferidas: int
    evidencias_total: int


class EncaixeIn(BaseModel):
    perfil: Perfil
    limite: int = Field(default=30, ge=1, le=60)


class VagaResumo(Modelo):
    id: int
    fonte: str
    titulo: str
    empresa: str
    cidade: str | None
    estado: str | None
    modalidade: str
    publicada_em: datetime | None
    confianca: int | None
    url: str


class Candidata(BaseModel):
    vaga: VagaResumo
    afinidade: int  # semantic similarity, 0-100: an ordering hint before the model explains
    nivel: str
    habilidades: list[str]


class ExplicarIn(BaseModel):
    perfil: Perfil
    paginas: list[str] = Field(min_length=1, max_length=6)
    vagas: list[int] = Field(min_length=1, max_length=8)


class Explicacao(BaseModel):
    vaga_id: int
    nota: int
    resumo: str
    fortes: list[dict]
    lacunas: list[dict]


class VagaOut(VagaResumo):
    descricao: str
    etiquetas: list[str]
    sinais: list[dict]
    ativa: bool


class Resumo(BaseModel):
    lidas: int
    escondidas: int
    fontes: dict[str, int]
    atualizada_em: datetime | None
