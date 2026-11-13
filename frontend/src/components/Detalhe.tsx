"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import { type Candidata, detalharVaga, type Explicacao, type Vaga } from "@/lib/api";
import { FONTE, lugar } from "@/lib/formato";

import { Arco } from "./Arco";

const entrar = { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -6 } };

/** One posting: the score, the quoted reasons, what's missing and why we trust it (or not).
 * The parent mounts one per posting (key = id) inside AnimatePresence, so state starts fresh. */
export function Detalhe({ candidata, explicacao, explicando, erro }: { candidata: Candidata; explicacao?: Explicacao; explicando: boolean; erro?: string }) {
  const [vaga, setVaga] = useState<Vaga | null>(null);
  const [aberta, setAberta] = useState(false);
  const id = candidata.vaga.id;

  useEffect(() => {
    let vivo = true;
    detalharVaga(id)
      .then((v) => vivo && setVaga(v))
      .catch(() => vivo && setVaga(null));
    return () => {
      vivo = false;
    };
  }, [id]);

  const v = candidata.vaga;
  const sinais = vaga?.sinais ?? [];
  return (
      <motion.article
        {...entrar}
        transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}
        className="rounded-[14px] border border-linha bg-cartao p-6 sm:p-8"
      >
        <div className="grid gap-8 sm:grid-cols-[1fr_auto] sm:items-start">
          <div>
            <p className="text-[13px] font-semibold uppercase tracking-[0.06em] text-verde">
              {v.empresa} · {lugar(v)}
            </p>
            <h1 className="mt-1.5 font-display text-[28px] font-bold leading-[1.1] tracking-tight sm:text-[32px]">{v.titulo}</h1>
            <p className="mt-3 max-w-[56ch] text-[17px] leading-relaxed text-[#3a4a41]">
              {explicacao?.resumo ?? (explicando ? "Lendo a vaga junto com o seu currículo…" : (erro ?? ""))}
            </p>
          </div>
          {explicacao ? (
            <Arco nota={explicacao.nota} />
          ) : (
            <div className="grid size-[140px] place-items-center rounded-full border-[10px] border-verde-suave text-center text-xs text-apagado">
              {explicando ? <span className="animate-pulse">avaliando</span> : "sem nota"}
            </div>
          )}
        </div>

        {explicacao && (
          <>
            <Secao titulo="Por que encaixa">
              {explicacao.fortes.length ? (
                explicacao.fortes.map((p, i) => <PontoCitado key={i} i={i} ponto={p} />)
              ) : (
                <p className="py-3 text-apagado">Nenhum requisito da vaga aparece comprovado no seu currículo.</p>
              )}
            </Secao>
            {!!explicacao.lacunas.length && (
              <Secao titulo="O que falta">
                {explicacao.lacunas.map((p, i) => (
                  <PontoCitado key={i} i={i} ponto={p} lacuna />
                ))}
              </Secao>
            )}
          </>
        )}

        <Secao titulo={`Confiança ${v.confianca ?? "—"}`}>
          <ul className="space-y-1.5 py-2">
            {sinais.map((s) => (
              <li key={s.codigo} className="flex gap-2.5 text-[15px] text-[#3a4a41]">
                <span className={`font-bold ${s.pontos > 0 ? "text-verde" : "text-ambar"}`}>{s.pontos > 0 ? "✓" : "!"}</span>
                {s.motivo}
              </li>
            ))}
            {vaga && !sinais.length && <li className="text-[15px] text-apagado">Nada fora do comum nesta vaga.</li>}
            <li className="text-[13px] text-apagado">Fonte: {FONTE[v.fonte] ?? v.fonte}</li>
          </ul>
        </Secao>

        {vaga && (
          <div className="mt-6">
            <button onClick={() => setAberta((a) => !a)} className="text-sm font-semibold text-verde underline-offset-4 hover:underline">
              {aberta ? "Esconder a descrição" : "Ler a descrição completa"}
            </button>
            <AnimatePresence initial={false}>
              {aberta && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <p className="mt-4 max-h-[50vh] overflow-y-auto whitespace-pre-line rounded-[10px] border border-linha bg-areia/50 p-5 text-[15px] leading-relaxed">
                    {vaga.descricao}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        <div className="mt-8 flex flex-wrap gap-3">
          <a
            href={v.url}
            target="_blank"
            rel="noreferrer"
            className="rounded-[10px] bg-verde px-6 py-3.5 font-semibold text-white transition-colors hover:bg-verde-escuro"
          >
            Abrir a vaga
          </a>
        </div>
      </motion.article>
  );
}

function Secao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="border-b border-linha pb-2.5 text-xs font-medium uppercase tracking-[0.14em] text-apagado">{titulo}</h2>
      {children}
    </section>
  );
}

function PontoCitado({ ponto, i, lacuna = false }: { ponto: Explicacao["fortes"][number]; i: number; lacuna?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 + i * 0.08, duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      className="grid gap-1 border-b border-linha py-3.5 last:border-0"
    >
      <b className={`font-semibold ${lacuna ? "text-ambar" : ""}`}>{ponto.texto}</b>
      <span className="text-[13.5px] leading-snug text-[#4d5a52]">
        <em className="mr-2 text-[11px] not-italic uppercase tracking-[0.1em] text-apagado">Vaga</em>“{ponto.trecho_vaga}”
      </span>
      {ponto.trecho_curriculo && (
        <span className="text-[13.5px] leading-snug text-[#4d5a52]">
          <em className="mr-2 text-[11px] not-italic uppercase tracking-[0.1em] text-apagado">Você</em>“{ponto.trecho_curriculo}”
        </span>
      )}
    </motion.div>
  );
}
