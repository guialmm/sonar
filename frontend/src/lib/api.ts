// The backend's shapes (backend/app/api/schemas.py) and the calls the browser makes.

export type Evidencia = { pagina: number; trecho: string; status?: string };
export type Habilidade = { nome: string; categoria: string; nivel: string; evidencia: Evidencia };
export type Perfil = {
  titulo: string;
  senioridade: "estagio" | "junior" | "pleno" | "senior" | "especialista";
  areas: string[];
  resumo: string;
  habilidades: Habilidade[];
  experiencias: { cargo: string; organizacao: string; tipo: string; inicio: string | null; fim: string | null; evidencia: Evidencia }[];
  cidade: string | null;
  estado: string | null;
  idiomas: string[];
  procura: string[];
};

export type Curriculo = {
  exemplo?: boolean; // the demo profile, not the visitor's own CV
  perfil: Perfil;
  paginas: string[];
  habilidades_descartadas: string[];
  evidencias_conferidas: number;
  evidencias_total: number;
};

export type VagaResumo = {
  id: number;
  fonte: string;
  titulo: string;
  empresa: string;
  cidade: string | null;
  estado: string | null;
  modalidade: "remoto" | "hibrido" | "presencial" | "nao_informado";
  publicada_em: string | null;
  confianca: number | null;
  url: string;
};
export type Candidata = { vaga: VagaResumo; afinidade: number; nivel: string; habilidades: string[] };
export type Ponto = { texto: string; trecho_vaga: string; trecho_curriculo: string | null };
export type Explicacao = { vaga_id: number; nota: number; resumo: string; fortes: Ponto[]; lacunas: Ponto[] };
export type Sinal = { codigo: string; pontos: number; motivo: string };
export type Vaga = VagaResumo & { descricao: string; etiquetas: string[]; sinais: Sinal[]; ativa: boolean };
export type Resumo = { lidas: number; escondidas: number; fontes: Record<string, number>; atualizada_em: string | null };

// LLM calls can take a minute on the free tier: they go straight to the API, not through
// the /api rewrite (a proxy gives up sooner).
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8004";

async function corpo<T>(r: Response): Promise<T> {
  if (r.ok) return r.json();
  const erro = await r.json().catch(() => null);
  throw new Error(erro?.detail ?? "Não deu certo agora. Tente de novo em instantes.");
}

export async function enviarCurriculo(arquivo: File): Promise<Curriculo> {
  const dados = new FormData();
  dados.append("arquivo", arquivo);
  return corpo(await fetch(`${API}/api/curriculo`, { method: "POST", body: dados }));
}

export async function curriculoExemplo(): Promise<Curriculo> {
  return { ...(await corpo<Curriculo>(await fetch("/api/exemplo"))), exemplo: true };
}

export async function buscarEncaixe(perfil: Perfil): Promise<Candidata[]> {
  return corpo(
    await fetch(`${API}/api/encaixe`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ perfil, limite: 30 }) }),
  );
}

export async function explicar(perfil: Perfil, paginas: string[], vagas: number[]): Promise<Explicacao[]> {
  return corpo(
    await fetch(`${API}/api/encaixe/explicar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ perfil, paginas, vagas }),
    }),
  );
}

export async function detalharVaga(id: number): Promise<Vaga> {
  return corpo(await fetch(`/api/vagas/${id}`));
}

// Server side: the summary at the top of the page.
export async function resumo(): Promise<Resumo | null> {
  try {
    const r = await fetch(`${process.env.API_URL ?? "http://localhost:8004"}/api/resumo`);
    return r.ok ? r.json() : null;
  } catch {
    return null;
  }
}
