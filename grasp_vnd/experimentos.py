"""Execuções pareadas, CSV detalhado e resumo agregado por instância."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Iterable

from .comparacao import ResultadoComparacao, comparar
from .construcao import validar_alpha
from .problema import Instancia, carregar_instancia, inteiro


def salvar_csv(linhas: list[dict[str, Any]], caminho: str | Path) -> None:
    if not linhas:
        raise ValueError("Nenhuma linha para salvar")
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def resumir(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grupos: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for linha in linhas:
        chave = (linha["instancia"], linha["sha256_instancia"], linha["iteracoes"], linha["alpha"])
        grupos.setdefault(chave, []).append(linha)
    resumo = []
    for (identificador, digest, iteracoes, alpha), grupo in grupos.items():
        g = [r["makespan_grasp"] for r in grupo]
        v = [r["makespan_vnd"] for r in grupo]
        melhorias = sum(b < a for a, b in zip(g, v))
        resumo.append({
            "instancia": identificador, "origem": grupo[0]["origem"],
            "sha256_instancia": digest, "iteracoes": iteracoes, "alpha": alpha,
            "execucoes": len(grupo),
            "melhor_grasp": min(g), "media_grasp": mean(g),
            "desvio_amostral_grasp": stdev(g) if len(g) > 1 else 0.0,
            "melhor_vnd": min(v), "media_vnd": mean(v),
            "desvio_amostral_vnd": stdev(v) if len(v) > 1 else 0.0,
            "media_tempo_grasp_s": mean(r["tempo_grasp_s"] for r in grupo),
            "media_tempo_adicional_vnd_s": mean(r["tempo_adicional_vnd_s"] for r in grupo),
            "media_tempo_total_s": mean(r["tempo_total_s"] for r in grupo),
            "media_reducao_percentual": mean(r["reducao_percentual"] for r in grupo),
            "media_realocacoes": mean(r["realocacoes_aceitas"] for r in grupo),
            "execucoes_com_melhoria": melhorias,
            "percentual_execucoes_com_melhoria": 100 * melhorias / len(grupo),
            "execucoes_sem_melhoria": sum(b == a for a, b in zip(g, v)),
        })
    return resumo


def linha_experimento(caminho: str | Path, instancia: Instancia,
                     resultado: ResultadoComparacao) -> dict[str, Any]:
    """Serializa uma comparação já executada, sem arredondar os números."""
    canonico = json.dumps(instancia.para_dict(), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
    g, v = resultado.grasp, resultado.vnd
    return {
        "instancia": instancia.identificador, "arquivo": Path(caminho).as_posix(),
        "origem": instancia.origem, "sha256_instancia": digest,
        "python": platform.python_version(), "plataforma": platform.platform(),
        "data_utc": datetime.now(timezone.utc).isoformat(),
        "numero_cirurgias": len(instancia.cirurgias), "numero_salas": instancia.numero_salas,
        "unidade_minutos": 30, "seed": g.seed, "iteracoes": g.iteracoes, "alpha": g.alpha,
        "makespan_grasp": g.makespan, "makespan_vnd": v.makespan,
        "tempo_grasp_s": g.tempo_execucao, "tempo_adicional_vnd_s": v.tempo_execucao,
        "tempo_total_s": resultado.tempo_total,
        "realocacoes_aceitas": v.realocacoes_aceitas,
        "avaliacoes_n1_grasp": g.avaliacoes_n1, "trocas_n1_grasp": g.trocas_n1,
        "avaliacoes_n2_vnd": v.avaliacoes_n2,
        "avaliacoes_n1_vnd": v.avaliacoes_n1, "trocas_n1_vnd": v.trocas_n1,
        "reducao_percentual": resultado.reducao_percentual,
        "solucao_grasp": json.dumps(g.melhor_solucao),
        "solucao_vnd": json.dumps(v.melhor_solucao),
        "historico_vnd": json.dumps(v.historico_makespan),
    }


def executar_experimentos(caminhos: Iterable[str | Path], seeds: Iterable[int],
                          iteracoes: int = 20, alpha: float = 0.5,
                          diretorio_saida: str | Path = "resultados/validacao") -> list[dict[str, Any]]:
    """Executa GRASP uma vez por par (arquivo, seed); VND aproveita seu resultado."""
    arquivos = [Path(c) for c in caminhos]
    sementes = list(seeds)
    if not arquivos or not sementes:
        raise ValueError("Informe pelo menos uma instância e uma seed")
    if len(set(arquivos)) != len(arquivos) or len(set(sementes)) != len(sementes):
        raise ValueError("Instâncias e seeds devem ser distintas")
    inteiro(iteracoes, "iterações", 1)
    validar_alpha(alpha)
    for seed in sementes:
        inteiro(seed, "seed")
    # Valida todos os arquivos antes de iniciar o lote.
    instancias = [(c, carregar_instancia(c)) for c in arquivos]
    linhas = []
    for caminho, instancia in instancias:
        for seed in sementes:
            resultado = comparar(instancia, seed, iteracoes, alpha)
            linhas.append(linha_experimento(caminho, instancia, resultado))
    saida = Path(diretorio_saida)
    salvar_csv(linhas, saida / "detalhado.csv")
    salvar_csv(resumir(linhas), saida / "resumo.csv")
    return linhas
