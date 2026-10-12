# SGCP — Coloração Seletiva de Grafos

Heurística construtiva para o **Problema de Coloração Seletiva de Grafos**
(*Selective Graph Coloring Problem*, SGCP), com gerador de instâncias,
validador formal de soluções, experimentos e artigo científico.

Trabalho da disciplina de Projeto e Análise de Algoritmos (PAA) — BCC, 2026.2.

---

## Etapas atual

| Fase | Conteúdo | Situação |
|------|----------|----------|
| 1 | Modelo de dados, leitura/escrita de instâncias, validador, testes | concluída |
| 2 | Gerador de instâncias (Şeker et al., 2021), banco `small`/`medium`/`large` e instâncias da literatura | concluída |
| 3 | Baseline, heurística construtiva e solver exato (ILP) | pendente |
| 4 | CLI e experimentos em lote | pendente |
| 5 | Artigo | pendente |

---

## Requisitos e instalação

- Python **3.10 ou superior** (desenvolvido com 3.14)
- `make` (opcional, mas simplifica os comandos)

Com `make`:

```bash
make venv            # cria .venv.nosync/ e instala requirements.txt
make test            # roda a suíte de testes
make instances       # (re)gera as 600 instâncias de grafos perfeitos (~10 s)
make literature      # baixa e converte random, nsfnet e ring (~20 s)
make literature-big  # baixa e converte big-random (n = 1000, ~200 MB)
make clean           # remove __pycache__ e caches do pytest
```

Sem `make`:

```bash
python3 -m venv .venv.nosync
.venv.nosync/bin/python -m pip install -r requirements.txt
.venv.nosync/bin/python -m pytest -q
```

> O ambiente virtual fica em `.venv.nosync/` porque o projeto local está no iCloud
> Drive: o sufixo `.nosync` impede que o iCloud tente sincronizar a pasta.

Dependências (`requirements.txt`): `networkx`, `numpy`, `pandas`,
`matplotlib`, `tabulate`, `pulp` e `pytest`.

---

## Estrutura do repositório

```text
├── src/
│   ├── model.py           # Instance (grafo + partição) e Solution
│   ├── instance_io.py     # Leitura/escrita de instâncias (.txt e .json)
│   ├── validator.py       # Validador formal de soluções
│   ├── generator.py       # Gerador PerfectGen (Şeker et al., 2021) e suíte
│   ├── literature.py      # Importador das instâncias da literatura
│   └── algorithms/        # (fase 3) heurística, baselines, solver exato
├── data/perfect_graphs/   # Grafos perfeitos de McKay (sementes do gerador)
├── tests/                 # Testes com pytest
├── instances/
│   ├── examples/toy.txt   # Instância de exemplo feita à mão (ótimo = 2)
│   ├── small/             # 60 instâncias geradas (n = 50)
│   ├── medium/            # 240 instâncias geradas (n = 100–250)
│   ├── large/             # 300 instâncias geradas (n = 300–500), fora do git
│   ├── manifest.csv       # As 600 instâncias geradas: parâmetros, sementes, sha256
│   └── literature/        # Benchmark da literatura (random, nsfnet, ring, big-random)
├── results/               # logs/, tables/, plots/ das execuções
├── report/                # Artigo científico (LaTeX)
├── instrucoes.md          # Enunciado do trabalho
├── requirements.txt
├── pyproject.toml         # Configuração do pytest
└── Makefile
```

---

## Formato das instâncias

São aceitos dois formatos, escolhidos pela extensão do arquivo. Nos arquivos,
**vértices e clusters são numerados a partir de 1**.

### Texto (`.txt`, formato `sgcp_dimacs`)

```text
# format: sgcp_dimacs
# name: toy
# optimum: 2
p edge <n> <m> <k>        # nº de vértices, arestas e clusters
c <id> <v1> <v2> ...      # um cluster por linha
e <u> <v>                 # uma aresta por linha
```

- O bloco de linhas `# chave: valor` no topo do arquivo vira metadado da
  instância (`name` dá o nome; os demais valores são lidos como JSON quando
  possível, então `2` vira inteiro). Os comentários que vêm depois são livres.
- **Atenção:** ao contrário do DIMACS clássico, a linha `c` declara um
  **cluster**, não um comentário.

Exemplo completo: [instances/examples/toy.txt](instances/examples/toy.txt).

### JSON (`.json`, formato `sgcp_json`)

```json
{
  "format": "sgcp_json",
  "name": "toy",
  "n": 8, "m": 12, "k": 4,
  "meta": {"optimum": 2},
  "clusters": [[1, 2], [3, 4], [5, 6], [7, 8]],
  "edges": [[1, 3], [1, 5], [1, 7], ...]
}
```

A leitura é estrita nos dois formatos. Partição incompleta ou sobreposta,
vértice fora do intervalo, laço, aresta repetida ou contagem `m`/`k`
divergente do cabeçalho geram `InstanceFormatError`, com a linha ou o campo
do problema.

---

## Banco de instâncias

| Família | Faixa | Instâncias | n | k | No git |
|---|---|---:|---|---|---|
| Grafos perfeitos (PerfectGen) | `small/` | 60 | 50 | 7–17 | sim |
| | `medium/` | 240 | 100–250 | 13–76 | sim |
| | `large/` | 300 | 300–500 | 39–150 | não: `make instances` |
| Literatura | `literature/random/` | 80 | 20–120 | 10–60 | sim |
| | `literature/nsfnet/` | 50 | 16–257 | 12–182 | sim |
| | `literature/ring/` | 150 | 8–760 | 4–380 | sim |
| | `literature/big-random/` | 90 | 1000 | 500 | não: `make literature-big` |

As faixas `small`/`medium`/`large` são definidas por n. A `small` é a usada
para comparação com o solver exato.

### Gerador de grafos perfeitos (`src/generator.py`)

Reproduz o gerador de Şeker, Ekim & Taşkın (2021, §5), já que as instâncias publicadas pelos autores saíram do ar.

Mudei uma coisa em relação ao artigo. Do jeito descrito por Şeker et al., cada passo sorteia uma operação ao acaso. Assim, a densidade 0,1 dá 0% de aceitação com n ≥ 200, e com n = 500 até 0,3 e 0,7 ficam em 2%. Por isso, o gerador agora sorteia 3 candidatos por passo e fica com o de densidade mais próxima do alvo, o que leva a aceitação para 31–100%. Todas as operações continuam preservando a perfeição; o modo original continua disponível com --steer 1.

- **Grafo — *Algorithm PerfectGen*.** Começa de um grafo perfeito pequeno e
  conexo, sorteado da coleção de McKay (até 9 vértices; ver
  [`data/perfect_graphs/`](data/perfect_graphs/README.md)). Depois aplica
  operações que preservam perfeição até chegar a exatamente n vértices:
  identificação de cliques, substituição (*replication lemma*), composição,
  união disjunta, junção e complemento. As operações com um segundo grafo
  sorteiam G' com |V'| ≤ n − |V|. O grafo é aceito se a densidade d está a
  menos de ε = 0,025 da desejada δ; se 1 − d está, aceita-se o complemento;
  senão, recomeça.
- **Partição.** Permutação aleatória dos vértices cortada em blocos de tamanho
  sorteado uniformemente em [lo, hi]. O último bloco fica com o que sobrar e
  pode ter menos de lo vértices, como no artigo.
- **Desvio documentado: direcionamento (`--steer`, padrão 3).** Com a escolha
  uniforme do artigo (`--steer 1`), algumas densidades praticamente nunca são
  atingidas. A cada passo, o gerador agora sorteia `steer` candidatos
  independentes e fica com o de densidade mais próxima do alvo (δ ou 1 − δ).
  Toda operação continua preservando perfeição; muda só a distribuição dos
  grafos. Taxa de aceitação por tentativa, medida no código final:

  | n | steer | δ = 0,1 | δ = 0,3 | δ = 0,5 | δ = 0,7 |
  |---:|---:|---:|---:|---:|---:|
  | 50 | 1 (artigo) | 4% | 12% | 9% | 11% |
  | 50 | 3 | 44% | 31% | 64% | 32% |
  | 200 | 1 (artigo) | 0% | 12% | 12% | 10% |
  | 200 | 3 | 43% | 64% | 88% | 72% |
  | 500 | 1 (artigo) | 0% | 2% | 26% | 2% |
  | 500 | 3 | 52% | 85% | 100% | 82% |

- **Grade (a do artigo).** n ∈ {50, 100, …, 500} × δ ∈ {0,1; 0,3; 0,5; 0,7} ×
  5 réplicas = 200 grafos. Cada grafo é combinado com três partições, com
  clusters de 2–5, 4–7 e 6–9 vértices: 600 instâncias. Os nomes seguem
  `pg_n<n>_d<δ>_c<lo>-<hi>_s<réplica>.txt`.
- **Reprodutibilidade.** As sementes derivam de `sha256(master:n:δ:réplica[:faixa])`,
  com master = 2021. Cada arquivo registra nos metadados `graph_seed`,
  `partition_seed`, `steer`, `attempts`, `complemented` e a contagem de cada
  operação, o que basta para regenerá-lo (`generator.regenerate`).
  `make instances` recria os arquivos byte a byte, e o sha256 de cada um está em
  `instances/manifest.csv`.

Uma instância avulsa:

```bash
python -m src.generator single --n 100 --density 0.3 --clusters 2 5 \
    --seed 42 --output instances/exemplo.txt
```

### Instâncias da literatura (`src/literature.py`)

São os conjuntos `random`, `nsfnet` e `ring`, usados por Frota et al. (2010),
Hoshino et al. (2011) e Furini, Malaguti & Santini (2018), mais o `big-random`.
São baixados do repositório de Santini (GPL-3.0), fixado em um commit, e
convertidos estritamente para o formato do projeto. Fontes, licença e
observações (incluindo as 12 instâncias `ring` duplicadas) estão em
[`instances/literature/README.md`](instances/literature/README.md).

---

## Validação de soluções

Toda solução produzida por qualquer algoritmo deve passar por
`validate(inst, sol)` ou `ensure_valid(inst, sol)`. Este último levanta
`InvalidSolutionError` se a solução for inválida. O validador recalcula tudo a
partir da instância e verifica:

1. **Representatividade estrita:** exatamente um vértice por cluster, e
   `selection[i]` pertence a $V_i$;
2. **Cores bem formadas:** uma cor inteira positiva por representante;
3. **Coloração própria:** nenhuma aresta de $G[S]$ tem as duas pontas com a
   mesma cor (os conflitos encontrados são listados no relatório);
4. **Custo:** o número de cores distintas tem que bater com o valor que o
   algoritmo declarou, quando ele declara um. Cores não contíguas (ex.:
   `{1, 3}`) geram apenas aviso.

---

## Testes

```bash
make test
```

A suíte cobre o modelo de dados, a leitura e escrita nos dois formatos (com
ida e volta e casos de erro) e o validador. Na instância `toy`, o ótimo 2 é
confirmado por força bruta. Para o gerador, ela confere o decodificador graph6
contra o networkx, a perfeição (`networkx.is_perfect_graph`) da saída de cada
operação e de grafos gerados, as densidades, a partição, o determinismo e a
regeneração byte a byte de instâncias versionadas. Para o importador, confere
o parser estrito do formato de Santini.

---

## Referências

1. Demange, M., Ekim, T., Ries, B., & Tanasescu, C. (2015). *On some
   applications of the selective graph coloring problem*. European Journal of
   Operational Research, 240(2), 307–314.
2. Şeker, O., Ekim, T., & Taşkın, Z. C. (2021). *An exact cutting plane
   algorithm to solve the selective graph coloring problem in perfect graphs*.
   European Journal of Operational Research, 291(1), 67–83.
3. Demange, M., Ekim, T., & de Werra, D. (2009). *A tutorial on the use of
   graph coloring for some problems in robotics*. European Journal of
   Operational Research, 192(1), 41–55.
4. Furini, F., Malaguti, E., & Santini, A. (2018). *An exact algorithm for the
   Partition Coloring Problem*. Computers & Operations Research, 92, 170–181.
5. Frota, Y., Maculan, N., Noronha, T. F., & Ribeiro, C. C. (2010). *A
   branch-and-cut algorithm for partition coloring*. Networks, 55(3), 194–204.
6. Li, G., & Simha, R. (2000). *The partition coloring problem and its
   application to wavelength routing and assignment*. Proc. First Workshop on
   Optical Networks.
7. McKay, B. *Combinatorial Data — Perfect graphs*.
   <https://users.cecs.anu.edu.au/~bdm/data/graphs.html>
