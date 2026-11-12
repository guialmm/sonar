"""Extract a profile from a CV, from the terminal (the PDF is read and discarded).

    python -m app.perfil ../dados-pessoais/curriculo.pdf ../dados-pessoais/perfil.json
"""

import asyncio
import json
import sys
from pathlib import Path

from app.llm import get_llm
from app.perfil.servico import extrair_perfil, ler_pdf


async def main() -> None:
    entrada, saida = Path(sys.argv[1]), Path(sys.argv[2])
    r = await extrair_perfil(get_llm(), ler_pdf(entrada.read_bytes()))
    saida.write_text(json.dumps(r.perfil, ensure_ascii=False, indent=2))
    p = r.perfil
    print(f"{p['titulo']} · {p['senioridade']} · {', '.join(p['areas'])}")
    print(f"{len(p['habilidades'])} habilidades, {len(p['experiencias'])} experiências")
    print(f"evidências conferidas: {r.evidencias_conferidas}/{r.evidencias_total}; descartadas: {r.habilidades_descartadas or 'nenhuma'}")
    print(f"{r.modelo} · {r.segundos}s · salvo em {saida}")


if __name__ == "__main__":
    asyncio.run(main())
