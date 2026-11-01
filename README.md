# GRASP e GRASP + VND para agendamento de cirurgias eletivas

Projeto acadêmico em Python que compara um GRASP de referência, baseado em
Soares et al. (2020), com sua pós-otimização VND. O objetivo é minimizar o
makespan em salas idênticas, considerando preparação dependente da sequência
e possivelmente assimétrica. Cada unidade de tempo representa **30 minutos**.

**Todas as instâncias incluídas são SINTÉTICAS.** Este projeto não reproduz
exatamente o software Java nem os resultados hospitalares do artigo.
Consulte [METODOLOGIA.md](METODOLOGIA.md) para as escolhas e fontes e
[docs/VALIDACAO.md](docs/VALIDACAO.md) para os resultados efetivamente executados.

## Instalação

Python 3.10 ou superior. Na raiz do projeto, em PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -e .
.\.venv\Scripts\python.exe -m pytest -q
```

O algoritmo usa somente a biblioteca padrão. `pytest` é dependência de testes.
No Linux/macOS, substitua `.\.venv\Scripts\python.exe` por `.venv/bin/python`.
O módulo também funciona sem instalar o pacote se executado na raiz.

O piloto da etapa 4.2 está documentado em
[docs/PILOTO_EXPERIMENTAL.md](docs/PILOTO_EXPERIMENTAL.md): 100 iterações, três
seeds e os dois perfis para 11, 50, 100 e 200 cirurgias. Os dados medidos e as
projeções, identificadas separadamente, estão em `resultados/piloto/`.

```powershell
# Use uma saída nova para preservar os resultados anteriores.
.\.venv\Scripts\python.exe scripts/piloto_experimental.py --saida resultados/piloto_repeticao
.\.venv\Scripts\python.exe scripts/analisar_piloto.py --piloto resultados/piloto_repeticao --documento docs/PILOTO_REPETICAO.md
```

O piloto salva cada execução, possui limites de tempo e recusa sobrescrever
saídas existentes. O script de análise só lê resultados e calcula projeções;
não inicia o experimento principal.

O experimento principal reduzido usa as mesmas oito instâncias, 1.000 iterações
e seeds 0..9. Sua análise está em
[docs/RESULTADOS_PRINCIPAIS.md](docs/RESULTADOS_PRINCIPAIS.md), com tabelas,
gráficos científicos em PNG de 600 dpi e discussão do custo adicional do VND.
Os dados e JSONs individuais ficam em `resultados/principal_reduzido/`.
Para refazer somente a análise dos resultados já concluídos:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-analise.txt
.\.venv\Scripts\python.exe scripts/analisar_principal.py
```

Essa análise confere parâmetros, objetivos, soluções e hashes antes de gerar
novos arquivos derivados. Os CSVs brutos e os resultados do piloto são preservados.

## Executar uma comparação

```powershell
.\.venv\Scripts\python.exe -m grasp_vnd comparar instancias/exemplo_manual.json --seed 0 --iteracoes 20
.\.venv\Scripts\python.exe -m grasp_vnd comparar instancias/sinteticas/SINTETICA-11-S3-sequencia-seed2020.json --seed 0 --iteracoes 20 --saida resultados/exemplo.json
```

A saída JSON inclui as duas soluções, makespans, tempos em segundos,
contadores de movimentos/avaliações, histórico do VND e redução percentual.
`comparar` usa **1.000 iterações por padrão** e `alpha=0.5`. Use `--iteracoes`
para reduzir o esforço. A entrada GRASP não é modificada pelo VND.
Após a instalação, também está disponível `.\.venv\Scripts\grasp-vnd.exe`.

Exemplo pela API:

```python
from grasp_vnd import carregar_instancia, executar_grasp, executar_vnd

instancia = carregar_instancia("instancias/exemplo_manual.json")
resultado_grasp = executar_grasp(instancia, seed=0, iteracoes=20)
resultado_vnd = executar_vnd(instancia, resultado_grasp.melhor_solucao)
print(resultado_grasp.makespan, resultado_vnd.makespan)
```

No exemplo manual, a solução específica `[["A", "B"], ["C"]]` tem makespan 7;
o VND move B para a segunda sala e obtém 5. O GRASP pode já encontrar 5,
portanto a comparação completa não precisa melhorar esse caso.

## Instâncias e experimentos

```powershell
# Gera arquivos; não executa os algoritmos.
.\.venv\Scripts\python.exe -m grasp_vnd gerar-suite

# Uma instância sintética personalizada.
.\.venv\Scripts\python.exe -m grasp_vnd gerar --cirurgias 21 --salas 2 --seed 42 --perfil sequencia --saida instancias/personalizada.json

# Validação pequena: 4 instâncias, 20 iterações, seeds 0, 1 e 2.
.\.venv\Scripts\python.exe scripts/validacao_rapida.py

# Lote personalizado: JSONs individuais ou diretórios.
.\.venv\Scripts\python.exe -m grasp_vnd experimentar instancias/exemplo_manual.json --iteracoes 20 --seeds 0 1 2 --saida resultados/manual

# Experimento completo, apenas quando solicitado pelo pesquisador.
.\.venv\Scripts\python.exe -m grasp_vnd experimentar instancias/sinteticas --iteracoes 1000 --execucoes 30 --seed-inicial 0 --saida resultados/completo
```

`experimentar` tem padrões rápidos: 20 iterações e 3 execuções. `--seeds`
substitui `--execucoes` e `--seed-inicial`. Os CSVs `detalhado.csv` e
`resumo.csv` contêm resultados pareados e agregados; soluções são células JSON
no CSV detalhado. Tempos variam entre execuções; qualidade e decisões são
reprodutíveis para a mesma instância, semente e parâmetros.

Os 14 cenários combinam N = 11, 21, 50, 75, 100, 130 e 200 com dois perfis.
As salas escolhidas são 3, 2, 4, 5, 5, 6 e 10, respectivamente. O perfil
`simples` usa durações 1..8 e preparo 0..1; `sequencia` usa durações 1..12 e
preparo 0..10. Todos esses intervalos são escolhas do projeto.

## Formato JSON

```json
{
  "identificador": "SINTETICA-EXEMPLO",
  "numero_salas": 2,
  "unidade_minutos": 30,
  "origem": "SINTETICA",
  "cirurgias": [{"id": "A", "duracao": 4}, {"id": "B", "duracao": 3}],
  "preparacao": [[0, 2], [1, 0]],
  "metadados": {"descricao": "Exemplo didático"}
}
```

A ordem de `cirurgias` define linhas e colunas de `preparacao`:
`preparacao[i][j]` é o preparo de i para j. A matriz deve ser quadrada e
completa. IDs são textos únicos e não vazios; durações são inteiros positivos;
preparações são inteiros não negativos. A diagonal é validada, mas não é usada
em soluções válidas. Salas vazias são permitidas; não há preparo inicial.
Instâncias sem cirurgias são rejeitadas. Metadados e origem não informados
recebem padrões neutros, sem presumir que sejam dados hospitalares.

## Arquivos

```text
grasp_vnd/
  __init__.py, __main__.py, cli.py
  problema.py, avaliacao.py
  construcao.py, busca_local.py, grasp.py, vnd.py
  comparacao.py, gerador.py, experimentos.py
instancias/
  exemplo_manual.json
  sinteticas/                  # 14 JSONs SINTÉTICOS
scripts/validacao_rapida.py
tests/
  conftest.py
  test_problema_avaliacao.py
  test_construcao_grasp.py
  test_busca_local.py
  test_vnd_comparacao.py
  test_gerador_experimentos_cli.py
docs/
  FONTES.md
  VALIDACAO.md
resultados/
  exemplo.json
  validacao/detalhado.csv
  validacao/resumo.csv
METODOLOGIA.md
README.md
requirements.txt
pyproject.toml
.gitignore
```

## Limitações

Heurísticas não garantem ótimo global. A N2 é exaustiva e pode custar mais em
instâncias grandes. Movimentos sem redução imediata do makespan são rejeitados,
mesmo que pudessem abrir caminho para uma melhoria posterior. Empates entre
salas críticas podem impedir realocações isoladas de melhoria estrita.
O lote completo não foi iniciado nesta entrega. As restrições são as do modelo
acadêmico solicitado, sem disponibilidade de equipes ou outras regras clínicas.
