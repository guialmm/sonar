"""Seniority of a posting, read from its title and labels, and how far it is from a profile's."""

import re

from app.coleta.base import sem_acento

ORDEM = ["estagio", "junior", "pleno", "senior", "especialista", "lideranca"]

PADROES = [
    # Leadership first: "Tech Lead Pleno" is a lead role.
    ("lideranca", r"\btech ?lead\b|\blead\b|\blider\b|\bhead\b|\bgerente\b|\bmanager\b|\bcoordenador|\bdiretor|\bdirector\b|\bchief\b|\bvp\b"),
    ("especialista", r"\bespecialista\b|\bspecialist\b|\bstaff\b|\bprincipal\b|\barquitet"),
    ("estagio", r"\bestagi|\bintern(ship)?\b"),
    ("senior", r"\bsenior\b|\bsr\b|\biii\b"),
    ("pleno", r"\bpleno\b|\bpl\b|\bmid(-level)?\b|\bii\b"),
    ("junior", r"\bjunior\b|\bjr\b|\btrainee\b|\bentry[- ]level\b|\bi\b"),
]


def nivel_da_vaga(titulo: str, etiquetas: list[str] = ()) -> str:
    for e in etiquetas:  # GitHub boards label it explicitly
        n = sem_acento(e).lower()
        for nivel in ("estagio", "junior", "pleno", "senior", "especialista"):
            if n == nivel or (nivel == "estagio" and n.startswith("estagi")):
                return nivel
    alvo = sem_acento(titulo).lower()
    for nivel, padrao in PADROES:
        if re.search(padrao, alvo):
            return nivel
    return "nao_informado"


# Points off for the gap between the profile and the posting; None: don't show at all.
DISTANCIA = {
    "estagio": {"estagio": 0, "junior": 10, "nao_informado": 15, "pleno": 45},
    "junior": {"junior": 0, "estagio": 15, "nao_informado": 10, "pleno": 25},
    "pleno": {"pleno": 0, "junior": 15, "senior": 20, "nao_informado": 10, "especialista": 35},
    "senior": {"senior": 0, "pleno": 20, "especialista": 10, "lideranca": 25, "nao_informado": 10},
    "especialista": {"especialista": 0, "senior": 10, "lideranca": 15, "nao_informado": 10},
}


def penalidade(perfil: str, vaga: str) -> int | None:
    return DISTANCIA.get(perfil, {}).get(vaga)
