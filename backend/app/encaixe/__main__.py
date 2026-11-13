"""Matching from the terminal.

    python -m app.encaixe vetores        # embed postings that have no vector yet
    python -m app.encaixe buscar ../dados-pessoais/perfil.json ../dados-pessoais/curriculo.pdf
    python -m app.encaixe aquecer        # explain today's best postings for the demo profile ahead
"""

import asyncio
import json
import sys
from pathlib import Path

from app.core.db import SessionLocal, engine
from app import exemplo
from app.citacoes.verificador import PaginaRef
from app.encaixe import guardadas, vetores
from app.encaixe.busca import candidatas, texto_perfil
from app.encaixe.explicar import explicar
from app.llm import LLMIndisponivel, get_llm
from app.perfil.servico import ler_pdf


AQUECER = 12  # what the demo shows first
LOTE = 4


async def aquecer(session, llm) -> str:
    """Explains the demo profile's best postings now, so the "see an example" button is instant."""
    e = exemplo.exemplo()
    if e is None:
        return "sem exemplo"
    perfil, paginas = exemplo.normalizar(e["perfil"], e["paginas"])
    base = exemplo.chave(perfil, paginas)
    try:
        [vetor] = await llm.embeddings([texto_perfil(perfil)], tipo="RETRIEVAL_QUERY")
    except LLMIndisponivel:
        vetor = None
    cands = await candidatas(session, perfil, vetor, limite=AQUECER)
    prontas = await guardadas.ler(session, base, [c.vaga.id for c in cands])
    faltam = [c for c in cands if c.vaga.id not in prontas]
    curriculo = [PaginaRef(i, 0, "Currículo", i, None, i, t) for i, t in enumerate(paginas, start=1)]
    feitas = 0
    for i in range(0, len(faltam), LOTE):
        try:
            encaixes = await explicar(llm, curriculo, faltam[i : i + LOTE])
        except LLMIndisponivel:
            break  # the rest tomorrow, or on click
        await guardadas.guardar(session, base, [
            {"vaga_id": x.candidata.vaga.id, "nota": x.nota, "resumo": x.resumo, "fortes": x.fortes, "lacunas": x.lacunas}
            for x in encaixes
        ])
        feitas += len(encaixes)
    return f"exemplo: {len(prontas)} já prontas, {feitas} novas de {len(cands)}"


async def main() -> None:
    comando = sys.argv[1] if len(sys.argv) > 1 else "vetores"
    async with SessionLocal() as session:
        if comando == "vetores":
            print(f"{await vetores.atualizar(session, get_llm())} vagas com vetor novo")
        elif comando == "buscar":
            perfil = json.loads(Path(sys.argv[2]).read_text())
            curriculo = ler_pdf(Path(sys.argv[3]).read_bytes())
            llm = get_llm()
            try:
                [vetor] = await llm.embeddings([texto_perfil(perfil)], tipo="RETRIEVAL_QUERY")
            except LLMIndisponivel:
                vetor = None
                print("(sem cota de embeddings hoje: só palavras-chave)")
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
        elif comando == "aquecer":
            print(await aquecer(session, get_llm()))
        else:
            sys.exit(f"comando desconhecido: {comando}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
