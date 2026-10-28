from itertools import combinations
from random import Random

import pytest

from grasp_vnd.avaliacao import makespan, tempo_sala
from grasp_vnd.busca_local import busca_local_n1, delta_troca, otimizar_sala
from grasp_vnd.gerador import gerar_instancia
from conftest import criar_instancia


@pytest.mark.parametrize("seed", range(8))
def test_delta_exato_e_otimo_local_por_trocas(seed):
    instancia = gerar_instancia(9, 1, seed, "sequencia")
    sala = [c.id for c in instancia.cirurgias]
    Random(seed + 10).shuffle(sala)
    antes = sala[:]
    for i, j in combinations(range(len(sala)), 2):
        candidata = sala[:]
        candidata[i], candidata[j] = candidata[j], candidata[i]
        assert delta_troca(instancia, sala, i, j) == tempo_sala(instancia, candidata) - tempo_sala(instancia, sala)
    resultado = otimizar_sala(instancia, sala)
    assert sala == antes
    assert resultado.tempo == tempo_sala(instancia, resultado.sequencia)
    assert resultado.tempo <= tempo_sala(instancia, sala)
    for i, j in combinations(range(len(sala)), 2):
        candidata = resultado.sequencia[:]
        candidata[i], candidata[j] = candidata[j], candidata[i]
        assert tempo_sala(instancia, candidata) >= resultado.tempo


def test_n1_melhora_sala_nao_critica():
    instancia = criar_instancia({"A": 1, "B": 1, "C": 100}, 2,
                                [[0, 9, 0], [0, 0, 0], [0, 0, 0]])
    solucao = [["A", "B"], ["C"]]
    resultado = busca_local_n1(instancia, solucao)
    assert resultado.solucao == [["B", "A"], ["C"]]
    assert solucao == [["A", "B"], ["C"]]
    assert makespan(instancia, resultado.solucao) == makespan(instancia, solucao) == 100


def test_n1_best_improvement_comparado_com_oraculo():
    instancia = gerar_instancia(8, 1, 91, "sequencia")
    sala = [c.id for c in instancia.cirurgias]
    oraculo = sala[:]
    while True:
        melhor, valor = oraculo, tempo_sala(instancia, oraculo)
        for i, j in combinations(range(len(oraculo)), 2):
            candidata = oraculo[:]
            candidata[i], candidata[j] = candidata[j], candidata[i]
            tempo = tempo_sala(instancia, candidata)
            if tempo < valor:
                melhor, valor = candidata, tempo
        if melhor == oraculo:
            break
        oraculo = melhor
    assert otimizar_sala(instancia, sala).sequencia == oraculo
