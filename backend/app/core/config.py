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
        "mobile", "android", "ios", "react", "node", ".net", "c#", "php", "golang", "typescript", "cloud",
        "infraestrutura", "segurança da informação", "redes", "analista de sistemas", "engenheiro de dados",
        "cientista de dados", "analista de dados", "bi", "machine learning", "inteligência artificial", "ux",
        "product manager", "product owner", "scrum", "arquiteto de software", "sre", "testes", "sap",
        "salesforce", "help desk", "estágio desenvolvimento", "trainee tecnologia", "tech lead",
    ]
    # Community job boards kept as GitHub issues. Some went quiet years ago with issues still
    # open: they stay in, and the ghost-job detector marks those postings.
    github_repos: list[str] = [
        "backend-br/vagas", "frontendbr/vagas", "soujava/vagas-java", "CocoaHeadsBrasil/vagas",
        "react-brasil/vagas", "phpdevbr/vagas", "datascience-br/vagas", "androiddevbr/vagas",
        "vuejs-br/vagas", "qa-brasil/vagas", "flutterbr/vagas", "nodejsdevbr/vagas",
    ]
    github_token: str = ""  # optional locally (60 requests/hour without); GITHUB_TOKEN in Actions
    # Company career pages on applicant-tracking systems with public APIs: the posting straight
    # from the employer, no middleman. Board token → company name.
    greenhouse_empresas: dict[str, str] = {
        "stone": "Stone", "c6bank": "C6 Bank", "inter": "Banco Inter", "xpinc": "XP Inc.",
        "quintoandar": "QuintoAndar", "gympass": "Wellhub (Gympass)", "vtex": "VTEX", "ebanx": "EBANX",
        "jusbrasil": "Jusbrasil", "wildlifestudios": "Wildlife Studios", "rdstation": "RD Station",
        "btgpactual": "BTG Pactual", "getnet": "Getnet", "blip": "Blip", "flash": "Flash",
    }
    ashby_empresas: dict[str, str] = {"nubank": "Nubank", "warren": "Warren"}
    lever_empresas: dict[str, str] = {"ciandt": "CI&T", "neon": "Neon"}
    # Global employers: only their Brazilian openings are read (the API filters by country).
    smartrecruiters_empresas: dict[str, str] = {
        "BoschGroup": "Bosch", "Experian": "Serasa Experian", "Wise": "Wise", "NielsenIQ": "NielsenIQ", "ServiceNow": "ServiceNow",
    }
    # Remote boards: Himalayas lists ~6,000 openings open to Brazil, 20 a page, newest first.
    himalayas_paginas: int = 150
    # Adzuna (Brazilian aggregator): free key at developer.adzuna.com; skipped when empty.
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_termos: list[str] = ["desenvolvedor", "programador", "engenheiro de software", "analista de sistemas", "dados", "suporte técnico", "devops", "qa"]
    adzuna_paginas: int = 5

    # Browser origins allowed to call the API directly (LLM calls outlast a proxy's patience).
    cors_origens: list[str] = ["http://localhost:3003"]

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
