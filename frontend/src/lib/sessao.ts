// The CV result lives only in this browser tab: no account, nothing on the server.
import { useSyncExternalStore } from "react";

import type { Curriculo } from "./api";

const CHAVE = "sonar:curriculo";

export function guardar(c: Curriculo) {
  try {
    sessionStorage.setItem(CHAVE, JSON.stringify(c));
  } catch {
    // private mode or full storage: the page still works for this visit
  }
}

export function ler(): Curriculo | null {
  try {
    const t = sessionStorage.getItem(CHAVE);
    return t ? (JSON.parse(t) as Curriculo) : null;
  } catch {
    return null;
  }
}

export function esquecer() {
  try {
    sessionStorage.removeItem(CHAVE);
  } catch {}
}

// React reads the stored result as an external store: same parsed object until it changes,
// and "undefined" on the server, where there is no tab to read from.
let cache: { texto: string | null; valor: Curriculo | null } = { texto: null, valor: null };

function instantaneo(): Curriculo | null {
  let texto: string | null = null;
  try {
    texto = sessionStorage.getItem(CHAVE);
  } catch {}
  if (texto !== cache.texto) cache = { texto, valor: texto ? (JSON.parse(texto) as Curriculo) : null };
  return cache.valor;
}

const nadaMuda = () => () => {};

export function useCurriculo(): Curriculo | null | undefined {
  return useSyncExternalStore(nadaMuda, instantaneo, () => undefined);
}
