# Grafos perfeitos pequenos (coleção-semente do gerador)

Arquivos de **Brendan McKay**, *Combinatorial Data — Perfect graphs*
(<https://users.cecs.anu.edu.au/~bdm/data/graphs.html>), baixados em
2026-10-11 sem modificação. Cada linha é um grafo no formato
[graph6](https://users.cecs.anu.edu.au/~bdm/data/formats.txt). Cada arquivo
traz todos os grafos perfeitos com aquele número de vértices, a menos de
isomorfismo, conexos ou não.

| Arquivo | Vértices | Grafos | Conexos |
|---|---:|---:|---:|
| `perfect5.g6` | 5 | 33 | 20 |
| `perfect6.g6` | 6 | 148 | 105 |
| `perfect7.g6` | 7 | 906 | 724 |
| `perfect8.g6` | 8 | 8 887 | 7 805 |
| `perfect9.g6` | 9 | 136 756 | 126 777 |

sha256 (`shasum -a 256 data/perfect_graphs/*.g6`):

```text
f1b4a21a5b9cdd1de924920aae744a10ea0d410dc7fb96b4abfc7a774db135d1  perfect5.g6
254d9be84ab6631ca7086048540740825db7f8993b9abaf2d89510a111843ef6  perfect6.g6
96947988db4639ecade2726a1673bb438380b06f8c48231f71ddf3fa0f901737  perfect7.g6
22a30a46889d34f552082bc7acd94ccab21b359babdf78bb5d96f7830bf59a6b  perfect8.g6
4a647cb09b2b9d96e59cf0a0b7f3cafff4c2e1ca4a59820789059bb8ab94c1e9  perfect9.g6
```

Şeker, Ekim & Taşkın (2021, §5) usam essa mesma coleção, filtrada para grafos
conexos, como conjunto P de onde o *Algorithm PerfectGen* sorteia grafos. Em
`src/generator.py`, o filtro de conexidade é aplicado no momento do sorteio
(por rejeição), e P é completado pelos 10 grafos conexos com 1 a 4 vértices,
listados em `SMALL_CONNECTED_GRAPH6`; todo grafo com até 4 vértices é perfeito.
