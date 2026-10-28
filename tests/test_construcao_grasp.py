from copy import deepcopy
from random import Random

import pytest

from grasp_vnd.avaliacao import makespan, verificar_validade
from grasp_vnd.construcao import construir_solucao, tamanho_lrc
from grasp_vnd.gerador import gerar_instancia
from grasp_vnd.grasp import executar_grasp
from conftest import criar_instancia


@pytest.mark.parametrize("alpha,esperados", [
    (0, [1, 1, 1, 1, 1]), (0.5, [1, 1, 2, 2, 3]), (1, [1, 2, 3, 4, 5]),
])
def test_lrc_floor_e_limites(alpha, esperados):
    assert [tamanho_lrc(n, alpha) for n in range(1, 6)] == esperados


@pytest.mark.parametrize("alpha", [-0.01, 1.01, float("nan"), float("inf"), True])
def test_alpha_invalido(alpha):
    with pytest.raises(ValueError):
        tamanho_lrc(5, alpha)


def test_ordenacao_desempates_e_distribuicao_entre_salas():
    instancia = criar_instancia({"D": 4, "C": 3, "B": 1, "A": 1}, 2)
    assert construir_solucao(instancia, Random(0), alpha=0) == [["A", "C"], ["B", "D"]]


def test_escolha_sala_inclui_setup():
    instancia = criar_instancia({"A": 1, "B": 2, "C": 3}, 2,
                                [[0, 0, 20], [0, 0, 0], [0, 0, 0]])
    assert construir_solucao(instancia, Random(0), 0) == [["A"], ["B", "C"]]


def test_sorteio_uniforme_do_prefixo_e_reconstrucao_lrc():
    class AleatorioControlado:
        def __init__(self):
            self.limites = []

        def randrange(self, limite):
            self.limites.append(limite)
            return limite - 1

    instancia = criar_instancia({"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}, 1)
    rng = AleatorioControlado()
    assert construir_solucao(instancia, rng, 0.5) == [["C", "B", "D", "A", "E"]]
    assert rng.limites == [3, 2, 2, 1, 1]


@pytest.mark.parametrize("n,salas", [(1, 1), (1, 4), (7, 1), (11, 3)])
def test_grasp_casos_limite_validade_reprodutibilidade(n, salas):
    instancia = gerar_instancia(n, salas, seed=5, perfil="sequencia")
    antes = deepcopy(instancia.para_dict())
    a = executar_grasp(instancia, 123, 8)
    b = executar_grasp(instancia, 123, 8)
    assert a.melhor_solucao == b.melhor_solucao
    assert a.makespan == b.makespan == makespan(instancia, a.melhor_solucao)
    assert a.avaliacoes_n1 == b.avaliacoes_n1
    assert verificar_validade(instancia, a.melhor_solucao)
    assert instancia.para_dict() == antes
    assert a.seed == 123 and a.iteracoes == 8
    assert a.tempo_execucao >= 0


@pytest.mark.parametrize("parametros", [{"iteracoes": 0}, {"iteracoes": 1.5}, {"seed": -1}])
def test_grasp_rejeita_parametros_invalidos(manual, parametros):
    with pytest.raises(ValueError):
        executar_grasp(manual, **parametros)
