# Etapa 4.2 — Validação experimental preliminar

## Configuração e verificação inicial

Piloto de 25/10/2026 com dados **SINTÉTICOS**, sem relação estatística presumida com dados hospitalares do artigo.

A revisão do código confirmou:

- GRASP e VND minimizam o mesmo makespan de `avaliacao.py`; a avaliação incremental da N2 usa o mesmo máximo dos tempos de salas.
- `comparacao.py` passa uma cópia exata de `grasp.melhor_solucao` ao VND, executado uma única vez após o GRASP.
- N1 minimiza o tempo individual de cada sala, inclusive quando o makespan global não muda.
- N2 enumera toda origem, cirurgia, destino diferente e posição de inserção, incluindo extremos e salas vazias.
- `tempo_sala` inclui durações e preparações direcionais consecutivas; a construção inclui o preparo da última cirurgia; o delta N1 preserva a soma das durações e atualiza os arcos afetados.

Os **81 testes existentes passaram em 1,94 s** antes do piloto. Após acrescentar três testes do protocolo experimental, **84 testes passaram em 1,99 s**, preservando os anteriores. Um quarto teste verifica a projeção de tempos; a suíte final tem **85 testes aprovados**. Não foi encontrada inconsistência nos algoritmos; nenhum arquivo de GRASP, N1, N2, VND, construção, objetivo ou comparação foi alterado nesta etapa.

Foram alteradas somente a serialização compartilhada dos experimentos e as métricas do resumo, além de acrescentados scripts, testes e documentação. Os SHA-256 dos arquivos dos algoritmos e das instâncias constam em `manifesto.json`.

Ambiente: Python 3.12.6; Windows-11-10.0.26200-SP0; processador `Intel64 Family 6 Model 186 Stepping 2, GenuineIntel`; 12 CPUs lógicas. Execuções sequenciais, com um processo por par instância/seed, sem paralelizar medições.

Parâmetros: 100 iterações GRASP, alpha=0,5, seeds de execução 0, 1 e 2. O VND usa exatamente a melhor solução final da mesma execução GRASP. O perfil, a seed de geração e o arquivo da instância são idênticos nas duas versões.

Seleção: os dois perfis existentes (`simples` e `sequencia`) para N=11, 50, 100, 200. Isso amplia a representação do impacto da sequência sem gerar novas instâncias. Seeds de geração: 2020, 2022, 2024, 2026; salas: 3, 4, 5, 10, respectivamente. Seeds de geração e de execução têm papéis diferentes.

## Comandos efetivamente executados

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -u scripts/piloto_experimental.py --iteracoes 100 --seeds 0 1 2 --alpha 0.5 --limite-execucao 120 --limite-total 600 --saida resultados/piloto
.\.venv\Scripts\python.exe scripts/analisar_piloto.py
```

O diretório de saída deve estar vazio. Para repetir sem sobrescrever evidências, escolha outro com `--saida` e passe-o depois a `analisar_piloto.py --piloto`. Os limites incluem o processo da execução completa; timeout ou falha interrompem o lote, preservando JSONs individuais e CSVs concluídos. O comportamento de timeout foi testado com processo simulado, sem contaminar as medições reais.

Estado final: **concluido**, 24/24 execuções. Tempo de parede do piloto: **155,649 s**; soma dos tempos internos GRASP+VND: **142,928 s**. A diferença inclui inicialização dos processos, leitura, serialização, validações externas e checkpoints. Nenhum timeout foi observado.

## Resultados de qualidade medidos

Makespan em blocos de 30 minutos. Cada linha agrega três seeds. DP é desvio padrão amostral (denominador n−1). Redução média é a média dos percentuais calculados dentro de cada par GRASP/VND.

| N / salas / perfil | Melhor G | Média G | DP G | Melhor V | Média V | DP V | Redução média (%) | Melhoria (%) | Sem melhoria |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 / 3 / sequencia | 32 | 33,000 | 1,000 | 32 | 33,000 | 1,000 | 0,000 | 0,0 | 3 |
| 11 / 3 / simples | 21 | 21,333 | 0,577 | 21 | 21,333 | 0,577 | 0,000 | 0,0 | 3 |
| 50 / 4 / sequencia | 99 | 100,000 | 1,000 | 98 | 98,667 | 1,155 | 1,327 | 66,7 | 1 |
| 50 / 4 / simples | 56 | 56,667 | 0,577 | 56 | 56,667 | 0,577 | 0,000 | 0,0 | 3 |
| 100 / 5 / sequencia | 169 | 169,000 | 0,000 | 166 | 167,000 | 1,732 | 1,183 | 66,7 | 1 |
| 100 / 5 / simples | 100 | 100,000 | 0,000 | 99 | 99,333 | 0,577 | 0,667 | 66,7 | 1 |
| 200 / 10 / sequencia | 164 | 165,000 | 1,000 | 163 | 164,333 | 1,528 | 0,405 | 66,7 | 1 |
| 200 / 10 / simples | 100 | 100,000 | 0,000 | 99 | 99,333 | 0,577 | 0,667 | 66,7 | 1 |

No total: **10/24** execuções com melhoria estrita (41,67%); **14** sem melhoria; nenhuma piora. Essas frequências descrevem este piloto, não uma estimativa robusta de superioridade do método.

## Tempos e movimentos medidos

Tempos em segundos; total = GRASP + adicional VND, sem executar novamente o GRASP. Média de realocações aceitas por execução:

| N / salas / perfil | GRASP médio (s) | VND adicional médio (s) | Total médio (s) | Realocações médias | Realocações por seed (0, 1, 2) |
| --- | ---: | ---: | ---: | ---: | --- |
| 11 / 3 / sequencia | 0,026570 | 0,002924 | 0,029494 | 0,000 | 0, 0, 0 |
| 11 / 3 / simples | 0,025733 | 0,002626 | 0,028359 | 0,000 | 0, 0, 0 |
| 50 / 4 / sequencia | 0,835627 | 0,294093 | 1,129720 | 1,333 | 0, 3, 1 |
| 50 / 4 / simples | 0,683816 | 0,145083 | 0,828899 | 0,000 | 0, 0, 0 |
| 100 / 5 / sequencia | 4,138442 | 2,712446 | 6,850887 | 1,667 | 2, 3, 0 |
| 100 / 5 / simples | 3,063386 | 1,875345 | 4,938731 | 0,667 | 1, 1, 0 |
| 200 / 10 / sequencia | 5,812546 | 11,798225 | 17,610770 | 0,667 | 1, 1, 0 |
| 200 / 10 / simples | 4,523781 | 11,701937 | 16,225718 | 0,667 | 1, 0, 1 |

O arquivo `detalhado.csv` tem uma linha por execução, com makespans, tempos, realocações, contadores de avaliações, soluções e hash. `resumo.csv` contém os agregados. Os CSVs e JSONs não passam por arredondamento explícito; somente estas tabelas arredondam valores. Tempos são floats com a precisão disponível em Python.

## Projeção do experimento principal — valores NÃO medidos

Alvo: 1.000 iterações, 30 seeds e todas as 14 instâncias (420 pares GRASP/VND). O experimento principal **não foi executado**.

Para as oito instâncias medidas, estima-se GRASP(1.000) = 10 × tempo médio GRASP(100). VND é pós-otimização única: sua projeção usa o tempo médio VND observado, sem multiplicá-lo por dez. A qualidade da melhor solução após 1.000 iterações pode alterar a trajetória do VND; portanto essa hipótese pode superestimar ou subestimar seu custo.

Para N=21, 75 e 130 (seis instâncias não medidas neste piloto), interpola-se separadamente por perfil. Para considerar a quantidade de salas, usam-se os indicadores de carga `WG=N^2/M` e `WV=N^2*(M-1)*(N/M+1)`. Normalizam-se os tempos medidos por essas cargas; interpola-se a taxa linearmente em N entre os dois tamanhos medidos vizinhos e multiplica-se pela carga do alvo. WG aproxima os pares N1 de uma varredura em salas balanceadas (a menos de constantes e termos lineares); a taxa incorpora construção e varreduras adicionais. WV aproxima realocações de uma varredura multiplicadas pelo custo linear de copiar/validar. O número de varreduras é variável. São modelos empíricos de planejamento, não fórmulas exatas de complexidade temporal.

```text
T_principal = 30 * soma_instancias(10 * G100_estimado + V100_estimado)
```

| N / salas / perfil | Origem da base de tempo | GRASP por seed, 1.000 it. (s) | VND por seed (s) | 30 seeds, total projetado (min) |
| --- | --- | ---: | ---: | ---: |
| 11 / 3 / sequencia | medida a 100 it. | 0,266 | 0,003 | 0,13 |
| 11 / 3 / simples | medida a 100 it. | 0,257 | 0,003 | 0,13 |
| 21 / 2 / sequencia | interpolada | 1,836 | 0,014 | 0,92 |
| 21 / 2 / simples | interpolada | 1,665 | 0,011 | 0,84 |
| 50 / 4 / sequencia | medida a 100 it. | 8,356 | 0,294 | 4,33 |
| 50 / 4 / simples | medida a 100 it. | 6,838 | 0,145 | 3,49 |
| 75 / 5 / sequencia | interpolada | 19,160 | 1,104 | 10,13 |
| 75 / 5 / simples | interpolada | 14,770 | 0,660 | 7,71 |
| 100 / 5 / sequencia | medida a 100 it. | 41,384 | 2,712 | 22,05 |
| 100 / 5 / simples | medida a 100 it. | 30,634 | 1,875 | 16,25 |
| 130 / 6 / sequencia | interpolada | 53,077 | 5,226 | 29,15 |
| 130 / 6 / simples | interpolada | 39,756 | 3,883 | 21,82 |
| 200 / 10 / sequencia | medida a 100 it. | 58,125 | 11,798 | 34,96 |
| 200 / 10 / simples | medida a 100 it. | 45,238 | 11,702 | 28,47 |

Projeção central: **180,40 minutos (3,01 horas)**, sendo GRASP 160,68 min e VND 19,71 min. Não inclui instalação, testes ou análise posterior.

Sensibilidade aos tempos mínimo/máximo das três seeds, com o mesmo modelo: 164,19–194,59 min. Essa faixa **não é intervalo de confiança, limite garantido nem validação da interpolação**. Com VND dez vezes mais lento que a hipótese central, mantendo GRASP, a projeção seria 357,83 min. Para planejamento operacional, reservar duas vezes a projeção central corresponde a 360,79 min; o fator 2 é uma margem escolhida, não uma medição.

## Configuração recomendada — não executada

Recomenda-se começar com as **oito instâncias do piloto, 1.000 iterações e 10 seeds (0..9)**: mantém quatro tamanhos e os dois perfis, com 80 pares. Projeção baseada diretamente nas oito instâncias medidas: **36,61 min**, ou 73,21 min com reserva de 2×. Esse desenho reduz o custo inicial e permite recalibrar o tempo do VND após 1.000 iterações, antes de expandir para 14 instâncias e 30 seeds.

Comando preparado para execução futura; **não executado nesta etapa**:

```powershell
.\.venv\Scripts\python.exe -u scripts/piloto_experimental.py --iteracoes 1000 --seeds 0 1 2 3 4 5 6 7 8 9 --alpha 0.5 --limite-execucao 300 --limite-total 7200 --saida resultados/principal_reduzido
```

O lote completo pode ser solicitado depois, passando os 14 arquivos em `--instancias` e as seeds 0..29. O script impõe limites de tempo e preserva execuções já concluídas; não deve haver execuções concorrentes de benchmark.

## Limitações e evidências preservadas

- Três seeds e uma instância por tamanho/perfil são insuficientes para inferência estatística forte; não foram feitos testes de significância ou alegações de ótimo global.
- Médias e desvios descrevem variação de seed dentro de uma instância, não variabilidade entre hospitais ou múltiplas instâncias independentes da mesma classe.
- Os seis casos intermediários do planejamento são projeções, com dependência de carga por sala e quantidade de varreduras. Melhorias e tempos do experimento principal não são resultados observados.
- Aquecimento do sistema, carga externa e frequência do processador não foram controlados; não se fixou afinidade de CPU. A execução do piloto foi sequencial, sem testes concorrentes.
- A N2 pode parar em platôs de makespan; ausência de melhoria não demonstra ótimo global. Não se alteraram aceitação estrita, desempates, vizinhanças ou alpha para favorecer resultados.
- Não houve timeout real ou falha no piloto. Há teste automatizado para interrupção, preservação dos resultados e recusa de sobrescrita.

Arquivos em `resultados/piloto/`: `detalhado.csv`, `resumo.csv`, `manifesto.json`, `execucoes/*.json` e `projecao_principal.{csv,json}`. O manifesto registra estado, horários UTC, ambiente, hashes e tempos de parede. Não contém dados hospitalares originais.
