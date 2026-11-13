import type { VagaResumo } from "./api";

export const MODALIDADE: Record<VagaResumo["modalidade"], string> = {
  remoto: "Remoto",
  hibrido: "Híbrido",
  presencial: "Presencial",
  nao_informado: "Modalidade não informada",
};

export const FONTE: Record<string, string> = {
  gupy: "Gupy",
  github: "Comunidade no GitHub",
  greenhouse: "Página de carreira",
  ashby: "Página de carreira",
  lever: "Página de carreira",
};

export const SENIORIDADE: Record<string, string> = {
  estagio: "estágio",
  junior: "júnior",
  pleno: "pleno",
  senior: "sênior",
  especialista: "especialista",
};

export function lugar(v: Pick<VagaResumo, "cidade" | "estado" | "modalidade">) {
  const onde = [v.cidade, v.estado].filter(Boolean).join(", ");
  return v.modalidade === "remoto" || !onde ? MODALIDADE[v.modalidade] : `${MODALIDADE[v.modalidade]} · ${onde}`;
}
