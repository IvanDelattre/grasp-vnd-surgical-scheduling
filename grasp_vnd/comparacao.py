"""Comparação pareada: uma execução GRASP e sua pós-otimização."""

from dataclasses import dataclass

from .grasp import ResultadoGRASP, executar_grasp
from .problema import Instancia
from .vnd import ResultadoVND, executar_vnd


@dataclass
class ResultadoComparacao:
    instancia: str
    origem: str
    grasp: ResultadoGRASP
    vnd: ResultadoVND
    tempo_total: float
    reducao_percentual: float


def comparar(instancia: Instancia, seed: int = 0, iteracoes: int = 1000,
             alpha: float = 0.5) -> ResultadoComparacao:
    grasp = executar_grasp(instancia, seed, iteracoes, alpha)
    copia = [sala[:] for sala in grasp.melhor_solucao]
    vnd = executar_vnd(instancia, copia)
    if grasp.melhor_solucao != copia:
        raise RuntimeError("VND modificou sua solução de entrada")
    if vnd.makespan_inicial != grasp.makespan or vnd.makespan > grasp.makespan:
        raise RuntimeError("Comparação violou o ponto de partida ou a não piora")
    reducao = 100 * (grasp.makespan - vnd.makespan) / grasp.makespan
    return ResultadoComparacao(instancia.identificador, instancia.origem, grasp, vnd,
                               grasp.tempo_execucao + vnd.tempo_execucao, reducao)
