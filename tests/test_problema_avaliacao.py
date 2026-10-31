from copy import deepcopy

import pytest

from grasp_vnd.avaliacao import makespan, tempo_sala, verificar_validade
from grasp_vnd.problema import carregar_instancia, instancia_de_dict, salvar_instancia
from conftest import criar_instancia


def test_calculo_manual_e_salas_vazias(manual):
    assert tempo_sala(manual, ["A", "B"]) == 7
    assert tempo_sala(manual, []) == 0
    assert makespan(manual, [["A", "B"], ["C"]]) == 7
    assert makespan(manual, [["A"], ["C", "B"]]) == 5
    assert verificar_validade(manual, [["A", "B", "C"], []])


@pytest.mark.parametrize("solucao", [
    [["A", "B"], ["A", "C"]], [["A"], ["C"]],
    [["A", "B"], ["X"]], [["A", "B", "C"]],
    [["A", "B"], [["C"]]], None, ["AB", ["C"]],
])
def test_validade_rejeita_cirurgias_ausentes_repetidas_e_estruturas(manual, solucao):
    assert not verificar_validade(manual, solucao)


def test_preparacao_direcional_e_inicial_nula():
    instancia = criar_instancia({"A": 2, "B": 3}, 1, [[99, 7], [1, 88]])
    assert tempo_sala(instancia, ["A"]) == 2
    assert tempo_sala(instancia, ["A", "B"]) == 12
    assert tempo_sala(instancia, ["B", "A"]) == 6


def test_json_round_trip(manual, tmp_path):
    caminho = tmp_path / "sub/instancia.json"
    salvar_instancia(manual, caminho)
    assert carregar_instancia(caminho) == manual


@pytest.mark.parametrize("alteracao", [
    {"numero_salas": 0}, {"numero_salas": True}, {"identificador": ""},
    {"cirurgias": []}, {"cirurgias": [{"id": "A", "duracao": 0}]},
    {"cirurgias": [{"id": "A", "duracao": 1.5}]},
    {"cirurgias": [{"id": "A", "duracao": True}]},
    {"cirurgias": [{"id": "A", "duracao": 1}, {"id": "A", "duracao": 2}]},
    {"preparacao": [[0]]}, {"preparacao": [[0, -1, 0]] * 3},
    {"preparacao": [[0, 0.5, 0]] * 3}, {"unidade_minutos": 60},
    {"cirurgias": [{"duracao": 1}]}, {"metadados": None},
])
def test_entrada_invalida(manual, alteracao):
    dados = manual.para_dict()
    dados.update(alteracao)
    with pytest.raises(ValueError):
        instancia_de_dict(dados)


def test_modelo_copia_dados_json(manual):
    dados = manual.para_dict()
    instancia = instancia_de_dict(dados)
    antes = deepcopy(instancia.para_dict())
    dados["cirurgias"][0]["duracao"] = 100
    dados["preparacao"][0][1] = 100
    assert instancia.para_dict() == antes
