from copy import deepcopy

import pytest

import grasp_vnd.comparacao as modulo_comparacao
import grasp_vnd.vnd as modulo_vnd
from grasp_vnd.avaliacao import makespan, verificar_validade
from grasp_vnd.busca_local import busca_local_n1
from grasp_vnd.comparacao import comparar
from grasp_vnd.gerador import gerar_instancia
from grasp_vnd.vnd import executar_vnd, melhor_realocacao
from conftest import criar_instancia


def enumerar_oraculo(instancia, solucao):
    valor = makespan(instancia, solucao)
    melhor = None
    contagem = 0
    for origem in range(instancia.numero_salas):
        for posicao in range(len(solucao[origem])):
            for destino in range(instancia.numero_salas):
                if origem == destino:
                    continue
                for insercao in range(len(solucao[destino]) + 1):
                    candidata = deepcopy(solucao)
                    cirurgia = candidata[origem].pop(posicao)
                    candidata[destino].insert(insercao, cirurgia)
                    contagem += 1
                    novo = makespan(instancia, candidata)
                    if novo < valor:
                        valor = novo
                        melhor = (origem, posicao, destino, insercao, candidata, novo)
    return melhor, contagem


def test_realocacao_b_reduz_7_para_5(manual):
    inicial = [["A", "B"], ["C"]]
    busca = melhor_realocacao(manual, inicial)
    movimento = busca.melhor_movimento
    assert movimento is not None
    assert (movimento.origem, movimento.posicao_origem, movimento.destino) == (0, 1, 1)
    assert movimento.solucao == [["A"], ["B", "C"]]
    resultado = executar_vnd(manual, inicial)
    assert resultado.makespan_inicial == 7 and resultado.makespan == 5
    assert resultado.realocacoes_aceitas == 1
    assert resultado.historico_makespan == [7, 5]
    assert inicial == [["A", "B"], ["C"]]


@pytest.mark.parametrize("insercao", [0, 1, 3])
def test_n2_insere_no_inicio_meio_e_fim(insercao):
    ids = ["X", "D", "A", "B", "C"]
    matriz = [[0 if i == j else 20 for j in range(5)] for i in range(5)]

    def liberar(a, b):
        matriz[ids.index(a)][ids.index(b)] = 0

    liberar("X", "D")
    liberar("A", "B")
    liberar("B", "C")
    destino = ["A", "B", "C"]
    if insercao > 0:
        liberar(destino[insercao - 1], "X")
    if insercao < 3:
        liberar("X", destino[insercao])
    instancia = criar_instancia({"X": 4, "D": 6, "A": 1, "B": 1, "C": 1}, 2, matriz)
    movimento = melhor_realocacao(instancia, [["X", "D"], destino]).melhor_movimento
    assert movimento is not None
    assert (movimento.origem, movimento.posicao_origem, movimento.destino, movimento.posicao_destino) == (0, 0, 1, insercao)
    assert movimento.makespan == 7


@pytest.mark.parametrize("seed", range(8))
def test_n2_enumera_todas_salas_e_posicoes_best_improvement(seed):
    instancia = gerar_instancia(8, 4, seed, "sequencia")
    ids = [c.id for c in instancia.cirurgias]
    solucao = [ids[:3], ids[3:4], [], ids[4:]]
    antes = deepcopy(solucao)
    esperado, contagem = enumerar_oraculo(instancia, solucao)
    resultado = melhor_realocacao(instancia, solucao)
    # Contagem analítica: para cada cirurgia de o, len(destino)+1 posições.
    assert contagem == sum(len(solucao[o]) * (len(solucao[d]) + 1)
                           for o in range(4) for d in range(4) if o != d)
    assert resultado.avaliacoes == contagem
    m = resultado.melhor_movimento
    obtido = None if m is None else (m.origem, m.posicao_origem, m.destino, m.posicao_destino, m.solucao, m.makespan)
    assert obtido == esperado
    assert solucao == antes


def test_vnd_n1_apenas_nas_salas_afetadas(monkeypatch):
    instancia = criar_instancia({"A": 4, "B": 3, "C": 2}, 3)
    inicial = [["A", "B"], ["C"], []]
    chamadas = []
    original = modulo_vnd.otimizar_sala

    def registrar(instancia, sala):
        chamadas.append(sala[:])
        return original(instancia, sala)

    monkeypatch.setattr(modulo_vnd, "otimizar_sala", registrar)
    resultado = executar_vnd(instancia, inicial)
    assert chamadas == [["B"], ["A"]]
    assert resultado.melhor_solucao[1] == ["C"]
    assert resultado.makespan == 4


@pytest.mark.parametrize("n,salas", [(1, 1), (1, 3), (7, 1), (11, 3), (21, 2)])
def test_vnd_nao_piora_valido_e_nao_altera_entrada(n, salas):
    instancia = gerar_instancia(n, salas, 13, "sequencia")
    inicial = [[c.id for c in instancia.cirurgias]] + [[] for _ in range(salas - 1)]
    inicial = busca_local_n1(instancia, inicial).solucao
    antes = deepcopy(inicial)
    resultado = executar_vnd(instancia, inicial)
    assert inicial == antes
    assert resultado.makespan <= makespan(instancia, inicial)
    assert verificar_validade(instancia, resultado.melhor_solucao)
    assert all(a > b for a, b in zip(resultado.historico_makespan, resultado.historico_makespan[1:]))
    assert melhor_realocacao(instancia, resultado.melhor_solucao).melhor_movimento is None
    assert busca_local_n1(instancia, resultado.melhor_solucao).solucao == resultado.melhor_solucao
    resultado.melhor_solucao[0].append("alteracao_externa")
    assert inicial == antes


def test_comparacao_executa_grasp_uma_vez_e_preserva_ponto_inicial(manual, monkeypatch):
    original_grasp = modulo_comparacao.executar_grasp
    original_vnd = modulo_comparacao.executar_vnd
    capturas = []

    def registrar_grasp(*args):
        resultado = original_grasp(*args)
        capturas.append(resultado)
        return resultado

    def registrar_vnd(instancia, solucao):
        assert solucao == capturas[0].melhor_solucao
        assert solucao is not capturas[0].melhor_solucao
        assert all(a is not b for a, b in zip(solucao, capturas[0].melhor_solucao))
        return original_vnd(instancia, solucao)

    monkeypatch.setattr(modulo_comparacao, "executar_grasp", registrar_grasp)
    monkeypatch.setattr(modulo_comparacao, "executar_vnd", registrar_vnd)
    resultado = comparar(manual, 0, 4)
    assert len(capturas) == 1
    assert resultado.tempo_total == resultado.grasp.tempo_execucao + resultado.vnd.tempo_execucao
    assert resultado.reducao_percentual == 100 * (resultado.grasp.makespan - resultado.vnd.makespan) / resultado.grasp.makespan


def test_comparacao_reprodutivel():
    instancia = gerar_instancia(11, 3, 41, "sequencia")
    a, b = comparar(instancia, 3, 10), comparar(instancia, 3, 10)
    assert a.grasp.melhor_solucao == b.grasp.melhor_solucao
    assert a.vnd.melhor_solucao == b.vnd.melhor_solucao
    assert a.reducao_percentual == b.reducao_percentual


def test_vnd_rejeita_solucao_invalida(manual):
    with pytest.raises(ValueError):
        executar_vnd(manual, [["A"], ["A", "B"]])
