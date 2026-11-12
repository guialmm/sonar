import enum
from datetime import datetime

from sqlalchemy import Computed, DateTime, Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


def pg_enum(cls: type[enum.Enum]) -> Enum:
    return Enum(cls, name=cls.__name__.lower(), values_callable=lambda e: [m.value for m in e])


class Fonte(str, enum.Enum):
    gupy = "gupy"
    github = "github"  # community job boards kept as GitHub issues (backend-br/vagas…)
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"


class Modalidade(str, enum.Enum):
    remoto = "remoto"
    hibrido = "hibrido"
    presencial = "presencial"
    nao_informado = "nao_informado"


class Vaga(TimestampMixin, Base):
    """One job posting as a source shows it. The same job in two sources is two rows,
    linked later by `assinatura`; the history columns feed the ghost-job detector."""

    __tablename__ = "vagas"
    __table_args__ = (
        UniqueConstraint("fonte", "id_externo"),
        Index("ix_vagas_busca", "busca", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[Fonte] = mapped_column(pg_enum(Fonte), index=True)
    id_externo: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)

    titulo: Mapped[str] = mapped_column(String(300))
    empresa: Mapped[str] = mapped_column(String(300))
    cidade: Mapped[str | None] = mapped_column(String(120))
    estado: Mapped[str | None] = mapped_column(String(120))
    pais: Mapped[str | None] = mapped_column(String(80))
    modalidade: Mapped[Modalidade] = mapped_column(pg_enum(Modalidade), default=Modalidade.nao_informado)
    descricao: Mapped[str] = mapped_column(Text)
    # Labels the source attaches (GitHub boards: "Remoto", "Júnior", "PJ", "Python", "verificada").
    etiquetas: Mapped[list[str]] = mapped_column(ARRAY(String(80)), default=list, server_default="{}")

    publicada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    prazo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What the collector observed, independent of what the source claims.
    vista_primeiro_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vista_ultimo_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    vezes_vista: Mapped[int] = mapped_column(Integer, default=1)

    # Normalized "company | title": the same opening reposted under a new id shares it.
    assinatura: Mapped[str] = mapped_column(String(400), index=True)
    raw: Mapped[dict] = mapped_column(JSONB)

    # 'simple' (no stemming) works for Portuguese and English postings alike.
    busca: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', titulo || ' ' || empresa || ' ' || descricao)", persisted=True),
    )


class Coleta(Base):
    """One run of one source: how many postings it saw and how many were new."""

    __tablename__ = "coletas"

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[Fonte] = mapped_column(pg_enum(Fonte))
    iniciada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    terminada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vistas: Mapped[int] = mapped_column(Integer, default=0)
    novas: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text)
