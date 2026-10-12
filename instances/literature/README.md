# Instâncias da literatura

Benchmark clássico do SGCP, também conhecido como *Partition Coloring Problem*
(PCP). Os arquivos vêm do repositório de A. Santini,
[`alberto-santini/selective-graph-colouring`](https://github.com/alberto-santini/selective-graph-colouring),
fixado no commit `731f99db29d5d20de9dc83ffada9f418b93100cf`. É o repositório
que acompanha Furini, Malaguti & Santini (2018), e o conjunto completo também
foi distribuído pelo grupo de C. C. Ribeiro
(<http://www2.ic.uff.br/~celso/grupo/pcp.htm>).

Os arquivos foram convertidos para o formato `sgcp_dimacs` do projeto, com
vértices e clusters numerados a partir de 1, por `python -m src.literature`
(`make literature`). Cada arquivo guarda nos metadados o conjunto, o arquivo de
origem, o repositório e o commit.

| Conjunto | Instâncias | n | k | Densidade | Origem | No git |
|---|---:|---|---|---|---|---|
| `random/` | 80 | 20–120 | 10–60 | 0,10–0,91 | Frota et al. (2010), grafos aleatórios | sim |
| `nsfnet/` | 50 | 16–257 | 12–182 | 0,09–0,13 | Li & Simha (2000), rede NSF (RWA) | sim |
| `ring/` | 150 | 8–760 | 4–380 | 0,36–0,41 | Frota et al. (2010), redes em anel (RWA) | sim |
| `big-random/` | 90 | 1000 | 500 | 0,1–0,9 | distribuído no mesmo repositório (origem a confirmar) | não: `make literature-big` |

Observações:

- Os clusters têm 1 ou 2 vértices em todos os conjuntos. `random` e `nsfnet`
  têm arestas entre vértices do mesmo cluster, o que o modelo aceita.
- Como já haviam notado Furini, Malaguti & Santini (2018, §5.1), as instâncias
  `ring_n{10,15,20}p1.0s{1..5}` são cinco cópias idênticas de três instâncias
  (12 arquivos redundantes). Elas foram mantidas para preservar os nomes
  originais; nas análises, conte cada grupo uma vez.
- `manifest.csv` lista cada instância com n, m, k, densidade, maior cluster,
  arquivo de origem e sha256 do arquivo convertido.

## Licença e citação

O repositório de origem é distribuído sob a **GNU GPL v3.0**. As instâncias são
redistribuídas aqui, convertidas, com atribuição. Ao usá-las, cite:

- F. Furini, E. Malaguti, A. Santini. *An exact algorithm for the Partition
  Coloring Problem*. Computers & Operations Research 92:170–181, 2018.
  doi:10.1016/j.cor.2017.12.019
- Y. Frota, N. Maculan, T. F. Noronha, C. C. Ribeiro. *A branch-and-cut
  algorithm for partition coloring*. Networks 55(3):194–204, 2010.
- G. Li, R. Simha. *The partition coloring problem and its application to
  wavelength routing and assignment*. Proc. 1st Workshop on Optical Networks, 2000.
