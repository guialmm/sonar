"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { curriculoExemplo, enviarCurriculo } from "@/lib/api";
import { guardar } from "@/lib/sessao";

// What actually happens while the model reads the CV, shown in order instead of a spinner.
const ETAPAS = ["Lendo o PDF", "Separando experiências e habilidades", "Conferindo cada habilidade no texto do currículo", "Quase lá"];

export function Envio() {
  const router = useRouter();
  const entrada = useRef<HTMLInputElement>(null);
  const [estado, setEstado] = useState<"parado" | "arrastando" | "lendo" | "erro">("parado");
  const [etapa, setEtapa] = useState(0);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (estado !== "lendo") return;
    const t = setInterval(() => setEtapa((e) => Math.min(e + 1, ETAPAS.length - 1)), 9000);
    return () => clearInterval(t);
  }, [estado]);

  async function verExemplo() {
    try {
      guardar(await curriculoExemplo());
      router.push("/vagas");
    } catch {
      setEstado("erro");
      setErro("O exemplo não está disponível agora.");
    }
  }

  async function enviar(arquivo?: File | null) {
    if (!arquivo) return;
    if (arquivo.type !== "application/pdf") {
      setEstado("erro");
      setErro("Mande o currículo em PDF.");
      return;
    }
    setEtapa(0);
    setEstado("lendo");
    try {
      guardar(await enviarCurriculo(arquivo));
      router.push("/vagas");
    } catch (e) {
      setEstado("erro");
      setErro(e instanceof Error ? e.message : "Não deu certo agora.");
    }
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (estado !== "lendo") setEstado("arrastando");
      }}
      onDragLeave={() => estado === "arrastando" && setEstado("parado")}
      onDrop={(e) => {
        e.preventDefault();
        enviar(e.dataTransfer.files[0]);
      }}
      className={`rounded-[14px] border bg-cartao p-7 transition-colors ${
        estado === "arrastando" ? "border-verde bg-verde-suave/40" : "border-linha"
      }`}
    >
      <AnimatePresence mode="wait" initial={false}>
        {estado === "lendo" ? (
          <motion.div key="lendo" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="py-2">
            <p className="font-display text-xl font-bold">Lendo seu currículo</p>
            <ol className="mt-5 space-y-3">
              {ETAPAS.map((t, i) => (
                <li key={t} className={`flex items-center gap-3 text-[15px] transition-colors ${i <= etapa ? "text-tinta" : "text-apagado/60"}`}>
                  <span
                    className={`grid size-5 place-items-center rounded-full border text-[11px] transition-colors ${
                      i < etapa ? "border-verde bg-verde text-white" : i === etapa ? "border-verde text-verde" : "border-linha-forte"
                    }`}
                  >
                    {i < etapa ? "✓" : ""}
                  </span>
                  {t}
                  {i === etapa && <span className="ml-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-verde" />}
                </li>
              ))}
            </ol>
            <p className="mt-5 text-sm text-apagado">A IA gratuita às vezes leva um minuto. O PDF não fica guardado.</p>
          </motion.div>
        ) : (
          <motion.div key="parado" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <p className="font-display text-xl font-bold">Mande seu currículo</p>
            <p className="mt-1.5 text-[15px] text-apagado">Arraste o PDF para cá, ou escolha o arquivo. Até 5 MB.</p>
            <button
              onClick={() => entrada.current?.click()}
              className="mt-6 w-full rounded-[10px] bg-verde px-6 py-3.5 font-semibold text-white transition-colors hover:bg-verde-escuro"
            >
              Escolher PDF
            </button>
            <input ref={entrada} type="file" accept="application/pdf" hidden onChange={(e) => enviar(e.target.files?.[0])} />
            <button
              onClick={verExemplo}
              className="mt-3 w-full rounded-[10px] border border-linha-forte px-6 py-3 text-[15px] font-semibold transition-colors hover:border-tinta"
            >
              Ver com um currículo de exemplo
            </button>
            {estado === "erro" && (
              <p role="alert" className="mt-4 text-sm text-ambar">
                {erro}
              </p>
            )}
            <p className="mt-5 text-xs leading-relaxed text-apagado">
              Lido em memória e descartado. Nada de conta, senha ou cadastro: o resultado fica só nesta aba do navegador.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
