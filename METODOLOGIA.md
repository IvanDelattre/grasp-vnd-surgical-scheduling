# Metodologia

## 1. Fonte científica e limites da implementação

A referência é Soares et al. (2020), *Aplicação do GRASP ao Problema de
Agendamento de Cirurgias Eletivas*, LII SBPO.
[Artigo completo](https://proceedings.science/proceedings/100144/_papers/122642/download/abstract_file2?lang=pt-br).

Elementos diretamente identificados no artigo: minimizar makespan, preparo
dependente da sequência (§2); construção seguida de busca local em iterações
independentes (§3); LC/LRC, sorteio e fórmula `1 + alpha*(N-1)` (§3.1);
troca de posições ilustrada como 2-opt (§3.2); LC por menor processamento,
alpha 0,5, 1.000 iterações e 30 execuções (§5); blocos de meia hora (§4.1).

O texto não determina todos os detalhes necessários para uma reprodução
computacional. As regras abaixo completam a especificação conforme o pedido
do trabalho. Não alegamos equivalência ao programa Java original.

## 2. Decisões complementares e modelo

O modelo implementado é de **salas paralelas idênticas**, com preparação
direcional dependente da sequência. Embora o artigo use a denominação Job Shop,
esta implementação não inclui rotas com múltiplas operações por cirurgia.

Todas as salas iniciam disponíveis no instante zero; o preparo inicial é zero.
Cirurgias não são interrompidas e cada ID deve aparecer exatamente uma vez em
M listas ordenadas. Salas vazias são permitidas. Não incluímos restrições
adicionais sobre pacientes, equipes, prioridades ou capacidade diária, nem o
corte de quantidade de cirurgias por sala apresentado no modelo do artigo.
Tempos são contagens inteiras de blocos de 30 minutos: processamento positivo,
preparação não negativa. Para a sequência `q`:

```text
C(q) = soma p[q[i]] + soma s[q[i], q[i+1]]
C([]) = 0
Cmax = max C(q), entre todas as salas
```

A solução representa execução contínua em cada sala, sem folgas deliberadas;
assim, as sequências e os preparos determinam uma programação sem sobreposição.
O validador verifica o número de salas e a multiplicidade dos IDs. O modelo
valida separadamente todos os valores e dimensões dos dados.

São decisões explícitas deste projeto: interpretação de N como número de
candidatos restantes; floor na cardinalidade da LRC; desempates por ID ou índice;
alocação pelo menor término projetado; N1 best improvement por sala; enumeração
determinística e aceitação estrita da N2; geração sintética e perfis abaixo.

## 3. Construção GRASP

Ordena-se a LC por `(duração, identificador)` crescente. Em cada passo, com N
candidatos restantes, a LRC contém os primeiros
`min(N, max(1, floor(1 + alpha*(N-1))))` elementos. O sorteio é uniforme no
prefixo, usando um gerador `random.Random(seed)` próprio da execução.

A cirurgia sorteada é acrescentada à sala com menor tempo projetado após a
inserção, incluindo processamento e preparo em relação à última cirurgia.
Empates escolhem o menor índice de sala. A cirurgia é removida da LC e a LRC é
reconstruída com o novo N. Não se preenche uma sala inteira de cada vez.

Uma única sequência pseudoaleatória controlada pela seed alimenta as iterações;
cada iteração começa com todas as salas vazias e todas as cirurgias disponíveis,
sem herdar a solução anterior. Não se reinicializa a mesma seed a cada iteração.
Após a N1, guarda-se uma cópia da melhor solução. Empates de qualidade preservam
a primeira solução encontrada. Padrões: alpha 0,5 e 1.000 iterações.

## 4. N1: trocas dentro da sala

Para cada sala, enumeram-se pares `i < j` em ordem crescente. Uma troca permuta
somente essas duas posições: não reverte o segmento. Avalia-se o tempo da sala
para cada par e aplica-se a maior redução estrita. Empates mantêm o primeiro par.
Repete-se a varredura completa até nenhuma troca melhorar o tempo individual.

Esta otimização por sala é uma **decisão metodológica do trabalho**: uma sala
não crítica pode melhorar mesmo sem reduzir imediatamente o makespan global.
O processamento total da sala não muda na troca. O cálculo usa a diferença exata
dos arcos de preparação incidentes às posições; um conjunto de índices evita
contagem dupla quando as posições são adjacentes. Os testes comparam essa
avaliação incremental ao recálculo completo em matrizes assimétricas.

## 5. Pós-otimização VND adaptada

O VND recebe uma cópia exata da melhor solução final do GRASP. Não executa o
GRASP novamente e inicia diretamente na N2, pois cada sala já está em ótimo
local por N1.

A N2 enumera, em ordem crescente, sala de origem, posição da cirurgia, sala de
destino diferente e posição de inserção entre zero e o comprimento do destino.
Inclui início, meio, fim e destino vazio. Cada candidato é construído, validado
e avaliado. Recalculam-se apenas as duas salas modificadas; reutilizam-se os
tempos das demais e seu máximo por par de salas. Todas as origens e destinos
são considerados, sem restrição à sala crítica e sem sorteios.

Depois da varredura inteira, aceita-se a realocação de maior redução **estrita
do makespan bruto da N2**. Não se aplica N1 a cada candidato para decidir a N2.
Em empate, aceita-se o primeiro movimento enumerado. Aplica-se N1 somente nas
salas de origem e destino do movimento aceito, e reinicia-se a N2 completa.
Sem realocação estritamente melhor, encerra-se.

Trata-se de uma adaptação da estratégia tradicional de VND, com N1 como
reotimização das salas afetadas após cada passo N2. Não existem vizinhanças
extras, trocas diretas entre salas nem movimentos de platô.

## 6. Por que reotimizar somente duas salas

Antes da primeira N2, todas as salas são ótimos locais por N1. Uma realocação
modifica apenas as sequências de origem e destino. Como duração e matriz de
preparação são fixas, as outras salas mantêm o mesmo tempo e a mesma vizinhança
de trocas: continuam localmente ótimas. Reotimizar as duas afetadas restabelece
esse invariante para a próxima N2.

Cada realocação aceita reduz o makespan; a N1 subsequente não aumenta nenhum
tempo individual. Logo o makespan não pode piorar. Tempos inteiros não negativos
e melhoria estrita também garantem término. O código verifica essa propriedade
com exceções explícitas, independentes da opção de otimização `python -O`.
Há testes de não piora, validade, preservação das entradas e término local.

`executar_vnd` aceita qualquer solução válida, mas a garantia de ótimo local
N1 em **todas** as salas pressupõe a entrada já otimizada pelo GRASP. Não faz
uma N1 inicial oculta para compensar entradas arbitrárias.

## 7. Dados e procedência

A consulta ao [repositório oficial](https://github.com/elisandrade21/POACE-Instancias)
em **25/10/2026** mostrou apenas `README.md` na branch `master`, sem os arquivos
de processamento/preparação. Por isso, nenhum dado original foi importado.
O README e o artigo divergem na quantidade de salas da instância de 130
cirurgias; não tentamos reconstruir essa instância a partir da descrição.
Detalhes da verificação estão em [docs/FONTES.md](docs/FONTES.md).

Todos os JSONs incluídos são **SINTÉTICOS**, inclusive o exemplo manual.
O gerador não estima distribuições hospitalares. São escolhas deste projeto:

| Perfil | Duração (blocos) | Preparação (blocos) |
| --- | --- | --- |
| simples | uniforme discreta 1..8 | uniforme discreta 0..1 |
| sequencia | uniforme discreta 1..12 | uniforme discreta 0..10 |

Sorteios são independentes, com uma matriz direcionada e diagonal zero.
Não se força assimetria em todo par; ela pode ocorrer naturalmente. A suíte
usa N/salas = 11/3, 21/2, 50/4, 75/5, 100/5, 130/6 e 200/10. Para o k-ésimo
tamanho, k começando em zero, usa-se `seed_base + k`, com `seed_base=2020`.
Os dois perfis reutilizam a seed correspondente ao tamanho; isso não implica
que compartilhem exatamente os mesmos sorteios após os diferentes intervalos.
Metadados registram seed, perfil, intervalos e identificação SINTÉTICA.

## 8. Comparação, reprodução e métricas

Para cada par instância/seed, executa-se uma vez o GRASP e em seguida o VND
sobre uma cópia da sua melhor solução. A melhoria percentual é:

```text
100 * (makespan_grasp - makespan_vnd) / makespan_grasp
```

O denominador é positivo porque há pelo menos uma cirurgia de duração positiva.
O tempo do GRASP e o adicional do VND são medidos com `perf_counter`; o total
é sua soma, incluindo cópias e validações internas, excluindo leitura JSON,
serialização CSV, cálculo do hash e verificações externas da comparação.

As avaliações N1 contam cada par de posições avaliado, incluindo a última
varredura sem melhoria. As avaliações N2 contam cada realocação candidata,
inclusive da última varredura. Construção, validação e reavaliações de controle
não são contadas como avaliações de vizinhança. Os contadores N1 do GRASP e
do VND são separados. O histórico guarda o makespan inicial e o valor após
cada N2 aceita com sua N1 subsequente.

O CSV detalhado registra parâmetros, qualidade, tempos, realocações, avaliações,
soluções, versão Python, plataforma, instante UTC e SHA-256 do JSON canônico
normalizado da instância. O hash identifica o conteúdo interpretado, não os
bytes/indentação do arquivo. O resumo agrupa instância, hash, iterações e alpha,
com melhor valor, média, desvio amostral e tempos médios. Para um grupo com
somente uma execução, o campo de desvio é preenchido com zero por convenção.
A melhoria média é a
média das reduções percentuais de cada execução pareada.

Instalação, testes e comandos estão no [README](README.md). O script
`scripts/validacao_rapida.py` roda somente as quatro instâncias pequenas,
20 iterações e seeds 0, 1, 2. O lote de 1.000 iterações/30 seeds está pronto
pela CLI, mas não roda automaticamente. A geração de instâncias grandes em
testes verifica somente dados, sem executar o experimento pesado.

## 9. Interpretação e limitações

Os resultados rápidos servem para validar o software, sem demonstrar
superioridade estatística do método. Não há garantia de ótimo global ou
equivalência aos resultados publicados. A N2 sem movimentos neutros pode parar
em platôs, especialmente com várias salas críticas empatadas. O custo de
validação de cada candidato é linear no número de cirurgias; privilegia-se a
correção e transparência nesta versão. Experimentação completa e comparação
com instâncias originais dependem de execução posterior e acesso aos dados.
