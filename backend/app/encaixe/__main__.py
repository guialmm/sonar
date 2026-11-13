"""Matching from the terminal.

    python -m app.encaixe vetores        # embed postings that have no vector yet
    python -m app.encaixe buscar ../dados-pessoais/perfil.json ../dados-pessoais/curriculo.pdf
"""

import asyncio
import json
import sys
from pathlib import Path

from app.core.db import SessionLocal, engine
from app.encaixe import vetores
from app.encaixe.busca import candidatas, texto_perfil
from app.encaixe.explicar import explicar
from app.llm import get_llm
from app.perfil.servico import ler_pdf


async def main() -> None:
    comando = sys.argv[1] if len(sys.argv) > 1 else "vetores"
    async with SessionLocal() as session:
        if comando == "vetores":
            print(f"{await vetores.atualizar(session, get_llm())} vagas com vetor novo")
        elif comando == "buscar":
            perfil = json.loads(Path(sys.argv[2]).read_text())
            curriculo = ler_pdf(Path(sys.argv[3]).read_bytes())
            llm = get_llm()
            [vetor] = await llm.embeddings([texto_perfil(perfil)], tipo="RETRIEVAL_QUERY")
            cands = await candidatas(session, perfil, vetor, limite=20)
            print(f"{len(cands)} candidatas depois das regras; pedindo a explicação…\n")
            for e in await explicar(llm, curriculo, cands):
                v = e.candidata.vaga
                print(f"{e.nota:3d}  {v.titulo} · {v.empresa} · {v.modalidade.value} · confiança {v.confianca}")
                print(f"     {e.resumo}")
                for p in e.fortes:
                    print(f"     + {p['texto']}")
                for p in e.lacunas:
                    print(f"     - {p['texto']}")
                print(f"     {v.url}\n")
        else:
            sys.exit(f"comando desconhecido: {comando}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
