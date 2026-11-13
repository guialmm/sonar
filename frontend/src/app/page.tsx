import { Suspense } from "react";

import { Contador } from "@/components/Contador";
import { Envio } from "@/components/Envio";
import { resumo } from "@/lib/api";

// The live numbers stream in; the rest of the page doesn't wait for the API.
async function Numeros() {
  const r = await resumo();
  if (!r) return null;
  return (
    <dl className="mt-10 grid max-w-xl grid-cols-2 gap-6 border-t border-linha pt-6">
      <div>
        <dt className="text-sm text-apagado">vagas abertas agora</dt>
        <dd className="mt-1 font-display text-4xl font-bold">
          <Contador valor={r.lidas} />
        </dd>
      </div>
      <div>
        <dt className="text-sm text-apagado">escondidas por parecerem fantasma</dt>
        <dd className="mt-1 font-display text-4xl font-bold text-ambar">
          <Contador valor={r.escondidas} />
        </dd>
      </div>
    </dl>
  );
}

export default function Inicio() {
  return (
    <div className="mx-auto grid max-w-[1440px] gap-12 px-5 py-14 sm:px-12 lg:grid-cols-[1.15fr_1fr] lg:items-center lg:py-24">
      <section>
        <h1 className="font-display text-[42px] font-bold leading-[1.05] tracking-tight sm:text-[56px]">
          As vagas que encaixam no seu currículo. <span className="text-verde">E o aviso quando a vaga é fantasma.</span>
        </h1>
        <p className="mt-6 max-w-[58ch] text-lg leading-relaxed text-[#3a4a41]">
          O Sonar lê vagas da Gupy, das comunidades do GitHub, de quadros de vagas remotas e das páginas de carreira de
          empresas como Nubank, BTG Pactual, Stone, CI&T e Bosch. Você manda o currículo; ele mostra onde você encaixa, com o trecho da vaga e do seu currículo que provam
          cada motivo.
        </p>
        <Suspense fallback={<div className="mt-10 h-[92px] max-w-xl border-t border-linha" />}>
          <Numeros />
        </Suspense>
      </section>
      <section>
        <Envio />
      </section>
    </div>
  );
}
