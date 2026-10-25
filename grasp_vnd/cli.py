"""Interface de linha de comando em português."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .comparacao import comparar
from .experimentos import executar_experimentos
from .gerador import PERFIS, gerar_instancia, gerar_suite
from .problema import carregar_instancia, salvar_instancia


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GRASP + VND: tempos em blocos de 30 minutos")
    comandos = parser.add_subparsers(dest="comando", required=True)
    comparar_cmd = comandos.add_parser("comparar", help="GRASP e pós-otimização na mesma instância")
    comparar_cmd.add_argument("instancia", type=Path)
    comparar_cmd.add_argument("--seed", type=int, default=0)
    comparar_cmd.add_argument("--iteracoes", type=int, default=1000)
    comparar_cmd.add_argument("--alpha", type=float, default=0.5)
    comparar_cmd.add_argument("--saida", type=Path, help="Salvar comparação completa em JSON")

    gerar = comandos.add_parser("gerar", help="Gerar uma instância SINTÉTICA")
    gerar.add_argument("--cirurgias", type=int, required=True)
    gerar.add_argument("--salas", type=int, required=True)
    gerar.add_argument("--seed", type=int, default=2020)
    gerar.add_argument("--perfil", choices=PERFIS, default="simples")
    gerar.add_argument("--saida", type=Path, required=True)

    suite = comandos.add_parser("gerar-suite", help="Gerar 14 cenários SINTÉTICOS, sem executar algoritmos")
    suite.add_argument("--saida", type=Path, default=Path("instancias/sinteticas"))
    suite.add_argument("--seed-base", type=int, default=2020)

    experimento = comandos.add_parser("experimentar", help="Lote pareado; padrão rápido de 20 iterações e 3 seeds")
    experimento.add_argument("instancias", type=Path, nargs="+", help="Arquivos JSON ou diretórios de JSON")
    experimento.add_argument("--iteracoes", type=int, default=20)
    experimento.add_argument("--execucoes", type=int, default=3)
    experimento.add_argument("--seed-inicial", type=int, default=0)
    experimento.add_argument("--seeds", type=int, nargs="+", help="Seeds explícitas; substituem execuções e seed inicial")
    experimento.add_argument("--alpha", type=float, default=0.5)
    experimento.add_argument("--saida", type=Path, default=Path("resultados/validacao"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = criar_parser()
    args = parser.parse_args(argv)
    try:
        if args.comando == "comparar":
            resultado = comparar(carregar_instancia(args.instancia), args.seed, args.iteracoes, args.alpha)
            texto = json.dumps(asdict(resultado), ensure_ascii=False, indent=2) + "\n"
            if args.saida:
                args.saida.parent.mkdir(parents=True, exist_ok=True)
                args.saida.write_text(texto, encoding="utf-8")
            print(texto, end="")
        elif args.comando == "gerar":
            instancia = gerar_instancia(args.cirurgias, args.salas, args.seed, args.perfil)
            salvar_instancia(instancia, args.saida)
            print(f"SINTETICA: {instancia.identificador} -> {args.saida}")
        elif args.comando == "gerar-suite":
            for caminho in gerar_suite(args.saida, args.seed_base):
                print(caminho)
        else:
            if args.execucoes < 1:
                raise ValueError("execuções deve ser >= 1")
            seeds = args.seeds if args.seeds is not None else range(args.seed_inicial, args.seed_inicial + args.execucoes)
            arquivos = []
            for caminho in args.instancias:
                arquivos.extend(sorted(caminho.glob("*.json")) if caminho.is_dir() else [caminho])
            linhas = executar_experimentos(arquivos, seeds, args.iteracoes, args.alpha, args.saida)
            print(f"{len(linhas)} comparações salvas em {args.saida / 'detalhado.csv'} e {args.saida / 'resumo.csv'}")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0
