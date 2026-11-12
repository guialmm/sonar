import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://sonar:sonar@localhost:5436/sonar_test")
os.environ["ENV"] = "test"

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402, F401
from app.core.db import Base, SessionLocal, engine  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(nome: str):
    return json.loads((FIXTURES / nome).read_text())


@pytest.fixture(scope="session", autouse=True)
async def schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db():
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session():
    async with SessionLocal() as s:
        yield s


async def sem_espera(_):
    pass
