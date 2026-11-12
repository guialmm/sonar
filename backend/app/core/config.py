from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://sonar:sonar@localhost:5436/sonar"

    # Collection: every source is a public page or API, read politely.
    agente_http: str = "Mozilla/5.0 (compatible; Sonar/0.1; +https://github.com/guialmm/sonar)"
    coleta_timeout_s: float = 30
    coleta_tentativas: int = 4
    # Gupy only searches by term. Tech first (see README); any field works the same way.
    gupy_termos: list[str] = [
        "desenvolvedor", "programador", "engenheiro de software", "software", "back-end", "front-end",
        "full stack", "python", "java", "javascript", "dados", "devops", "qa", "estágio ti", "suporte ti",
    ]

    # LLM (Gemini free tier; models tried in order when one is overloaded)
    gemini_api_key: str = ""
    # The lite model is the last resort: weaker, but almost never overloaded.
    gemini_modelos: list[str] = ["gemini-3.7-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]

    @field_validator("database_url")
    @classmethod
    def _asyncpg_url(cls, url: str) -> str:
        """Accept the plain URLs hosts hand out (Neon, Render):
        postgres://…?sslmode=require&channel_binding=require → asyncpg form."""
        parts = urlsplit(url)
        scheme = "postgresql+asyncpg" if parts.scheme in ("postgres", "postgresql") else parts.scheme
        query = dict(parse_qsl(parts.query))
        if (mode := query.pop("sslmode", None)) and mode != "disable":
            query["ssl"] = "require"
        query.pop("channel_binding", None)  # libpq-only option
        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
