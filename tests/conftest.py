import pytest

from grasp_vnd.problema import Cirurgia, Instancia


@pytest.fixture
def manual():
    return Instancia("manual", 2, (Cirurgia("A", 4), Cirurgia("B", 3), Cirurgia("C", 2)),
                     ((0, 0, 0), (0, 0, 0), (0, 0, 0)), "SINTETICA")


def criar_instancia(duracoes, salas, preparacao=None):
    n = len(duracoes)
    matriz = preparacao if preparacao is not None else [[0] * n for _ in range(n)]
    return Instancia("teste", salas, tuple(Cirurgia(c, d) for c, d in duracoes.items()),
                     tuple(tuple(linha) for linha in matriz), "SINTETICA")
