"""Construção gulosa aleatorizada com LRC por cardinalidade."""

import math
from random import Random

from .problema import Instancia, Solucao, inteiro


def validar_alpha(alpha: float) -> None:
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0 <= alpha <= 1:
        raise ValueError("alpha deve estar entre 0 e 1")


def tamanho_lrc(n: int, alpha: float = 0.5) -> int:
    inteiro(n, "número de candidatos", 1)
    validar_alpha(alpha)
    return min(n, max(1, math.floor(1 + alpha * (n - 1))))


def construir_solucao(instancia: Instancia, rng: Random, alpha: float = 0.5) -> Solucao:
    """Insere no final da sala com menor conclusão projetada, desempate pelo índice."""
    validar_alpha(alpha)
    candidatos = sorted(instancia.duracoes, key=lambda c: (instancia.duracoes[c], c))
    solucao: Solucao = [[] for _ in range(instancia.numero_salas)]
    tempos = [0] * instancia.numero_salas
    while candidatos:
        cirurgia = candidatos.pop(rng.randrange(tamanho_lrc(len(candidatos), alpha)))
        projetados = [
            tempos[i] + instancia.duracoes[cirurgia]
            + (instancia.setup(sala[-1], cirurgia) if sala else 0)
            for i, sala in enumerate(solucao)
        ]
        destino = min(range(instancia.numero_salas), key=lambda i: (projetados[i], i))
        solucao[destino].append(cirurgia)
        tempos[destino] = projetados[destino]
    return solucao
