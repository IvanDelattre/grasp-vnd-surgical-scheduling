"""Audita e analisa os CSVs do experimento principal; não executa algoritmos.

Gera tabelas sem arredondamento explícito, figuras PNG de 600 dpi e relatório.
Dependências opcionais: requirements-analise.txt. Executar na raiz do projeto.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from grasp_vnd.avaliacao import makespan, verificar_validade
from grasp_vnd.experimentos import resumir, salvar_csv
from grasp_vnd.problema import carregar_instancia
from scripts.analisar_piloto import ler_detalhado


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def salvar_json(dados: Any, caminho: Path) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def auditar(saida: Path, piloto: Path, preflight: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verifica CSVs contra JSONs, objetivos, parâmetros e hashes preservados."""
    manifesto = json.loads((saida / "manifesto.json").read_text(encoding="utf-8"))
    anterior = json.loads((piloto / "manifesto.json").read_text(encoding="utf-8"))
    antes = json.loads(preflight.read_text(encoding="utf-8"))

    def exigir(condicao: bool, mensagem: str) -> None:
        if not condicao:
            raise ValueError(mensagem)

    exigir(manifesto["status"] == "concluido", "Lote incompleto: não tratar resultados parciais como completos")
    exigir(manifesto["iteracoes"] == 1000 and manifesto["alpha"] == 0.5,
           "Parâmetros do experimento principal divergentes")
    exigir(manifesto["seeds"] == list(range(10)), "Esperadas seeds 0..9")
    exigir(manifesto["fontes_algoritmos_sha256"] == anterior["fontes_algoritmos_sha256"]
           == antes["algoritmos_sha256"], "Código dos algoritmos difere do piloto")
    for nome, digest in manifesto["fontes_algoritmos_sha256"].items():
        exigir(sha256(RAIZ / "grasp_vnd" / nome) == digest, f"Arquivo alterado: {nome}")
    exigir(manifesto["instancias"] == anterior["instancias"], "Seleção ou dados diferem do piloto")
    for instancia in manifesto["instancias"]:
        exigir(sha256(Path(instancia["arquivo"])) == instancia["sha256_arquivo"], "Instância modificada")
    for caminho, digest in {**antes["piloto_sha256"], **antes["documentacao_piloto_sha256"]}.items():
        exigir(sha256(Path(caminho)) == digest, f"Arquivo do piloto modificado: {caminho}")
    exigir({p.as_posix() for p in piloto.rglob("*") if p.is_file()} == set(antes["piloto_sha256"]),
           "Conjunto de arquivos do piloto foi alterado")
    linhas = ler_detalhado(saida / "detalhado.csv")
    exigir(len(linhas) == manifesto["execucoes_concluidas"] == manifesto["execucoes_planejadas"] == 80,
           "Esperadas 80 comparações concluídas")
    exigir(len({(r["instancia"], r["seed"]) for r in linhas}) == 80, "Pares repetidos")
    por_instancia: dict[str, list[dict[str, Any]]] = {}
    for r in linhas:
        por_instancia.setdefault(r["instancia"], []).append(r)
        exigir(r["iteracoes"] == 1000 and r["alpha"] == 0.5 and r["origem"] == "SINTETICA",
               "Linha com parâmetros ou procedência incorretos")
        exigir(r["makespan_vnd"] <= r["makespan_grasp"], "Piora do VND")
        exigir(r["reducao_percentual"] == 100 * (r["makespan_grasp"] - r["makespan_vnd"]) / r["makespan_grasp"],
               "Redução percentual inconsistente")
        exigir(r["tempo_total_s"] == r["tempo_grasp_s"] + r["tempo_adicional_vnd_s"], "Tempo total incorreto")
    for grupo in por_instancia.values():
        exigir(sorted(r["seed"] for r in grupo) == list(range(10)), "Seeds incompletas por instância")
    por_par = {(r["instancia"], r["seed"]): r for r in linhas}
    for registro in manifesto["execucoes"]:
        exigir(registro["status"] == "concluida", "Execução com falha no manifesto")
        dados = json.loads((saida / registro["json"]).read_text(encoding="utf-8"))
        r = por_par[registro["instancia"], registro["seed"]]
        instancia = carregar_instancia(r["arquivo"])
        for chave, coluna in (("grasp", "makespan_grasp"), ("vnd", "makespan_vnd")):
            resultado = dados[chave]
            exigir(verificar_validade(instancia, resultado["melhor_solucao"]), "Solução inválida")
            exigir(makespan(instancia, resultado["melhor_solucao"]) == resultado["makespan"] == r[coluna],
                   "Makespan do CSV/JSON diverge da reavaliação")
            exigir(json.loads(r["solucao_" + chave]) == resultado["melhor_solucao"], "Solução CSV/JSON divergente")
        exigir(dados["grasp"]["iteracoes"] == 1000 and dados["grasp"]["seed"] == r["seed"], "Parâmetros JSON divergentes")
        exigir(dados["vnd"]["makespan_inicial"] == dados["grasp"]["makespan"], "Ponto de partida divergente")
        exigir(dados["grasp"]["tempo_execucao"] == r["tempo_grasp_s"], "Tempo GRASP alterado")
        exigir(dados["vnd"]["tempo_execucao"] == r["tempo_adicional_vnd_s"], "Tempo VND alterado")
        exigir(dados["tempo_total"] == r["tempo_total_s"], "Tempo total alterado")
        exigir(dados["vnd"]["realocacoes_aceitas"] == r["realocacoes_aceitas"], "Contador alterado")
    # Confere os agregados já persistidos pelo executor, sem sobrescrevê-los.
    with (saida / "resumo.csv").open(encoding="utf-8", newline="") as arquivo:
        gravados = {r["instancia"]: r for r in csv.DictReader(arquivo)}
    for r in resumir(linhas):
        for chave, valor in r.items():
            exigir(str(valor) == gravados[r["instancia"]][chave], f"Resumo divergente em {chave}")
    exigir(math.isclose(sum(r["tempo_total_s"] for r in linhas), manifesto["tempo_algoritmos_total_s"], rel_tol=1e-12),
           "Soma dos tempos diverge do manifesto")
    return linhas, manifesto


def agregar(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agregados calculados dos CSVs, sem arredondamento de armazenamento."""
    resultado = resumir(linhas)
    for r in resultado:
        grupo = [a for a in linhas if a["instancia"] == r["instancia"]]
        instancia = carregar_instancia(grupo[0]["arquivo"])
        r.update(
            numero_cirurgias=len(instancia.cirurgias), numero_salas=instancia.numero_salas,
            perfil=instancia.metadados["perfil"], seed_geracao=instancia.metadados["seed"],
            pior_grasp=max(a["makespan_grasp"] for a in grupo),
            pior_vnd=max(a["makespan_vnd"] for a in grupo),
            mediana_reducao_percentual=median(a["reducao_percentual"] for a in grupo),
            menor_reducao_percentual=min(a["reducao_percentual"] for a in grupo),
            maior_reducao_percentual=max(a["reducao_percentual"] for a in grupo),
            desvio_tempo_grasp_s=stdev(a["tempo_grasp_s"] for a in grupo),
            desvio_tempo_total_s=stdev(a["tempo_total_s"] for a in grupo),
            custo_adicional_percentual=100 * r["media_tempo_adicional_vnd_s"] / r["media_tempo_grasp_s"],
            total_realocacoes=sum(a["realocacoes_aceitas"] for a in grupo),
        )
    return sorted(resultado, key=lambda r: (r["numero_cirurgias"], r["perfil"]))


def gerar_figuras(linhas: list[dict[str, Any]], resumos: list[dict[str, Any]], destino: Path) -> dict[str, Any]:
    """Figuras descritivas; barras de erro são DP, nunca intervalos de confiança."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import MaxNLocator
    from PIL import Image

    destino.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10,
        "axes.labelsize": 10, "axes.spines.top": False, "axes.spines.right": False,
        "axes.axisbelow": True, "grid.alpha": 0.2, "savefig.facecolor": "white",
    })
    azul, laranja = "#0072B2", "#D55E00"
    arquivos = []

    def salvar(fig, nome: str) -> None:
        caminho = destino / nome
        fig.savefig(caminho, dpi=600, bbox_inches="tight", metadata={"Description": "Instâncias SINTÉTICAS; 1000 iterações; alpha=0.5; seeds=0..9"})
        plt.close(fig)
        arquivos.append(caminho)

    fig, eixos = plt.subplots(2, 4, figsize=(7.2, 5.5))
    for linha, perfil in enumerate(("simples", "sequencia")):
        for coluna, n in enumerate((11, 50, 100, 200)):
            r = next(a for a in resumos if a["perfil"] == perfil and a["numero_cirurgias"] == n)
            grupo = sorted((a for a in linhas if a["instancia"] == r["instancia"]), key=lambda a: a["seed"])
            ax = eixos[linha, coluna]
            for a in grupo:
                deslocamento = (a["seed"] - 4.5) * 0.014
                ax.plot([deslocamento, 1 + deslocamento], [a["makespan_grasp"], a["makespan_vnd"]], color="0.65", linewidth=0.8, alpha=0.65)
                ax.scatter(deslocamento, a["makespan_grasp"], color=azul, s=18, zorder=3)
                ax.scatter(1 + deslocamento, a["makespan_vnd"], color=laranja, marker="s", s=18, zorder=3)
            ax.errorbar([0.15, 1.15], [r["media_grasp"], r["media_vnd"]],
                        yerr=[r["desvio_amostral_grasp"], r["desvio_amostral_vnd"]],
                        fmt="D", color="black", markersize=3.5, capsize=3, linewidth=1, zorder=4)
            valores = [a[c] for a in grupo for c in ("makespan_grasp", "makespan_vnd")]
            valores.extend([r["media_grasp"] - r["desvio_amostral_grasp"],
                            r["media_grasp"] + r["desvio_amostral_grasp"],
                            r["media_vnd"] - r["desvio_amostral_vnd"],
                            r["media_vnd"] + r["desvio_amostral_vnd"]])
            margem = max(0.6, (max(valores) - min(valores)) * 0.2)
            ax.set_ylim(math.floor(min(valores) - margem), math.ceil(max(valores) + margem))
            ax.set_xlim(-0.25, 1.35)
            ax.set_xticks([0, 1], ["GRASP", "GRASP\n+ VND"])
            ax.tick_params(axis="both", labelsize=8)
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.set_title(f"N={n}, M={r['numero_salas']}\n{perfil}", fontsize=9)
            ax.grid(axis="y")
            if coluna == 0:
                ax.set_ylabel("Makespan (blocos de 30 min)", fontsize=9)
    fig.suptitle("Qualidade pareada — instâncias sintéticas", fontsize=11)
    fig.legend(handles=[Line2D([], [], color="0.65", marker="o", markersize=3, label="Mesma seed ligada entre métodos"),
                        Line2D([], [], color="black", marker="D", linestyle="none", markersize=4, label="Média ± desvio padrão amostral")],
               loc="lower center", ncol=1, bbox_to_anchor=(0.5, 0.025), frameon=False, fontsize=8)
    fig.text(0.5, 0.005, "10 seeds/painel; escalas verticais independentes. Menor makespan é melhor.", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.13, 1, 0.95))
    salvar(fig, "qualidade_pareada.png")

    etiquetas = [f"{r['numero_cirurgias']}\n{r['perfil']}" for r in resumos]
    posicoes = list(range(len(resumos)))
    fig, (ax, custo) = plt.subplots(2, 1, figsize=(7.2, 6.2), gridspec_kw={"height_ratios": [2, 1]})
    g = [r["media_tempo_grasp_s"] for r in resumos]
    v = [r["media_tempo_adicional_vnd_s"] for r in resumos]
    esquerda = [i - 0.2 for i in posicoes]
    direita = [i + 0.2 for i in posicoes]
    ax.bar(esquerda, g, width=0.35, color=azul, yerr=[r["desvio_tempo_grasp_s"] for r in resumos], capsize=2)
    ax.bar(direita, g, width=0.35, color=azul, label="Tempo GRASP")
    ax.bar(direita, v, bottom=g, width=0.35, color=laranja, label="Tempo adicional VND")
    ax.errorbar(direita, [a + b for a, b in zip(g, v)], yerr=[r["desvio_tempo_total_s"] for r in resumos], fmt="none", ecolor="black", capsize=2, linewidth=0.8)
    ax.set_xticks(posicoes, etiquetas, fontsize=8)
    ax.set_ylabel("Tempo médio por execução (s)")
    ax.set_title("Esquerda: GRASP | Direita: GRASP + VND", fontsize=10)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y")
    ax.legend(frameon=False)
    extras = [r["custo_adicional_percentual"] for r in resumos]
    custo.bar(posicoes, extras, width=0.55, color=laranja)
    custo.set_xticks(posicoes, etiquetas, fontsize=8)
    custo.set_ylabel("Custo adicional VND (%)")
    custo.set_title("100 × tempo médio VND / tempo médio GRASP")
    custo.set_ylim(0, max(1, max(extras) * 1.25))
    custo.grid(axis="y")
    for x, valor in zip(posicoes, extras):
        custo.annotate(f"{valor:.1f}%", (x, valor), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    fig.suptitle("Custo computacional — 1.000 iterações e 10 seeds", fontsize=11)
    fig.text(0.5, 0.003, "Erros: DP amostral. Tempos internos; medições sequenciais; início de processos e I/O excluídos.", ha="center", fontsize=7.5)
    fig.tight_layout(rect=(0, 0.025, 1, 0.96))
    salvar(fig, "tempo_comparativo.png")

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    dados = [[a["reducao_percentual"] for a in sorted(linhas, key=lambda a: a["seed"]) if a["instancia"] == r["instancia"]] for r in resumos]
    ax.boxplot(dados, positions=posicoes, widths=0.5, showfliers=False,
               medianprops={"color": "black"}, boxprops={"color": "0.4"}, whiskerprops={"color": "0.4"})
    for x, valores in zip(posicoes, dados):
        ax.scatter([x + (i - 4.5) * 0.022 for i in range(len(valores))], valores, color=azul, s=22, zorder=3)
    ax.scatter(posicoes, [mean(a) for a in dados], color=laranja, marker="D", s=30, zorder=4, label="Média pareada")
    ax.set_xticks(posicoes, [f"{r['numero_cirurgias']}\n{r['perfil']}\n{r['execucoes_com_melhoria']}/10" for r in resumos], fontsize=8)
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set_ylabel("Redução pareada do makespan (%)")
    ax.set_title("Ganho individual da pós-otimização VND — dados sintéticos", fontsize=10)
    ax.grid(axis="y")
    ax.legend(frameon=False)
    fig.text(0.5, 0.005, "Pontos: seeds; caixas: quartis e mediana. Rótulos: N, perfil e melhorias/10; análise descritiva.", ha="center", fontsize=7.5)
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    salvar(fig, "reducao_percentual.png")
    metadados = {"matplotlib": matplotlib.__version__, "dpi_solicitado": 600, "figuras": {}}
    for caminho in arquivos:
        with Image.open(caminho) as img:
            metadados["figuras"][caminho.name] = {"pixels": list(img.size), "dpi": list(img.info.get("dpi", ())), "sha256": sha256(caminho)}
    return metadados


def f(valor: float, casas: int = 3) -> str:
    """Arredondamento somente de apresentação."""
    return f"{valor:.{casas}f}".replace(".", ",")


def etiqueta(r: dict[str, Any]) -> str:
    return f"{r['numero_cirurgias']} / {r['numero_salas']} / {r['perfil']}"


def gerar_relatorio(saida: Path, piloto: Path, preflight: Path, documento: Path) -> dict[str, Any]:
    linhas, manifesto = auditar(saida, piloto, preflight)
    resumos = agregar(linhas)
    salvar_csv(resumos, saida / "analise_resumo.csv")
    campos = ("instancia", "seed", "makespan_grasp", "makespan_vnd", "reducao_percentual",
              "tempo_grasp_s", "tempo_adicional_vnd_s", "tempo_total_s", "realocacoes_aceitas")
    casos = sorted(({c: r[c] for c in campos} for r in linhas),
                   key=lambda r: (-r["reducao_percentual"], r["instancia"], r["seed"]))
    salvar_csv(casos, saida / "casos_melhoria.csv")
    positivos = [r for r in casos if r["reducao_percentual"] > 0]
    nulos = [r for r in casos if r["reducao_percentual"] == 0]
    total_g = sum(r["tempo_grasp_s"] for r in linhas)
    total_v = sum(r["tempo_adicional_vnd_s"] for r in linhas)
    sumario: dict[str, Any] = {
        "tipo_dado": "MEDICAO_EXPERIMENTO_PRINCIPAL_REDUZIDO",
        "comparacoes": len(linhas), "instancias": len(resumos), "iteracoes": 1000,
        "alpha": 0.5, "seeds": list(range(10)),
        "execucoes_com_melhoria": len(positivos), "execucoes_sem_melhoria": len(nulos),
        "percentual_execucoes_com_melhoria": 100 * len(positivos) / len(linhas),
        "media_reducao_percentual_pareada": mean(r["reducao_percentual"] for r in linhas),
        "mediana_reducao_percentual_pareada": median(r["reducao_percentual"] for r in linhas),
        "tempo_grasp_soma_s": total_g, "tempo_vnd_soma_s": total_v,
        "tempo_algoritmos_soma_s": total_g + total_v,
        "tempo_parede_total_s": manifesto["tempo_parede_total_s"],
        "custo_adicional_global_percentual": 100 * total_v / total_g,
        "maior_reducao_individual_percentual": casos[0]["reducao_percentual"],
        "melhores_casos_empatados": [r for r in casos if r["reducao_percentual"] == casos[0]["reducao_percentual"]],
        "menor_reducao_positiva": min(positivos, key=lambda r: r["reducao_percentual"]) if positivos else None,
        "caso_sem_melhoria_maior_tempo_vnd": max(nulos, key=lambda r: r["tempo_adicional_vnd_s"]) if nulos else None,
    }
    figuras = gerar_figuras(linhas, resumos, saida / "figuras")
    salvar_json(sumario, saida / "sumario.json")
    auditoria = {
        "status": "APROVADA", "comparacoes_auditadas": len(linhas),
        "testes_antes_execucao": json.loads(preflight.read_text(encoding="utf-8"))["testes_antes"],
        "mesmos_algoritmos_do_piloto": True, "mesmas_instancias_do_piloto": True,
        "arquivos_piloto_preservados": True, "objetivos_reavaliados": True,
        "csv_detalhado_sha256": sha256(saida / "detalhado.csv"),
        "csv_resumo_sha256": sha256(saida / "resumo.csv"),
        "manifesto_sha256": sha256(saida / "manifesto.json"),
        "script_analise_sha256": sha256(Path(__file__)),
        "figuras": figuras,
    }
    testes_finais = saida / "testes_finais.json"
    if testes_finais.exists():
        auditoria["testes_finais"] = json.loads(testes_finais.read_text(encoding="utf-8"))
    salvar_json(auditoria, saida / "auditoria.json")
    relativo = Path(os.path.relpath(saida, documento.parent)).as_posix()
    horario = lambda s: datetime.fromisoformat(s).astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S %Z")
    texto = [
        "# Resultados do experimento principal reduzido", "",
        "## Configuração e integridade", "",
        "Foram avaliadas as mesmas **oito instâncias SINTÉTICAS do piloto**, nos perfis `simples` e `sequencia`, com N=11, 50, 100 e 200 cirurgias. Não são dados hospitalares reais nem uma reprodução dos resultados originais do artigo.", "",
        "Cada instância foi executada com **1.000 iterações GRASP, alpha=0,5 e 10 seeds, 0 a 9**. O VND foi aplicado uma única vez à cópia exata da melhor solução final de cada GRASP. O custo GRASP é compartilhado na comparação pareada; não houve nova execução GRASP para a versão com VND. Execuções sequenciais, sem testes ou geração de gráficos concorrentes às medições.", "",
        "Os **85 testes passaram em 2,14 s antes de iniciar**. Os hashes do código e das instâncias foram conferidos contra o piloto antes e depois do lote. GRASP, construção, N1, N2, VND, objetivo e comparação permaneceram inalterados. Todos os arquivos de resultados e a documentação anterior do piloto foram preservados.", "",
        "A verificação após a execução incluiu os três testes novos da análise: **88 testes passaram em 2,61 s**, cobrindo percentuais pareados, preservação de precisão e recusa de publicação de lote parcial.", "",
        f"Ambiente de execução: Python {manifesto['python']}; {manifesto['plataforma']}; processador `{manifesto['processador']}`; {manifesto['cpu_logicas']} CPUs lógicas. A disponibilidade de múltiplos núcleos não foi usada para paralelizar o lote.", "",
        f"Início: **{horario(manifesto['inicio_utc'])}**; fim: **{horario(manifesto['fim_utc'])}**, no fuso America/Sao_Paulo. O manifesto preserva também os horários UTC originais.", "",
        "| Instância SINTÉTICA | N | Salas | Perfil | Seed de geração |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for r in resumos:
        texto.append(f"| {r['instancia']} | {r['numero_cirurgias']} | {r['numero_salas']} | {r['perfil']} | {r['seed_geracao']} |")
    texto += ["", "As seeds de geração identificam o arquivo fixo de entrada. As seeds 0..9 controlam o GRASP; não geram novas instâncias.", "",
              "Comando efetivamente executado na raiz:", "", "```powershell",
              ".\\.venv\\Scripts\\python.exe -m pytest -q",
              ".\\.venv\\Scripts\\python.exe -u scripts/piloto_experimental.py --iteracoes 1000 --seeds 0 1 2 3 4 5 6 7 8 9 --alpha 0.5 --limite-execucao 300 --limite-total 7200 --saida resultados/principal_reduzido",
              "```", "",
              "Os limites de 300 s por execução e 7.200 s no total foram mantidos. O executor salva JSON individual e atualiza os CSVs após cada comparação; recusa sobrescrever saídas existentes.", "",
              "## Execução efetiva", "",
              f"Estado final: **{manifesto['status']}**, **{len(linhas)}/80 comparações concluídas**. Tempo de parede efetivo: **{f(manifesto['tempo_parede_total_s'], 6)} s ({f(manifesto['tempo_parede_total_s'] / 60, 2)} min)**, sem timeout ou falha. Soma dos tempos internos dos algoritmos: **{f(total_g + total_v, 6)} s**; GRASP: {f(total_g, 6)} s; adicional VND: {f(total_v, 6)} s.", "",
              "O tempo de parede inclui inicialização de 80 processos, leitura dos arquivos, serialização, verificações externas, checkpoints e comunicação. Os tempos internos vêm de `perf_counter` e incluem as validações internas dos algoritmos; não incluem geração posterior de gráficos, análise ou testes. Por isso, a soma dos tempos internos difere do tempo de parede.", "",
              "## Qualidade por instância", "",
              "Makespan em **blocos de 30 minutos**. Menor é melhor. Média e DP amostral (denominador n−1) são calculados nas 10 seeds de cada instância. A redução é a média dos percentuais **pareados**, `100*(G−V)/G`, não a razão entre médias. Os melhores valores de cada método são mínimos sobre seeds e não necessariamente pertencem ao mesmo par.", "",
              "| N / salas / perfil | Melhor G | Média G | DP G | Melhor G+VND | Média G+VND | DP G+VND | Redução média pareada (%) |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in resumos:
        texto.append(f"| {etiqueta(r)} | {r['melhor_grasp']} | {f(r['media_grasp'])} | {f(r['desvio_amostral_grasp'])} | {r['melhor_vnd']} | {f(r['media_vnd'])} | {f(r['desvio_amostral_vnd'])} | {f(r['media_reducao_percentual'])} |")
    texto += ["", "## Frequência e magnitude das melhorias", "",
              "| N / salas / perfil | Com melhoria | Melhoria (%) | Sem melhoria | Mediana da redução (%) | Maior redução individual (%) | Realocações aceitas (total) |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in resumos:
        texto.append(f"| {etiqueta(r)} | {r['execucoes_com_melhoria']}/10 | {f(r['percentual_execucoes_com_melhoria'], 1)} | {r['execucoes_sem_melhoria']} | {f(r['mediana_reducao_percentual'])} | {f(r['maior_reducao_percentual'])} | {r['total_realocacoes']} |")
    texto += ["", f"No conjunto observado, o VND melhorou **{len(positivos)}/{len(linhas)} execuções ({f(sumario['percentual_execucoes_com_melhoria'], 2)}%)**, não alterou o makespan em **{len(nulos)}** e não piorou nenhuma. A redução média pareada entre as 80 execuções foi **{f(sumario['media_reducao_percentual_pareada'])}%**, e a mediana foi {f(sumario['mediana_reducao_percentual_pareada'])}%. Essa média global dá o mesmo peso a cada uma das oito instâncias, pois todas têm 10 execuções; não é uma métrica de desempenho clínico.", "",
              "## Custo computacional", "",
              "Tempos médios em segundos por execução. Custo adicional = `100*tempo_médio_VND/tempo_médio_GRASP`; é uma razão das médias. Total = GRASP + VND, com uma única execução GRASP.", "",
              "| N / salas / perfil | GRASP médio (s) | VND adicional médio (s) | Total médio (s) | Custo adicional (%) |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for r in resumos:
        texto.append(f"| {etiqueta(r)} | {f(r['media_tempo_grasp_s'], 6)} | {f(r['media_tempo_adicional_vnd_s'], 6)} | {f(r['media_tempo_total_s'], 6)} | {f(r['custo_adicional_percentual'], 2)} |")
    texto += ["", f"Considerando a soma de todos os tempos GRASP como base, o VND acrescentou **{f(sumario['custo_adicional_global_percentual'], 2)}%** de tempo computacional. Esse valor global pondera mais as instâncias demoradas e difere da média simples dos percentuais da tabela.", "",
              "## Melhores e piores casos observados", ""]
    if positivos:
        texto += ["Cinco maiores reduções individuais (empates ordenados por identificador e seed):", "",
                  "| Instância SINTÉTICA | Seed | GRASP | Após VND | Redução (%) | Realocações |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for r in positivos[:5]:
            texto.append(f"| {r['instancia']} | {r['seed']} | {r['makespan_grasp']} | {r['makespan_vnd']} | {f(r['reducao_percentual'])} | {r['realocacoes_aceitas']} |")
        menor = sumario["menor_reducao_positiva"]
        texto += ["", f"Menor ganho estritamente positivo: `{menor['instancia']}`, seed {menor['seed']}, makespan **{menor['makespan_grasp']} → {menor['makespan_vnd']}**, redução {f(menor['reducao_percentual'])}%."]
    else:
        texto += ["Não houve redução estrita após 1.000 iterações GRASP em nenhuma das 80 execuções. Esse resultado foi mantido sem modificar os algoritmos ou o protocolo."]
    if nulos:
        pior = sumario["caso_sem_melhoria_maior_tempo_vnd"]
        texto += ["", f"O menor ganho observado foi **0%**, em {len(nulos)} execuções. Entre elas, o maior custo adicional VND ocorreu em `{pior['instancia']}`, seed {pior['seed']}: **{f(pior['tempo_adicional_vnd_s'], 6)} s**, mantendo makespan {pior['makespan_grasp']}. Ausência de redução não significa falha de implementação nem certifica ótimo global."]
    com_ganho = [r for r in resumos if r["execucoes_com_melhoria"]]
    sem_ganho = [r for r in resumos if not r["execucoes_com_melhoria"]]
    texto += ["", "## Interpretação científica", "",
              f"Houve alguma melhoria em **{len(com_ganho)}/8 instâncias**. As instâncias sem redução nas 10 seeds foram: " + ("; ".join(f"`{r['instancia']}`" for r in sem_ganho) if sem_ganho else "nenhuma") + "."]
    if com_ganho:
        melhor_media = max(com_ganho, key=lambda r: r["media_reducao_percentual"])
        texto += ["", f"A maior redução média pareada ocorreu em **{etiqueta(melhor_media)}**, com {f(melhor_media['media_reducao_percentual'])}% e melhoria em {melhor_media['execucoes_com_melhoria']}/10 seeds. O efeito é específico ao arquivo e às seeds avaliados; a classe de instâncias inteira não foi amostrada."]
        mesmos_melhores = [r for r in com_ganho if r["melhor_grasp"] == r["melhor_vnd"]]
        if mesmos_melhores:
            texto += ["", "Em " + "; ".join(etiqueta(r) for r in mesmos_melhores) + ", houve redução da média sem alteração do melhor valor observado sobre as dez seeds. Ganho médio e obtenção de um novo mínimo são resultados distintos."]
        dispersao_maior = [r for r in com_ganho if r["desvio_amostral_vnd"] > r["desvio_amostral_grasp"]]
        if dispersao_maior:
            texto += ["", "O DP do makespan após VND foi maior que o do GRASP em " + "; ".join(etiqueta(r) for r in dispersao_maior) + ". Melhorias concentradas em parte das seeds podem aumentar a dispersão, mesmo sem piorar qualquer par individual. Não se interpreta a redução da média como redução automática de variabilidade."]
    texto += ["", "A N1 atua apenas na ordem interna de cada sala. A N2 pode alterar a distribuição de cirurgias entre salas; isso explica o mecanismo pelo qual ainda pode existir ganho após o GRASP, mesmo quando todas as salas estão em ótimo local por N1. O resultado não demonstra que todo caso se beneficia da pós-otimização.", "",
              "Quando não houve ganho, o ótimo local por realocação estrita da N2 já estava atingido para a solução recebida, conforme a vizinhança definida. Empates entre salas críticas e movimentos que precisariam atravessar um platô podem impedir melhoria imediata. Não se investigou causalmente qual desses fatores explica cada execução, e não se adicionaram movimentos neutros ou vizinhanças para obter ganhos artificiais.", "",
              "### Limite da comparação sem orçamento equivalente", "",
              "A comparação mede o efeito incremental do VND sobre a mesma solução de partida e mantém fixas as 1.000 iterações do GRASP. A versão GRASP+VND recebe **tempo adicional**. Portanto, resultados melhores não permitem concluir maior eficiência sob um orçamento computacional igual. Para isso seria necessário um experimento separado com GRASP isolado executado por tempo equivalente, mantendo regras de parada comparáveis. Esse experimento não foi realizado nesta etapa.", "",
              "### Limitações dos dados e da inferência", "",
              "As oito instâncias são sintéticas e há um único arquivo por combinação tamanho/perfil. Durações e preparações são geradas segundo escolhas do projeto; não representam distribuições hospitalares validadas. As 10 seeds medem variabilidade da heurística em cada arquivo, não variabilidade entre hospitais ou entre muitas instâncias independentes da mesma classe. Os perfis alteram simultaneamente durações e preparações, e a quantidade de salas varia com N; comparações entre perfis/tamanhos não isolam causalmente o efeito de N, dos preparos ou da ocupação por sala.", "",
              "Não foram aplicados testes de significância ou estimativas de incerteza com desenho apropriado. Desvios padrão, boxplots e frequências são descritivos; **não se afirma superioridade estatística**. Também não há comparação com ótimo global, limite inferior certificado ou agenda hospitalar real. Seeds compartilhadas mantêm o pareamento e não transformam 80 execuções em 80 instâncias independentes.", "",
              "Os tempos dependem da carga externa, frequência do processador, aquecimento e ambiente. Não houve fixação de afinidade de CPU. O lote foi sequencial e os gráficos foram gerados somente depois; os DP dos tempos, quando exibidos, refletem variação entre execuções, não intervalos de confiança.", "",
              "## Figuras para artigo", "",
              "Todos os PNGs foram exportados em **600 dpi**, com fonte legível, fundo branco e paleta azul/laranja. Não são imagens geradas por IA. Pontos ligados representam a mesma seed. As barras de erro de qualidade e tempo são DP amostrais; a figura de qualidade usa escalas verticais independentes entre painéis e não usa barras de altura truncada.", "",
              f"![Qualidade pareada]({relativo}/figuras/qualidade_pareada.png)", "",
              f"![Tempo comparativo]({relativo}/figuras/tempo_comparativo.png)", "",
              f"![Redução percentual pareada]({relativo}/figuras/reducao_percentual.png)", "",
              "## Conclusão preliminar", ""]
    if positivos:
        texto += [f"Neste conjunto sintético, a pós-otimização VND foi útil para refinar parte das melhores soluções GRASP: {len(positivos)}/{len(linhas)} execuções tiveram redução estrita, com redução média pareada global de {f(sumario['media_reducao_percentual_pareada'])}%. O custo adicional global observado foi {f(sumario['custo_adicional_global_percentual'], 2)}%. A utilidade prática depende da importância de ganhos dessa magnitude e do orçamento disponível; não há evidência aqui para declarar superioridade estatística, vantagem sob tempo equivalente ou benefício clínico."]
    else:
        texto += ["Neste conjunto sintético, o VND não trouxe melhoria adicional após 1.000 iterações GRASP e aumentou o tempo total. Sob o protocolo observado, isso não sustenta uma vantagem de qualidade da pós-otimização. O resultado não deve ser generalizado a outros arquivos, parâmetros ou vizinhanças sem novos experimentos."]
    texto += ["", "## Arquivos, precisão e reprodução", "",
              f"- [CSV por execução]({relativo}/detalhado.csv): fonte dos cálculos, 80 linhas, sem arredondamento explícito.",
              f"- [Resumo original]({relativo}/resumo.csv) e [resumo ampliado da análise]({relativo}/analise_resumo.csv).",
              f"- [Casos ordenados de melhoria]({relativo}/casos_melhoria.csv) e [sumário numérico]({relativo}/sumario.json).",
              f"- [Manifesto]({relativo}/manifesto.json), JSONs individuais em `execucoes/` e [auditoria]({relativo}/auditoria.json).", "",
              "Os cálculos são realizados diretamente dos CSVs. Os números brutos e os agregados são armazenados com a precisão de `int`/`float` disponível em Python; o arredondamento explícito ocorre apenas nas tabelas e nos rótulos das figuras. O resumo original foi conferido com os agregados recalculados, sem sobrescrevê-lo.", "",
              "Para reproduzir somente a análise, sem reexecutar o experimento:", "", "```powershell",
              ".\\.venv\\Scripts\\python.exe -m pip install -r requirements-analise.txt",
              ".\\.venv\\Scripts\\python.exe scripts/analisar_principal.py", "```", ""]
    documento.parent.mkdir(parents=True, exist_ok=True)
    documento.write_text("\n".join(texto), encoding="utf-8")
    return sumario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=Path("resultados/principal_reduzido"))
    parser.add_argument("--piloto", type=Path, default=Path("resultados/piloto"))
    parser.add_argument("--preflight", type=Path, default=Path("resultados/principal_reduzido_preflight.json"))
    parser.add_argument("--documento", type=Path, default=Path("docs/RESULTADOS_PRINCIPAIS.md"))
    args = parser.parse_args()
    print(json.dumps(gerar_relatorio(args.saida, args.piloto, args.preflight, args.documento), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
