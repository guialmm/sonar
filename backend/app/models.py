import enum
from datetime import datetime

from sqlalchemy import Boolean, Computed, DateTime, Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from pgvector.sqlalchemy import Vector
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
        Index(
            "ix_vagas_embedding", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
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

    # Ghost-job detector (app/confianca.py): 0-100, the reasons behind it, and whether the
    # source still lists the posting.
    confianca: Mapped[int | None] = mapped_column(Integer, index=True)
    sinais: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)

    # Meaning of the posting for semantic search (gemini-embedding-001, 768 dims), and a hash of
    # the text it was computed from, so an edited posting gets a fresh vector.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    embedding_hash: Mapped[str | None] = mapped_column(String(40))

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
    # False when run for a subset (some terms, some boards): it can't tell what was taken down.
    completa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
