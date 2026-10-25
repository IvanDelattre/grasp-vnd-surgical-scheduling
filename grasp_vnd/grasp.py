"""Multistart GRASP: construção nova e N1 em cada iteração."""

from dataclasses import dataclass
from random import Random
from time import perf_counter

from .avaliacao import exigir_validade, makespan
from .busca_local import busca_local_n1
from .construcao import construir_solucao, validar_alpha
from .problema import Instancia, Solucao, inteiro


@dataclass
class ResultadoGRASP:
    melhor_solucao: Solucao
    makespan: int
    seed: int
    iteracoes: int
    alpha: float
    tempo_execucao: float
    avaliacoes_n1: int
    trocas_n1: int


def executar_grasp(instancia: Instancia, seed: int = 0, iteracoes: int = 1000,
                   alpha: float = 0.5) -> ResultadoGRASP:
    inteiro(seed, "seed")
    inteiro(iteracoes, "iterações", 1)
    validar_alpha(alpha)
    inicio = perf_counter()
    rng = Random(seed)
    melhor: Solucao | None = None
    melhor_valor = float("inf")
    avaliacoes = trocas = 0
    for _ in range(iteracoes):
        local = busca_local_n1(instancia, construir_solucao(instancia, rng, alpha))
        valor = makespan(instancia, local.solucao)
        avaliacoes += local.avaliacoes
        trocas += local.trocas
        if valor < melhor_valor:
            melhor = [sala[:] for sala in local.solucao]
            melhor_valor = valor
    if melhor is None:
        raise RuntimeError("GRASP não produziu solução")
    exigir_validade(instancia, melhor)
    return ResultadoGRASP(melhor, int(melhor_valor), seed, iteracoes, alpha,
                         perf_counter() - inicio, avaliacoes, trocas)
