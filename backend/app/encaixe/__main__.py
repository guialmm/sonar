"""Matching from the terminal.

    python -m app.encaixe vetores        # embed postings that have no vector yet
"""

import asyncio
import sys

from app.core.db import SessionLocal, engine
from app.encaixe import vetores
from app.llm import get_llm


async def main() -> None:
    comando = sys.argv[1] if len(sys.argv) > 1 else "vetores"
    async with SessionLocal() as session:
        if comando == "vetores":
            print(f"{await vetores.atualizar(session, get_llm())} vagas com vetor novo")
        else:
            sys.exit(f"comando desconhecido: {comando}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
