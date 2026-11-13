"use client";

import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { buscarEncaixe, type Candidata, type Curriculo, type Explicacao, explicar } from "@/lib/api";
import { lugar, SENIORIDADE } from "@/lib/formato";
import { esquecer, useCurriculo } from "@/lib/sessao";

import { Detalhe } from "./Detalhe";

const PRIMEIRAS = 8; // explained right away; the rest when clicked

export function Resultados() {
  const cv = useCurriculo();
  const [cands, setCands] = useState<Candidata[] | null>(null);
  const [notas, setNotas] = useState<Record<number, Explicacao>>({});
  const [explicando, setExplicando] = useState<Set<number>>(new Set());
  const [erros, setErros] = useState<Record<number, string>>({});
  const [selecionada, setSelecionada] = useState<number | null>(null);
  const [erro, setErro] = useState("");

  async function pedirExplicacao(c: Curriculo, ids: number[]) {
    setExplicando((s) => new Set([...s, ...ids]));
    try {
      const lista = await explicar(c.perfil, c.paginas, ids);
      setNotas((n) => ({ ...n, ...Object.fromEntries(lista.map((e) => [e.vaga_id, e])) }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Não deu para avaliar agora.";
      setErros((m) => ({ ...m, ...Object.fromEntries(ids.map((i) => [i, msg])) }));
    } finally {
      setExplicando((s) => new Set([...s].filter((i) => !ids.includes(i))));
    }
  }

  useEffect(() => {
    const c = cv;
    if (!c) return;
    buscarEncaixe(c.perfil)
      .then((lista) => {
        setCands(lista);
        if (lista.length) {
          setSelecionada(lista[0].vaga.id);
          pedirExplicacao(c, lista.slice(0, PRIMEIRAS).map((x) => x.vaga.id));
        }
      })
      .catch((e) => setErro(e instanceof Error ? e.message : "Não deu para buscar as vagas agora."));
  }, [cv]);

  // Explained postings by score; the rest keep the server's order (meaning, skills, level,
  // trust) below them.
  const ordenadas = useMemo(() => {
    if (!cands) return [];
    const posicao = new Map(cands.map((c, i) => [c.vaga.id, i]));
    return [...cands].sort((a, b) => {
      const na = notas[a.vaga.id]?.nota ?? -1;
      const nb = notas[b.vaga.id]?.nota ?? -1;
      return nb - na || posicao.get(a.vaga.id)! - posicao.get(b.vaga.id)!;
    });
  }, [cands, notas]);

  if (cv === undefined) return null;
  if (cv === null) {
    return (
      <div className="mx-auto max-w-xl px-5 py-24 text-center">
        <p className="font-display text-2xl font-bold">Primeiro, o currículo</p>
        <p className="mt-2 text-apagado">O resultado fica só na aba onde você mandou o PDF.</p>
        <Link href="/" className="mt-6 inline-block rounded-[10px] bg-verde px-6 py-3 font-semibold text-white">
          Mandar currículo
        </Link>
      </div>
    );
  }

  const p = cv.perfil;
  const atual = ordenadas.find((c) => c.vaga.id === selecionada);
  return (
    <div className="mx-auto max-w-[1440px] px-5 pb-16 sm:px-12">
      <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-2 border-b border-linha py-4 text-sm">
        <p>
          <b className="font-semibold">Seu perfil</b>{" "}
          <span className="text-apagado">
            {p.titulo} · {SENIORIDADE[p.senioridade] ?? p.senioridade}
            {p.cidade ? ` · ${p.cidade}${p.estado ? `, ${p.estado}` : ""}` : ""} · {p.habilidades.length} habilidades conferidas no currículo
          </span>
        </p>
        <Link href="/" onClick={esquecer} className="text-apagado underline-offset-4 hover:text-tinta hover:underline">
          Trocar currículo
        </Link>
      </div>

      {erro && <p className="py-10 text-ambar">{erro}</p>}
      {!cands && !erro && <p className="py-10 text-apagado">Procurando nas vagas abertas…</p>}
      {cands && !cands.length && <p className="py-10 text-apagado">Nenhuma vaga confiável encaixa no seu perfil hoje.</p>}

      {!!cands?.length && (
        <div className="grid gap-10 pt-7 lg:grid-cols-[minmax(340px,1fr)_1.35fr]">
          <section>
            <h2 className="mb-3.5 text-xs font-medium uppercase tracking-[0.12em] text-apagado">Para você hoje</h2>
            <LayoutGroup>
              <ul className="space-y-2">
                {ordenadas.map((c, i) => (
                  <motion.li
                    key={c.vaga.id}
                    layout
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ layout: { type: "spring", stiffness: 380, damping: 34 }, delay: Math.min(i, 10) * 0.05 }}
                  >
                    <button
                      onClick={() => {
                        setSelecionada(c.vaga.id);
                        if (!notas[c.vaga.id] && !explicando.has(c.vaga.id)) pedirExplicacao(cv, [c.vaga.id]);
                      }}
                      className={`grid w-full grid-cols-[44px_1fr_auto] items-center gap-3.5 rounded-[10px] border bg-cartao px-4 py-3.5 text-left transition-colors ${
                        selecionada === c.vaga.id ? "border-verde bg-[#fbfdfa]" : "border-linha hover:border-linha-forte"
                      }`}
                    >
                      <Nota explicacao={notas[c.vaga.id]} carregando={explicando.has(c.vaga.id)} />
                      <span className="min-w-0">
                        <b className="block truncate text-[15px] font-semibold">{c.vaga.titulo}</b>
                        <small className="block truncate text-[12.5px] text-apagado">
                          {c.vaga.empresa} · {lugar(c.vaga)}
                        </small>
                      </span>
                      <span className="text-xs tabular-nums text-apagado">confiança {c.vaga.confianca}</span>
                    </button>
                  </motion.li>
                ))}
              </ul>
            </LayoutGroup>
          </section>
          <section className="lg:sticky lg:top-6 lg:self-start">
            <AnimatePresence mode="wait">
              {atual && (
                <Detalhe
                  key={atual.vaga.id}
                  candidata={atual}
                explicacao={notas[atual.vaga.id]}
                explicando={explicando.has(atual.vaga.id)}
                  erro={erros[atual.vaga.id]}
                />
              )}
            </AnimatePresence>
          </section>
        </div>
      )}
    </div>
  );
}

function Nota({ explicacao, carregando }: { explicacao?: Explicacao; carregando: boolean }) {
  if (explicacao) {
    const boa = explicacao.nota >= 60;
    return (
      <motion.span
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 420, damping: 22 }}
        className={`grid size-11 place-items-center rounded-xl font-display text-[17px] font-bold tabular-nums ${
          boa ? "bg-verde-suave text-verde" : "bg-ambar-suave text-ambar"
        }`}
      >
        {explicacao.nota}
      </motion.span>
    );
  }
  return (
    <span className={`grid size-11 place-items-center rounded-xl bg-areia text-[11px] text-apagado ${carregando ? "animate-pulse" : ""}`}>
      {carregando ? "···" : "—"}
    </span>
  );
}
