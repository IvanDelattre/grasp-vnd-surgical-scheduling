"""VND adaptado: N2 estrita, seguida de N1 nas duas salas afetadas."""

from dataclasses import dataclass
from time import perf_counter

from .avaliacao import exigir_validade, makespan, tempo_sala
from .busca_local import otimizar_sala
from .problema import Instancia, Solucao


@dataclass
class Movimento:
    origem: int
    posicao_origem: int
    destino: int
    posicao_destino: int
    solucao: Solucao
    makespan: int


@dataclass
class ResultadoN2:
    melhor_movimento: Movimento | None
    avaliacoes: int


@dataclass
class ResultadoVND:
    melhor_solucao: Solucao
    makespan: int
    makespan_inicial: int
    tempo_execucao: float
    realocacoes_aceitas: int
    avaliacoes_n2: int
    avaliacoes_n1: int
    trocas_n1: int
    historico_makespan: list[int]


def melhor_realocacao(instancia: Instancia, solucao: Solucao) -> ResultadoN2:
    """Enumera origem, posição, destino e inserção, nessa ordem crescente.

    Cada candidato é validado. Somente as duas salas alteradas são reavaliadas;
    o máximo das demais salas é reutilizado para cada par origem/destino.
    Empates mantêm o primeiro movimento enumerado.
    """
    exigir_validade(instancia, solucao)
    tempos = [tempo_sala(instancia, sala) for sala in solucao]
    melhor_valor = max(tempos)
    melhor = None
    avaliacoes = 0
    outros = {
        (o, d): max((t for i, t in enumerate(tempos) if i not in (o, d)), default=0)
        for o in range(instancia.numero_salas)
        for d in range(instancia.numero_salas) if o != d
    }
    for origem, sala in enumerate(solucao):
        for posicao, cirurgia in enumerate(sala):
            for destino, sala_destino in enumerate(solucao):
                if origem == destino:
                    continue
                for insercao in range(len(sala_destino) + 1):
                    candidata = [s[:] for s in solucao]
                    candidata[origem].pop(posicao)
                    candidata[destino].insert(insercao, cirurgia)
                    exigir_validade(instancia, candidata)
                    valor = max(outros[origem, destino],
                                tempo_sala(instancia, candidata[origem]),
                                tempo_sala(instancia, candidata[destino]))
                    avaliacoes += 1
                    if valor < melhor_valor:
                        melhor_valor = valor
                        melhor = Movimento(origem, posicao, destino, insercao, candidata, valor)
    return ResultadoN2(melhor, avaliacoes)


def executar_vnd(instancia: Instancia, solucao: Solucao) -> ResultadoVND:
    """Parte de cópia exata e inicia por N2; espera entrada já otimizada por N1.

    Também aceita qualquer solução válida, mas nesse caso não garante ótimo
    local por N1 nas salas que nunca forem afetadas por uma realocação.
    """
    inicio = perf_counter()
    exigir_validade(instancia, solucao)
    atual = [sala[:] for sala in solucao]
    inicial = valor = makespan(instancia, atual)
    historico = [inicial]
    aceitas = avaliacoes_n2 = avaliacoes_n1 = trocas = 0
    while True:
        busca = melhor_realocacao(instancia, atual)
        avaliacoes_n2 += busca.avaliacoes
        movimento = busca.melhor_movimento
        if movimento is None:
            break
        atual = movimento.solucao
        for indice in (movimento.origem, movimento.destino):
            local = otimizar_sala(instancia, atual[indice])
            atual[indice] = local.sequencia
            avaliacoes_n1 += local.avaliacoes
            trocas += local.trocas
        novo_valor = makespan(instancia, atual)
        if novo_valor >= valor:
            raise RuntimeError("Realocação aceita não produziu melhoria estrita")
        valor = novo_valor
        historico.append(valor)
        aceitas += 1
    exigir_validade(instancia, atual)
    if valor > inicial:
        raise RuntimeError("VND piorou o makespan inicial")
    return ResultadoVND(atual, valor, inicial, perf_counter() - inicio,
                        aceitas, avaliacoes_n2, avaliacoes_n1, trocas, historico)
