"""Avaliação independente de qualquer algoritmo de busca."""

from collections import Counter
from collections.abc import Sequence

from .problema import Instancia


def tempo_sala(instancia: Instancia, sala: Sequence[str]) -> int:
    """Soma processamento e preparações consecutivas; preparo inicial zero."""
    return sum(instancia.duracoes[c] for c in sala) + sum(
        instancia.setup(a, b) for a, b in zip(sala, sala[1:])
    )


def makespan(instancia: Instancia, solucao: Sequence[Sequence[str]]) -> int:
    return max((tempo_sala(instancia, sala) for sala in solucao), default=0)


def verificar_validade(instancia: Instancia, solucao: object) -> bool:
    """Verifica M sequências e presença única de todos os IDs conhecidos.

    A execução sequencial implícita impede sobreposição e interrupções.
    """
    if not isinstance(solucao, (list, tuple)) or len(solucao) != instancia.numero_salas:
        return False
    if any(not isinstance(sala, (list, tuple)) for sala in solucao):
        return False
    ids = [c for sala in solucao for c in sala]
    if any(not isinstance(c, str) for c in ids):
        return False
    return Counter(ids) == Counter(instancia.duracoes.keys())


def exigir_validade(instancia: Instancia, solucao: object) -> None:
    if not verificar_validade(instancia, solucao):
        raise ValueError("Solução inválida: use M salas e cada cirurgia exatamente uma vez")
