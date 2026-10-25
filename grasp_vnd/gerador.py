"""Instâncias SINTÉTICAS; as distribuições são escolhas deste projeto."""

from pathlib import Path
from random import Random

from .problema import Cirurgia, Instancia, inteiro, salvar_instancia

TAMANHOS_SALAS = ((11, 3), (21, 2), (50, 4), (75, 5), (100, 5), (130, 6), (200, 10))
PERFIS = {
    "simples": ((1, 8), (0, 1)),
    "sequencia": ((1, 12), (0, 10)),
}


def gerar_instancia(n: int, salas: int, seed: int = 0,
                    perfil: str = "simples") -> Instancia:
    """Sorteios uniformes inteiros independentes, inclusive nos dois sentidos.

    Perfil simples: duração 1..8, preparo 0..1. Perfil sequencia:
    duração 1..12, preparo 0..10. Diagonal nula. Não são dados hospitalares.
    """
    inteiro(n, "número de cirurgias", 1)
    inteiro(salas, "número de salas", 1)
    inteiro(seed, "seed")
    if perfil not in PERFIS:
        raise ValueError(f"Perfil deve ser um de {tuple(PERFIS)}")
    duracao, preparo = PERFIS[perfil]
    rng = Random(seed)
    cirurgias = tuple(Cirurgia(f"C{i + 1:04d}", rng.randint(*duracao)) for i in range(n))
    matriz = tuple(tuple(0 if i == j else rng.randint(*preparo) for j in range(n)) for i in range(n))
    return Instancia(
        f"SINTETICA-{n}-S{salas}-{perfil}-seed{seed}", salas, cirurgias, matriz,
        origem="SINTETICA",
        metadados={
            "seed": seed, "perfil": perfil,
            "distribuicao": "uniforme discreta independente (escolha deste projeto)",
            "intervalo_duracao": list(duracao), "intervalo_preparacao": list(preparo),
            "diagonal_preparacao": 0,
        },
    )


def gerar_suite(diretorio: str | Path, seed_base: int = 2020) -> list[Path]:
    """Gera os sete tamanhos em dois perfis, totalizando 14 arquivos."""
    inteiro(seed_base, "seed base")
    caminhos = []
    for k, (n, salas) in enumerate(TAMANHOS_SALAS):
        for perfil in PERFIS:
            instancia = gerar_instancia(n, salas, seed_base + k, perfil)
            caminho = Path(diretorio) / f"{instancia.identificador}.json"
            salvar_instancia(instancia, caminho)
            caminhos.append(caminho)
    return caminhos
