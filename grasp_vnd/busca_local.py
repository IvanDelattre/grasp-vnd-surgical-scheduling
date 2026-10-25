"""N1: troca de duas posições na mesma sala, com best improvement."""

from collections.abc import Sequence
from dataclasses import dataclass

from .avaliacao import exigir_validade, tempo_sala
from .problema import Instancia, Solucao


@dataclass
class ResultadoSala:
    sequencia: list[str]
    tempo: int
    avaliacoes: int
    trocas: int


@dataclass
class ResultadoN1:
    solucao: Solucao
    avaliacoes: int
    trocas: int


def delta_troca(instancia: Instancia, sala: Sequence[str], i: int, j: int) -> int:
    """Diferença exata de tempo: somente até quatro arcos são afetados.

    O conjunto de arcos evita contar duas vezes arestas de posições adjacentes.
    As durações permanecem iguais, mesmo com preparação assimétrica.
    """
    arcos = {k for k in (i - 1, i, j - 1, j) if 0 <= k < len(sala) - 1}

    def depois(k: int) -> str:
        return sala[j] if k == i else sala[i] if k == j else sala[k]

    return sum(
        instancia.setup(depois(k), depois(k + 1)) - instancia.setup(sala[k], sala[k + 1])
        for k in arcos
    )


def otimizar_sala(instancia: Instancia, sala: Sequence[str]) -> ResultadoSala:
    """Retorna cópia em ótimo local por trocas, sem alterar a entrada."""
    sequencia = list(sala)
    tempo = tempo_sala(instancia, sequencia)
    avaliacoes = trocas = 0
    while True:
        melhor_delta = 0
        melhor_par = None
        for i in range(len(sequencia)):
            for j in range(i + 1, len(sequencia)):
                delta = delta_troca(instancia, sequencia, i, j)
                avaliacoes += 1
                if delta < melhor_delta:
                    melhor_delta, melhor_par = delta, (i, j)
        if melhor_par is None:
            return ResultadoSala(sequencia, tempo, avaliacoes, trocas)
        i, j = melhor_par
        sequencia[i], sequencia[j] = sequencia[j], sequencia[i]
        tempo += melhor_delta
        trocas += 1


def busca_local_n1(instancia: Instancia, solucao: Solucao) -> ResultadoN1:
    exigir_validade(instancia, solucao)
    resultados = [otimizar_sala(instancia, sala) for sala in solucao]
    return ResultadoN1(
        [r.sequencia for r in resultados],
        sum(r.avaliacoes for r in resultados),
        sum(r.trocas for r in resultados),
    )
