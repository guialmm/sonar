"""CV → structured profile. The PDF is read in memory and never stored; the model extracts
skills and experiences, and each one must quote the CV to stay: a skill whose quote is not
in the text is dropped, so the matching never rests on something the person didn't write.

Personal data (name, e-mail, phone) is not part of the schema at all."""

import io
import time
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.citacoes.verificador import PaginaRef, Verificador
from app.llm import LLM
from app.perfil.schemas import Perfil

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGINAS = 6
VALIDAS = {"verificada", "corrigida", "aproximada"}

SISTEMA = """Você lê currículos para um buscador de vagas. Extraia o perfil profissional da pessoa.

Regras:
- Use só o que está escrito. Não deduza habilidades que o texto não menciona.
- Toda habilidade e toda experiência precisa de uma evidência: a página [p. N] e um trecho
  copiado literalmente do currículo (mesmas palavras, mesma ordem).
- Liste TODAS as habilidades que o currículo cita, em qualquer seção (resumo, experiências,
  projetos, lista de habilidades): linguagens, frameworks, bancos, infraestrutura, ferramentas,
  IA. Um currículo técnico costuma ter de 20 a 40. Uma por item, sem repetir.
- Habilidades com nome canônico e curto ("FastAPI", não "framework FastAPI para APIs").
  Inclua competências não técnicas quando o currículo as mostrar (atendimento, gestão de equipe).
- Senioridade pela experiência profissional real (empregos, estágios, freelas). Projetos pessoais
  e acadêmicos contam como habilidade, não como tempo de carreira.
- Não inclua nome, e-mail, telefone, endereço nem links pessoais.
Escreva em português do Brasil."""


class CurriculoInvalido(Exception):
    """Not a readable PDF, too big, or no text layer (a scan)."""


@dataclass
class Resultado:
    perfil: dict
    habilidades_descartadas: list[str]
    evidencias_conferidas: int
    evidencias_total: int
    modelo: str
    segundos: float


def ler_pdf(conteudo: bytes) -> list[PaginaRef]:
    if len(conteudo) > MAX_BYTES:
        raise CurriculoInvalido("O arquivo passa de 5 MB.")
    try:
        leitor = PdfReader(io.BytesIO(conteudo))
        paginas = [p.extract_text() or "" for p in leitor.pages[:MAX_PAGINAS]]
    except (PdfReadError, ValueError, KeyError) as exc:
        raise CurriculoInvalido("Não deu para ler o PDF.") from exc
    if sum(len(t.strip()) for t in paginas) < 200:
        raise CurriculoInvalido("O PDF não tem texto selecionável (parece uma imagem escaneada).")
    return [
        PaginaRef(global_n=i, documento_id=0, documento="Currículo", numero=i, arquivo=None, pagina_no_arquivo=i, texto=t)
        for i, t in enumerate(paginas, start=1)
    ]


async def extrair_perfil(llm: LLM, paginas: list[PaginaRef]) -> Resultado:
    conteudo = "\n\n".join(f"[p. {p.global_n}]\n{p.texto}" for p in paginas)
    inicio = time.monotonic()
    r = await llm.estruturado(sistema=SISTEMA, conteudo=conteudo, esquema=Perfil)
    perfil = r.dados.model_dump()

    verificador = Verificador(paginas)
    total = conferidas = 0

    def conferir(item: dict) -> bool:
        nonlocal total, conferidas
        ev = item["evidencia"]
        v = verificador.verificar(ev["pagina"], ev["trecho"])
        total += 1
        ok = v.status in VALIDAS
        conferidas += ok
        ev["status"] = v.status
        if v.pagina:
            ev["pagina"] = v.pagina
        return ok

    habilidades, descartadas, vistas = [], [], set()
    for h in perfil["habilidades"]:
        chave = h["nome"].strip().lower()
        if chave in vistas:
            continue
        vistas.add(chave)
        (habilidades if conferir(h) else descartadas).append(h)
    perfil["habilidades"] = habilidades
    # Experiences stay even when the quote slipped (dates and titles are easy to mangle),
    # marked so the UI can show they were not confirmed.
    for e in perfil["experiencias"]:
        conferir(e)

    return Resultado(
        perfil=perfil,
        habilidades_descartadas=[h["nome"] for h in descartadas],
        evidencias_conferidas=conferidas,
        evidencias_total=total,
        modelo=r.uso.modelo,
        segundos=round(time.monotonic() - inicio, 1),
    )
