"""Regera tabelas e projeções a partir dos dados medidos; não roda algoritmos."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from grasp_vnd.experimentos import resumir, salvar_csv
from grasp_vnd.problema import carregar_instancia


def ler_detalhado(caminho: Path) -> list[dict[str, Any]]:
    inteiros = {"numero_cirurgias", "numero_salas", "unidade_minutos", "seed", "iteracoes",
                "makespan_grasp", "makespan_vnd", "realocacoes_aceitas", "avaliacoes_n1_grasp",
                "trocas_n1_grasp", "avaliacoes_n2_vnd", "avaliacoes_n1_vnd", "trocas_n1_vnd"}
    reais = {"alpha", "tempo_grasp_s", "tempo_adicional_vnd_s", "tempo_total_s", "reducao_percentual"}
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return [{k: int(v) if k in inteiros else float(v) if k in reais else v
                 for k, v in linha.items()} for linha in csv.DictReader(arquivo)]


def cargas(n: int, m: int) -> tuple[float, float]:
    """Indicadores de trabalho para interpolação, sem estimar qualidade.

    G: N^2/M aproxima o número de pares N1 por varredura (salas balanceadas),
    a menos de constantes e termos lineares; varreduras extras ficam na taxa.
    V: N vezes o número de realocações de uma varredura com salas balanceadas;
    o fator N representa o custo de copiar/validar cada candidato.
    Não são limites exatos do tempo nem da quantidade de varreduras.
    """
    return n * n / m, n * n * (m - 1) * (n / m + 1)


def projetar(linhas: list[dict[str, Any]], arquivos: list[Path],
             iteracoes: int = 1000, execucoes: int = 30) -> list[dict[str, Any]]:
    """Interpola taxas por carga entre tamanhos medidos do mesmo perfil.

    GRASP escala proporcionalmente às iterações; VND é aplicado uma única vez.
    A faixa usa mínimos/máximos das três seeds e não é intervalo de confiança.
    """
    resumo = {r["instancia"]: r for r in resumir(linhas)}
    ancoras: dict[str, list[dict[str, Any]]] = {}
    for identificador, agregado in resumo.items():
        grupo = [r for r in linhas if r["instancia"] == identificador]
        instancia = carregar_instancia(grupo[0]["arquivo"])
        n, m = len(instancia.cirurgias), instancia.numero_salas
        wg, wv = cargas(n, m)
        ancoras.setdefault(instancia.metadados["perfil"], []).append({
            "n": n,
            "g": agregado["media_tempo_grasp_s"] / wg / agregado["iteracoes"],
            "v": agregado["media_tempo_adicional_vnd_s"] / wv,
            "g_min": min(r["tempo_grasp_s"] for r in grupo) / wg / agregado["iteracoes"],
            "g_max": max(r["tempo_grasp_s"] for r in grupo) / wg / agregado["iteracoes"],
            "v_min": min(r["tempo_adicional_vnd_s"] for r in grupo) / wv,
            "v_max": max(r["tempo_adicional_vnd_s"] for r in grupo) / wv,
        })
    resultado = []
    for caminho in arquivos:
        instancia = carregar_instancia(caminho)
        n, m = len(instancia.cirurgias), instancia.numero_salas
        perfil = instancia.metadados["perfil"]
        pontos = sorted(ancoras[perfil], key=lambda a: a["n"])
        if not pontos[0]["n"] <= n <= pontos[-1]["n"]:
            raise ValueError("Projeção requer âncoras que cubram o intervalo de tamanhos")
        inferior = max((a for a in pontos if a["n"] <= n), key=lambda a: a["n"])
        superior = min((a for a in pontos if a["n"] >= n), key=lambda a: a["n"])
        peso = 0 if inferior["n"] == superior["n"] else (n - inferior["n"]) / (superior["n"] - inferior["n"])

        def taxa(campo: str) -> float:
            return inferior[campo] * (1 - peso) + superior[campo] * peso

        wg, wv = cargas(n, m)
        g, v = iteracoes * wg * taxa("g"), wv * taxa("v")
        resultado.append({
            "tipo_dado": "PROJECAO_NAO_MEDIDA", "instancia": instancia.identificador,
            "perfil": perfil, "numero_cirurgias": n, "numero_salas": m,
            "iteracoes_projetadas": iteracoes, "execucoes_projetadas": execucoes,
            "base": "tempo_piloto_mesma_instancia" if inferior["n"] == superior["n"] else "interpolacao_taxas_por_carga",
            "ancora_inferior_n": inferior["n"], "ancora_superior_n": superior["n"],
            "tempo_grasp_por_execucao_s": g, "tempo_vnd_por_execucao_s": v,
            "tempo_lote_grasp_s": execucoes * g, "tempo_lote_vnd_s": execucoes * v,
            "tempo_lote_total_s": execucoes * (g + v),
            "faixa_seeds_min_s": execucoes * (iteracoes * wg * taxa("g_min") + wv * taxa("v_min")),
            "faixa_seeds_max_s": execucoes * (iteracoes * wg * taxa("g_max") + wv * taxa("v_max")),
            "cenario_vnd_10x_s": execucoes * (g + 10 * v),
        })
    return resultado


def f(valor: float, casas: int = 3) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def gerar_relatorio(piloto: Path, suite: Path, documento: Path) -> dict[str, Any]:
    manifesto = json.loads((piloto / "manifesto.json").read_text(encoding="utf-8"))
    if manifesto["status"] != "concluido":
        raise ValueError("Piloto parcial: examine o manifesto antes de projetar o lote completo")
    linhas = ler_detalhado(piloto / "detalhado.csv")
    resumos = resumir(linhas)
    arquivos = sorted(suite.glob("*.json"))
    if len(arquivos) != 14:
        raise ValueError("Esperadas as 14 instâncias sintéticas para a projeção")
    projecoes = projetar(linhas, arquivos)
    salvar_csv(projecoes, piloto / "projecao_principal.csv")
    total_g = sum(r["tempo_lote_grasp_s"] for r in projecoes)
    total_v = sum(r["tempo_lote_vnd_s"] for r in projecoes)
    total = total_g + total_v
    selecionados = {r["instancia"] for r in linhas}
    reduzido = sum(r["tempo_lote_total_s"] / 3 for r in projecoes if r["instancia"] in selecionados)
    projecao = {
        "tipo_dado": "PROJECAO_NAO_MEDIDA", "metodo": "interpolacao_taxas_por_carga_por_perfil",
        "iteracoes": 1000, "execucoes_por_instancia": 30, "instancias": 14,
        "grasp_s": total_g, "vnd_s": total_v, "total_s": total,
        "faixa_seeds_min_s": sum(r["faixa_seeds_min_s"] for r in projecoes),
        "faixa_seeds_max_s": sum(r["faixa_seeds_max_s"] for r in projecoes),
        "cenario_vnd_10x_s": sum(r["cenario_vnd_10x_s"] for r in projecoes),
        "reserva_2x_total_s": 2 * total,
        "reduzido_8_instancias_10_seeds_1000_iteracoes_s": reduzido,
        "reduzido_reserva_2x_s": 2 * reduzido,
    }
    (piloto / "projecao_principal.json").write_text(json.dumps(projecao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    texto = [
        "# Etapa 4.2 — Validação experimental preliminar", "",
        "## Configuração e verificação inicial", "",
        "Piloto de 25/10/2026 com dados **SINTÉTICOS**, sem relação estatística presumida com dados hospitalares do artigo.", "",
        "A revisão do código confirmou:", "",
        "- GRASP e VND minimizam o mesmo makespan de `avaliacao.py`; a avaliação incremental da N2 usa o mesmo máximo dos tempos de salas.",
        "- `comparacao.py` passa uma cópia exata de `grasp.melhor_solucao` ao VND, executado uma única vez após o GRASP.",
        "- N1 minimiza o tempo individual de cada sala, inclusive quando o makespan global não muda.",
        "- N2 enumera toda origem, cirurgia, destino diferente e posição de inserção, incluindo extremos e salas vazias.",
        "- `tempo_sala` inclui durações e preparações direcionais consecutivas; a construção inclui o preparo da última cirurgia; o delta N1 preserva a soma das durações e atualiza os arcos afetados.", "",
        "Os **81 testes existentes passaram em 1,94 s** antes do piloto. Após acrescentar três testes do protocolo experimental, **84 testes passaram em 1,99 s**, preservando os anteriores. Um quarto teste verifica a projeção de tempos; a suíte final tem **85 testes aprovados**. Não foi encontrada inconsistência nos algoritmos; nenhum arquivo de GRASP, N1, N2, VND, construção, objetivo ou comparação foi alterado nesta etapa.", "",
        "Foram alteradas somente a serialização compartilhada dos experimentos e as métricas do resumo, além de acrescentados scripts, testes e documentação. Os SHA-256 dos arquivos dos algoritmos e das instâncias constam em `manifesto.json`.", "",
        f"Ambiente: Python {manifesto['python']}; {manifesto['plataforma']}; processador `{manifesto['processador']}`; {manifesto['cpu_logicas']} CPUs lógicas. Execuções sequenciais, com um processo por par instância/seed, sem paralelizar medições.", "",
        "Parâmetros: 100 iterações GRASP, alpha=0,5, seeds de execução 0, 1 e 2. O VND usa exatamente a melhor solução final da mesma execução GRASP. O perfil, a seed de geração e o arquivo da instância são idênticos nas duas versões.", "",
        "Seleção: os dois perfis existentes (`simples` e `sequencia`) para N=11, 50, 100, 200. Isso amplia a representação do impacto da sequência sem gerar novas instâncias. Seeds de geração: 2020, 2022, 2024, 2026; salas: 3, 4, 5, 10, respectivamente. Seeds de geração e de execução têm papéis diferentes.", "",
        "## Comandos efetivamente executados", "",
        "```powershell", ".\\.venv\\Scripts\\python.exe -m pytest -q",
        ".\\.venv\\Scripts\\python.exe -u scripts/piloto_experimental.py --iteracoes 100 --seeds 0 1 2 --alpha 0.5 --limite-execucao 120 --limite-total 600 --saida resultados/piloto",
        ".\\.venv\\Scripts\\python.exe scripts/analisar_piloto.py", "```", "",
        "O diretório de saída deve estar vazio. Para repetir sem sobrescrever evidências, escolha outro com `--saida` e passe-o depois a `analisar_piloto.py --piloto`. Os limites incluem o processo da execução completa; timeout ou falha interrompem o lote, preservando JSONs individuais e CSVs concluídos. O comportamento de timeout foi testado com processo simulado, sem contaminar as medições reais.", "",
        f"Estado final: **{manifesto['status']}**, {manifesto['execucoes_concluidas']}/{manifesto['execucoes_planejadas']} execuções. Tempo de parede do piloto: **{f(manifesto['tempo_parede_total_s'])} s**; soma dos tempos internos GRASP+VND: **{f(manifesto['tempo_algoritmos_total_s'])} s**. A diferença inclui inicialização dos processos, leitura, serialização, validações externas e checkpoints. Nenhum timeout foi observado.", "",
        "## Resultados de qualidade medidos", "",
        "Makespan em blocos de 30 minutos. Cada linha agrega três seeds. DP é desvio padrão amostral (denominador n−1). Redução média é a média dos percentuais calculados dentro de cada par GRASP/VND.", "",
        "| N / salas / perfil | Melhor G | Média G | DP G | Melhor V | Média V | DP V | Redução média (%) | Melhoria (%) | Sem melhoria |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in resumos:
        linha = next(a for a in linhas if a["instancia"] == r["instancia"])
        perfil = carregar_instancia(linha["arquivo"]).metadados["perfil"]
        etiqueta = f"{linha['numero_cirurgias']} / {linha['numero_salas']} / {perfil}"
        r["etiqueta"] = etiqueta
        texto.append(f"| {etiqueta} | {r['melhor_grasp']} | {f(r['media_grasp'])} | {f(r['desvio_amostral_grasp'])} | {r['melhor_vnd']} | {f(r['media_vnd'])} | {f(r['desvio_amostral_vnd'])} | {f(r['media_reducao_percentual'])} | {f(r['percentual_execucoes_com_melhoria'], 1)} | {r['execucoes_sem_melhoria']} |")
    melhorias = sum(r["makespan_vnd"] < r["makespan_grasp"] for r in linhas)
    texto += ["", f"No total: **{melhorias}/{len(linhas)}** execuções com melhoria estrita ({f(100 * melhorias / len(linhas), 2)}%); **{len(linhas) - melhorias}** sem melhoria; nenhuma piora. Essas frequências descrevem este piloto, não uma estimativa robusta de superioridade do método.", "",
              "## Tempos e movimentos medidos", "",
              "Tempos em segundos; total = GRASP + adicional VND, sem executar novamente o GRASP. Média de realocações aceitas por execução:", "",
              "| N / salas / perfil | GRASP médio (s) | VND adicional médio (s) | Total médio (s) | Realocações médias | Realocações por seed (0, 1, 2) |",
              "| --- | ---: | ---: | ---: | ---: | --- |"]
    for r in resumos:
        grupo = sorted((a for a in linhas if a["instancia"] == r["instancia"]), key=lambda a: a["seed"])
        movimentos = ", ".join(str(a["realocacoes_aceitas"]) for a in grupo)
        texto.append(f"| {r['etiqueta']} | {f(r['media_tempo_grasp_s'], 6)} | {f(r['media_tempo_adicional_vnd_s'], 6)} | {f(r['media_tempo_total_s'], 6)} | {f(r['media_realocacoes'])} | {movimentos} |")
    texto += ["", "O arquivo `detalhado.csv` tem uma linha por execução, com makespans, tempos, realocações, contadores de avaliações, soluções e hash. `resumo.csv` contém os agregados. Os CSVs e JSONs não passam por arredondamento explícito; somente estas tabelas arredondam valores. Tempos são floats com a precisão disponível em Python.", "",
              "## Projeção do experimento principal — valores NÃO medidos", "",
              "Alvo: 1.000 iterações, 30 seeds e todas as 14 instâncias (420 pares GRASP/VND). O experimento principal **não foi executado**.", "",
              "Para as oito instâncias medidas, estima-se GRASP(1.000) = 10 × tempo médio GRASP(100). VND é pós-otimização única: sua projeção usa o tempo médio VND observado, sem multiplicá-lo por dez. A qualidade da melhor solução após 1.000 iterações pode alterar a trajetória do VND; portanto essa hipótese pode superestimar ou subestimar seu custo.", "",
              "Para N=21, 75 e 130 (seis instâncias não medidas neste piloto), interpola-se separadamente por perfil. Para considerar a quantidade de salas, usam-se os indicadores de carga `WG=N^2/M` e `WV=N^2*(M-1)*(N/M+1)`. Normalizam-se os tempos medidos por essas cargas; interpola-se a taxa linearmente em N entre os dois tamanhos medidos vizinhos e multiplica-se pela carga do alvo. WG aproxima os pares N1 de uma varredura em salas balanceadas (a menos de constantes e termos lineares); a taxa incorpora construção e varreduras adicionais. WV aproxima realocações de uma varredura multiplicadas pelo custo linear de copiar/validar. O número de varreduras é variável. São modelos empíricos de planejamento, não fórmulas exatas de complexidade temporal.", "",
              "```text", "T_principal = 30 * soma_instancias(10 * G100_estimado + V100_estimado)", "```", "",
              "| N / salas / perfil | Origem da base de tempo | GRASP por seed, 1.000 it. (s) | VND por seed (s) | 30 seeds, total projetado (min) |",
              "| --- | --- | ---: | ---: | ---: |"]
    for r in sorted(projecoes, key=lambda a: (a["numero_cirurgias"], a["perfil"])):
        base = "medida a 100 it." if r["base"] == "tempo_piloto_mesma_instancia" else "interpolada"
        texto.append(f"| {r['numero_cirurgias']} / {r['numero_salas']} / {r['perfil']} | {base} | {f(r['tempo_grasp_por_execucao_s'])} | {f(r['tempo_vnd_por_execucao_s'])} | {f(r['tempo_lote_total_s'] / 60, 2)} |")
    texto += ["", f"Projeção central: **{f(total / 60, 2)} minutos ({f(total / 3600, 2)} horas)**, sendo GRASP {f(total_g / 60, 2)} min e VND {f(total_v / 60, 2)} min. Não inclui instalação, testes ou análise posterior.", "",
              f"Sensibilidade aos tempos mínimo/máximo das três seeds, com o mesmo modelo: {f(projecao['faixa_seeds_min_s'] / 60, 2)}–{f(projecao['faixa_seeds_max_s'] / 60, 2)} min. Essa faixa **não é intervalo de confiança, limite garantido nem validação da interpolação**. Com VND dez vezes mais lento que a hipótese central, mantendo GRASP, a projeção seria {f(projecao['cenario_vnd_10x_s'] / 60, 2)} min. Para planejamento operacional, reservar duas vezes a projeção central corresponde a {f(2 * total / 60, 2)} min; o fator 2 é uma margem escolhida, não uma medição.", "",
              "## Configuração recomendada — não executada", "",
              f"Recomenda-se começar com as **oito instâncias do piloto, 1.000 iterações e 10 seeds (0..9)**: mantém quatro tamanhos e os dois perfis, com 80 pares. Projeção baseada diretamente nas oito instâncias medidas: **{f(reduzido / 60, 2)} min**, ou {f(2 * reduzido / 60, 2)} min com reserva de 2×. Esse desenho reduz o custo inicial e permite recalibrar o tempo do VND após 1.000 iterações, antes de expandir para 14 instâncias e 30 seeds.", "",
              "Comando preparado para execução futura; **não executado nesta etapa**:", "",
              "```powershell", ".\\.venv\\Scripts\\python.exe -u scripts/piloto_experimental.py --iteracoes 1000 --seeds 0 1 2 3 4 5 6 7 8 9 --alpha 0.5 --limite-execucao 300 --limite-total 7200 --saida resultados/principal_reduzido", "```", "",
              "O lote completo pode ser solicitado depois, passando os 14 arquivos em `--instancias` e as seeds 0..29. O script impõe limites de tempo e preserva execuções já concluídas; não deve haver execuções concorrentes de benchmark.", "",
              "## Limitações e evidências preservadas", "",
              "- Três seeds e uma instância por tamanho/perfil são insuficientes para inferência estatística forte; não foram feitos testes de significância ou alegações de ótimo global.",
              "- Médias e desvios descrevem variação de seed dentro de uma instância, não variabilidade entre hospitais ou múltiplas instâncias independentes da mesma classe.",
              "- Os seis casos intermediários do planejamento são projeções, com dependência de carga por sala e quantidade de varreduras. Melhorias e tempos do experimento principal não são resultados observados.",
              "- Aquecimento do sistema, carga externa e frequência do processador não foram controlados; não se fixou afinidade de CPU. A execução do piloto foi sequencial, sem testes concorrentes.",
              "- A N2 pode parar em platôs de makespan; ausência de melhoria não demonstra ótimo global. Não se alteraram aceitação estrita, desempates, vizinhanças ou alpha para favorecer resultados.",
              "- Não houve timeout real ou falha no piloto. Há teste automatizado para interrupção, preservação dos resultados e recusa de sobrescrita.", "",
              "Arquivos em `resultados/piloto/`: `detalhado.csv`, `resumo.csv`, `manifesto.json`, `execucoes/*.json` e `projecao_principal.{csv,json}`. O manifesto registra estado, horários UTC, ambiente, hashes e tempos de parede. Não contém dados hospitalares originais.", ""]
    documento.parent.mkdir(parents=True, exist_ok=True)
    documento.write_text("\n".join(texto), encoding="utf-8")
    return projecao


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piloto", type=Path, default=Path("resultados/piloto"))
    parser.add_argument("--suite", type=Path, default=Path("instancias/sinteticas"))
    parser.add_argument("--documento", type=Path, default=Path("docs/PILOTO_EXPERIMENTAL.md"))
    args = parser.parse_args()
    print(json.dumps(gerar_relatorio(args.piloto, args.suite, args.documento), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
