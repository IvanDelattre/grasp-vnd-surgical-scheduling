# Resultados da validação executada

Execução em **25/10/2026**, Windows, Python **3.12.6**, pytest **9.1.1**.
Todos os dados utilizados são **SINTÉTICOS**. Os valores abaixo foram produzidos
pelo programa, sem extrapolação para as instâncias hospitalares do artigo.

## Testes

Comando executado:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado: **81 passed in 2.33s**.

A suíte verifica entrada JSON, multiplicidade de IDs, cálculo manual, preparo
direcional, delta exato da N1, best improvement, término local, todas as salas
e posições de inserção da N2, não piora do VND, preservação das entradas,
reprodutibilidade, LRC nos extremos, salas vazias, casos unitários, CLI,
geração sintética e CSVs. O teste especificado de `[[A, B], [C]]`, com durações
4, 3, 2 e preparação zero, confirmou makespan **7 → 5** movendo B.

Também foram verificados o comando instalado `grasp-vnd --help` e
`git diff --check` (sem erro de whitespace).

## Experimento rápido

Comando executado após gerar a suíte:

```powershell
.\.venv\Scripts\python.exe scripts/validacao_rapida.py
```

Foram feitas **12 comparações pareadas**: quatro instâncias pequenas, seeds
0, 1, 2, alpha 0,5 e 20 iterações GRASP por execução. A seed de geração de cada
instância, indicada no nome do JSON, é diferente da seed de execução do GRASP.

| Instância SINTÉTICA | Melhor GRASP | Média GRASP | Melhor após VND | Média após VND | Redução percentual média |
| --- | ---: | ---: | ---: | ---: | ---: |
| 11 cirurgias, 3 salas, sequencia, seed de geração 2020 | 32 | 34,3333 | 32 | 33,6667 | 1,9048% |
| 11 cirurgias, 3 salas, simples, seed de geração 2020 | 21 | 21,6667 | 21 | 21,6667 | 0,0000% |
| 21 cirurgias, 2 salas, sequencia, seed de geração 2021 | 72 | 73,6667 | 71 | 71,3333 | 3,1062% |
| 21 cirurgias, 2 salas, simples, seed de geração 2021 | 45 | 45,3333 | 45 | 45,3333 | 0,0000% |

Makespans em blocos de 30 minutos; a redução média é calculada por par de
execuções, não pela razão entre as médias.

| Instância/perfil | Tempo médio GRASP (s) | Tempo médio adicional VND (s) |
| --- | ---: | ---: |
| 11 / sequencia | 0,007525 | 0,003692 |
| 11 / simples | 0,005414 | 0,003180 |
| 21 / sequencia | 0,054857 | 0,027056 |
| 21 / simples | 0,049228 | 0,013732 |

Dados completos, incluindo soluções, ambiente e parâmetros:
[detalhado.csv](../resultados/validacao/detalhado.csv) e
[resumo.csv](../resultados/validacao/resumo.csv).
Tempos dependem do ambiente e da carga da máquina; são medições de validação,
sem rigor de benchmark. Parte das verificações foi executada em paralelo.

## Exemplo individual efetivamente executado

```powershell
.\.venv\Scripts\python.exe -m grasp_vnd comparar instancias/sinteticas/SINTETICA-11-S3-sequencia-seed2020.json --seed 0 --iteracoes 20 --saida resultados/exemplo.json
```

O resultado completo está em [exemplo.json](../resultados/exemplo.json).

| Métrica | Valor observado |
| --- | ---: |
| Makespan GRASP | 35 blocos (1.050 minutos) |
| Makespan após VND | 33 blocos (990 minutos) |
| Redução | 5,7142857% |
| Tempo GRASP | 0,0066531 s |
| Tempo adicional VND | 0,0057556 s |
| Tempo total | 0,0124087 s |
| Realocações aceitas | 1 |
| Avaliações N1 no GRASP | 559 |
| Avaliações N2 no VND | 204 |
| Avaliações N1 no VND | 9 |

Histórico de makespan do VND: `[35, 33]`. A cirurgia C0003 foi realocada da
terceira para a segunda sala. A primeira sala manteve sua sequência.

## Escopo não executado

Foram gerados os 14 JSONs, incluindo N=50, 75, 100, 130 e 200, mas os algoritmos
foram experimentados somente nas instâncias pequenas acima. O lote de 1.000
iterações e 30 execuções não foi iniciado. Os resultados rápidos não sustentam
conclusão de superioridade estatística nem reprodução de resultados originais.
