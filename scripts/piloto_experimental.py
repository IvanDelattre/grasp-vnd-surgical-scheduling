"""Piloto sequencial com limite de tempo e persistência por execução.

Reutiliza a CLI comparar e os mesmos serializadores dos experimentos existentes.
Não altera GRASP, N1, N2 ou VND. Executar na raiz do projeto.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from grasp_vnd.avaliacao import exigir_validade, makespan
from grasp_vnd.comparacao import ResultadoComparacao
from grasp_vnd.construcao import validar_alpha
from grasp_vnd.experimentos import linha_experimento, resumir, salvar_csv
from grasp_vnd.grasp import ResultadoGRASP
from grasp_vnd.problema import carregar_instancia, inteiro
from grasp_vnd.vnd import ResultadoVND


def agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def salvar_json_atomico(dados: Any, destino: Path) -> None:
    temporario = destino.with_suffix(destino.suffix + ".tmp")
    temporario.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporario.replace(destino)


def checkpoint(linhas: list[dict[str, Any]], saida: Path) -> None:
    """Substitui CSVs somente depois de gravar o arquivo inteiro."""
    if linhas:
        for nome, conteudo in (("detalhado.csv", linhas), ("resumo.csv", resumir(linhas))):
            temporario = saida / (nome + ".tmp")
            salvar_csv(conteudo, temporario)
            temporario.replace(saida / nome)


def validar_resultado(caminho: Path, dados: dict[str, Any]) -> ResultadoComparacao:
    """Confere soluções e objetivos fora das regiões cronometradas."""
    instancia = carregar_instancia(caminho)
    g, v = ResultadoGRASP(**dados["grasp"]), ResultadoVND(**dados["vnd"])
    for resultado in (g, v):
        exigir_validade(instancia, resultado.melhor_solucao)
        if makespan(instancia, resultado.melhor_solucao) != resultado.makespan:
            raise ValueError("Makespan exportado difere da avaliação independente")
    if v.makespan_inicial != g.makespan or v.makespan > g.makespan:
        raise ValueError("Ponto inicial ou não piora do VND violado")
    return ResultadoComparacao(dados["instancia"], dados["origem"], g, v,
                               dados["tempo_total"], dados["reducao_percentual"])


def executar_piloto(arquivos: list[Path], seeds: list[int], iteracoes: int,
                    alpha: float, saida: Path, limite_execucao_s: float = 120,
                    limite_total_s: float = 600) -> dict[str, Any]:
    """Interrompe o lote no primeiro timeout/falha, preservando checkpoints.

    Usa processo separado por execução para impor timeout sem interromper os
    algoritmos por dentro. Recusa sobrescrever um diretório de resultados.
    """
    inteiro(iteracoes, "iterações", 1)
    validar_alpha(alpha)
    if not arquivos or not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("Informe instâncias e seeds distintas não vazias")
    if len({p.resolve() for p in arquivos}) != len(arquivos):
        raise ValueError("Instâncias devem ser distintas")
    for seed in seeds:
        inteiro(seed, "seed")
    for limite in (limite_execucao_s, limite_total_s):
        if not math.isfinite(limite) or limite <= 0:
            raise ValueError("Limites de tempo devem ser positivos e finitos")
    instancias = [(c, carregar_instancia(c)) for c in arquivos]
    if any(i.origem != "SINTETICA" for _, i in instancias):
        raise ValueError("Este piloto aceita apenas instâncias explicitamente SINTETICAS")
    if saida.exists() and any(saida.iterdir()):
        raise ValueError("Diretório de saída não vazio; escolha outro para preservar os resultados")
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "execucoes").mkdir()
    fontes = ("avaliacao.py", "construcao.py", "busca_local.py", "grasp.py", "vnd.py", "comparacao.py", "problema.py")
    manifesto: dict[str, Any] = {
        "inicio_utc": agora(), "status": "em_execucao", "iteracoes": iteracoes,
        "alpha": alpha, "seeds": seeds, "limite_execucao_s": limite_execucao_s,
        "limite_total_s": limite_total_s, "execucoes_planejadas": len(arquivos) * len(seeds),
        "python": platform.python_version(), "plataforma": platform.platform(),
        "processador": platform.processor(), "cpu_logicas": os.cpu_count(),
        "fontes_algoritmos_sha256": {
            nome: hashlib.sha256((RAIZ / "grasp_vnd" / nome).read_bytes()).hexdigest()
            for nome in fontes
        },
        "instancias": [{"arquivo": c.as_posix(), "identificador": i.identificador,
                         "sha256_arquivo": hashlib.sha256(c.read_bytes()).hexdigest()}
                        for c, i in instancias],
        "execucoes": [],
    }
    salvar_json_atomico(manifesto, saida / "manifesto.json")
    inicio = perf_counter()
    linhas: list[dict[str, Any]] = []
    processo = None
    try:
        for indice, (caminho, instancia) in enumerate(instancias):
            for seed in seeds:
                restante = limite_total_s - (perf_counter() - inicio)
                if restante <= 0:
                    manifesto["status"] = "interrompido_limite_total"
                    return manifesto
                destino = saida / "execucoes" / f"{indice:02d}-seed{seed}.json"
                comando = [sys.executable, "-m", "grasp_vnd", "comparar", str(caminho.resolve()),
                           "--seed", str(seed), "--iteracoes", str(iteracoes),
                           "--alpha", str(alpha), "--saida", str(destino.resolve())]
                registro: dict[str, Any] = {
                    "instancia": instancia.identificador, "seed": seed,
                    "inicio_utc": agora(), "status": "em_execucao",
                    "json": destino.relative_to(saida).as_posix(),
                }
                manifesto["execucoes"].append(registro)
                salvar_json_atomico(manifesto, saida / "manifesto.json")
                print(f"INICIO {instancia.identificador} seed={seed}", flush=True)
                inicio_execucao = perf_counter()
                processo = subprocess.Popen(
                    comando, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                try:
                    _, erro = processo.communicate(timeout=min(limite_execucao_s, restante))
                except subprocess.TimeoutExpired:
                    processo.kill()
                    processo.communicate()
                    registro["status"] = "timeout"
                    registro["tempo_parede_s"] = perf_counter() - inicio_execucao
                    manifesto["status"] = "interrompido_timeout"
                    print(f"TIMEOUT: resultados anteriores preservados em {saida}", flush=True)
                    return manifesto
                registro["tempo_parede_s"] = perf_counter() - inicio_execucao
                if processo.returncode != 0:
                    registro.update(status="falha", erro=erro, codigo=processo.returncode)
                    manifesto["status"] = "interrompido_falha"
                    return manifesto
                dados = json.loads(destino.read_text(encoding="utf-8"))
                resultado = validar_resultado(caminho, dados)
                linhas.append(linha_experimento(caminho, instancia, resultado))
                checkpoint(linhas, saida)
                registro["status"] = "concluida"
                salvar_json_atomico(manifesto, saida / "manifesto.json")
                print(f"FIM {len(linhas)}/{manifesto['execucoes_planejadas']} "
                      f"G={resultado.grasp.makespan} V={resultado.vnd.makespan} "
                      f"tG={resultado.grasp.tempo_execucao:.3f}s "
                      f"tV={resultado.vnd.tempo_execucao:.3f}s "
                      f"realocacoes={resultado.vnd.realocacoes_aceitas}", flush=True)
        manifesto["status"] = "concluido"
    except KeyboardInterrupt:
        manifesto["status"] = "interrompido_usuario"
    except Exception as exc:
        manifesto.update(status="interrompido_falha", erro=repr(exc))
        raise
    finally:
        if processo is not None and processo.poll() is None:
            processo.kill()
            processo.communicate()
        if manifesto["execucoes"] and manifesto["execucoes"][-1]["status"] == "em_execucao":
            manifesto["execucoes"][-1]["status"] = "interrompida"
        checkpoint(linhas, saida)
        manifesto.update(fim_utc=agora(), execucoes_concluidas=len(linhas),
                         tempo_parede_total_s=perf_counter() - inicio,
                         tempo_algoritmos_total_s=sum(r["tempo_total_s"] for r in linhas))
        salvar_json_atomico(manifesto, saida / "manifesto.json")
    return manifesto


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=Path("resultados/piloto"))
    parser.add_argument("--iteracoes", type=int, default=100)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--limite-execucao", type=float, default=120)
    parser.add_argument("--limite-total", type=float, default=600)
    parser.add_argument("--instancias", type=Path, nargs="+", help="Substitui a seleção padrão de oito instâncias")
    args = parser.parse_args(argv)
    arquivos = args.instancias
    if arquivos is None:
        arquivos = []
        for n in (11, 50, 100, 200):
            arquivos.extend(sorted(Path("instancias/sinteticas").glob(f"SINTETICA-{n}-*.json")))
        if len(arquivos) != 8:
            parser.error("São esperadas oito instâncias sintéticas; verifique os arquivos existentes")
    try:
        manifesto = executar_piloto(arquivos, args.seeds, args.iteracoes, args.alpha,
                                    args.saida, args.limite_execucao, args.limite_total)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({k: manifesto[k] for k in ("status", "execucoes_concluidas", "tempo_parede_total_s")}), flush=True)
    return 0 if manifesto["status"] == "concluido" else 1


if __name__ == "__main__":
    raise SystemExit(main())
