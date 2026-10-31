"""Executar na raiz: python scripts/validacao_rapida.py.

Somente instâncias com 11/21 cirurgias, 20 iterações e seeds 0, 1, 2.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grasp_vnd.experimentos import executar_experimentos


def main() -> None:
    raiz = Path(__file__).resolve().parents[1]
    arquivos = sorted((raiz / "instancias/sinteticas").glob("SINTETICA-11-*.json"))
    arquivos += sorted((raiz / "instancias/sinteticas").glob("SINTETICA-21-*.json"))
    if len(arquivos) != 4:
        raise SystemExit("Gere antes: python -m grasp_vnd gerar-suite")
    linhas = executar_experimentos(arquivos, range(3), 20,
                                  diretorio_saida=raiz / "resultados/validacao")
    print(f"Validação rápida concluída: {len(linhas)} comparações.")


if __name__ == "__main__":
    main()
