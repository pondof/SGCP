"""Estruturas de dados do SGCP: instância (grafo + partição) e solução.

Convenções adotadas em todo o projeto:

- Internamente, vértices e clusters são indexados a partir de 0. Em arquivos e
  em tudo o que é exibido ao usuário a indexação começa em 1; a conversão
  acontece apenas em ``instance_io`` e nos métodos ``format_*``.
- A adjacência é armazenada como bitsets: ``adj[v]`` é um ``int`` cujo bit
  ``u`` vale 1 se, e somente se, a aresta {u, v} existe. Isso mantém instâncias
  grandes compactas (~n²/8 bytes) e permite operações de conjunto em lote,
  como ``(adj[v] & mascara).bit_count()``.
- Cores são rótulos inteiros positivos (1, 2, ...), exibidos como estão.
"""

from __future__ import annotations

import operator
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any


class InstanceError(ValueError):
    """Instância malformada (partição inválida, aresta inválida etc.)."""


def iter_bits(mask: int) -> Iterator[int]:
    """Itera, em ordem crescente, os índices dos bits ligados de ``mask`` (>= 0).

    Varre a representação binária com ``str.find`` (em C): ~2,5x mais rápido
    que isolar o bit menos significativo a cada passo em máscaras densas.
    """
    bits = bin(mask)[:1:-1]  # remove o prefixo "0b" e inverte: bits[i] é o bit i
    i = bits.find("1")
    while i != -1:
        yield i
        i = bits.find("1", i + 1)


def _as_vertex(v: Any, n: int, where: str) -> int:
    try:
        v = operator.index(v)
    except TypeError:
        raise InstanceError(f"{where}: vértice {v!r} não é um inteiro") from None
    if not 0 <= v < n:
        raise InstanceError(f"{where}: vértice {v} fora do intervalo [0, {n})")
    return v


@dataclass(frozen=True, slots=True)
class Instance:
    """Instância do SGCP: grafo G = (V, E) com V particionado em V_1, ..., V_k.

    A igualdade (``==``) compara apenas a estrutura (n, partição e arestas),
    ignorando ``name`` e ``meta``.
    """

    n: int
    clusters: tuple[tuple[int, ...], ...]
    adj: tuple[int, ...]
    name: str = field(default="", compare=False)
    meta: dict[str, Any] = field(default_factory=dict, compare=False)
    # Derivados, calculados em __post_init__.
    m: int = field(init=False, compare=False)
    cluster_of: tuple[int, ...] = field(init=False, repr=False, compare=False)
    cluster_mask: tuple[int, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # operator.index converte inteiros "de fora" (ex.: numpy.int64) em int.
        n = operator.index(self.n)
        if n < 1:
            raise InstanceError(f"o grafo precisa de ao menos 1 vértice (n = {n})")

        clusters = tuple(
            tuple(_as_vertex(v, n, f"cluster {i + 1}") for v in c)
            for i, c in enumerate(self.clusters)
        )
        if not clusters:
            raise InstanceError("a partição precisa de ao menos 1 cluster")
        cluster_of = [-1] * n
        for i, cluster in enumerate(clusters):
            if not cluster:
                raise InstanceError(f"cluster {i + 1} está vazio")
            for v in cluster:
                if cluster_of[v] != -1:
                    raise InstanceError(
                        f"vértice {v + 1} aparece nos clusters "
                        f"{cluster_of[v] + 1} e {i + 1}"
                    )
                cluster_of[v] = i
        missing = [v + 1 for v in range(n) if cluster_of[v] == -1]
        if missing:
            raise InstanceError(f"vértices fora de qualquer cluster: {_preview(missing)}")

        adj = tuple(operator.index(row) for row in self.adj)
        if len(adj) != n:
            raise InstanceError(f"adj tem {len(adj)} entradas; esperado {n}")
        full = (1 << n) - 1
        degree_sum = 0
        for v, row in enumerate(adj):
            if row < 0 or row & ~full:
                raise InstanceError(f"adj[{v}] referencia vértices fora de [0, {n})")
            if (row >> v) & 1:
                raise InstanceError(f"laço no vértice {v + 1}")
            for u in iter_bits(row):
                if not (adj[u] >> v) & 1:
                    raise InstanceError(f"adjacência assimétrica entre {v + 1} e {u + 1}")
            degree_sum += row.bit_count()

        cluster_mask = tuple(sum(1 << v for v in c) for c in clusters)
        object.__setattr__(self, "n", n)
        object.__setattr__(self, "clusters", clusters)
        object.__setattr__(self, "adj", adj)
        object.__setattr__(self, "m", degree_sum // 2)
        object.__setattr__(self, "cluster_of", tuple(cluster_of))
        object.__setattr__(self, "cluster_mask", cluster_mask)

    @classmethod
    def from_edges(
        cls,
        n: int,
        clusters: Iterable[Iterable[int]],
        edges: Iterable[tuple[int, int]],
        name: str = "",
        meta: dict[str, Any] | None = None,
    ) -> Instance:
        """Constrói a instância a partir de uma lista de arestas (0-indexadas).

        Rejeita laços e arestas repetidas (inclusive {u, v} e {v, u}).
        """
        adj = [0] * n
        for idx, (u, v) in enumerate(edges):
            # Caso comum (int nativo no intervalo) primeiro; mensagem só se houver erro.
            if not (type(u) is int and type(v) is int and 0 <= u < n and 0 <= v < n):
                where = f"aresta #{idx + 1}"
                u, v = _as_vertex(u, n, where), _as_vertex(v, n, where)
            if u == v:
                raise InstanceError(f"aresta #{idx + 1}: laço no vértice {u + 1}")
            if (adj[u] >> v) & 1:
                raise InstanceError(f"aresta #{idx + 1}: aresta {{{u + 1}, {v + 1}}} repetida")
            adj[u] |= 1 << v
            adj[v] |= 1 << u
        return cls(
            n=n,
            clusters=tuple(tuple(c) for c in clusters),
            adj=tuple(adj),
            name=name,
            meta=dict(meta or {}),
        )

    @property
    def k(self) -> int:
        """Número de clusters da partição."""
        return len(self.clusters)

    @property
    def density(self) -> float:
        """Densidade de arestas 2m / (n(n-1))."""
        return 2 * self.m / (self.n * (self.n - 1)) if self.n > 1 else 0.0

    def neighbors(self, v: int) -> list[int]:
        return list(iter_bits(self.adj[v]))

    def degree(self, v: int) -> int:
        return self.adj[v].bit_count()

    def has_edge(self, u: int, v: int) -> bool:
        return bool((self.adj[u] >> v) & 1)

    def edges(self) -> Iterator[tuple[int, int]]:
        """Itera as arestas como pares (u, v) com u < v, em ordem lexicográfica."""
        for u, row in enumerate(self.adj):
            for w in iter_bits(row >> (u + 1)):
                yield u, u + 1 + w

    def cluster_sizes(self) -> tuple[int, ...]:
        return tuple(len(c) for c in self.clusters)

    def to_networkx(self):
        """Converte para ``networkx.Graph``; cada nó recebe o atributo ``cluster``."""
        import networkx as nx

        g = nx.Graph(name=self.name)
        g.add_nodes_from((v, {"cluster": self.cluster_of[v]}) for v in range(self.n))
        g.add_edges_from(self.edges())
        return g


@dataclass(frozen=True, slots=True)
class Solution:
    """Solução do SGCP: um representante por cluster e a cor de cada um.

    ``selection[i]`` é o vértice escolhido em V_i e ``colors[i]`` é a sua cor.
    A classe não valida nada por conta própria — soluções inválidas precisam
    ser representáveis para que ``validator`` possa rejeitá-las.
    """

    selection: tuple[int, ...]
    colors: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selection", tuple(self.selection))
        object.__setattr__(self, "colors", tuple(self.colors))

    @property
    def num_colors(self) -> int:
        """Valor da função objetivo: número de cores distintas usadas."""
        return len(set(self.colors))

    def normalized(self) -> Solution:
        """Reetiqueta as cores como 1..c, na ordem da primeira ocorrência."""
        relabel: dict[int, int] = {}
        for c in self.colors:
            relabel.setdefault(c, len(relabel) + 1)
        return Solution(self.selection, tuple(relabel[c] for c in self.colors))

    def format_selection(self) -> str:
        """Ex.: ``[(Cluster 1: v_3), (Cluster 2: v_7)]``."""
        parts = (f"(Cluster {i + 1}: v_{v + 1})" for i, v in enumerate(self.selection))
        return "[" + ", ".join(parts) + "]"

    def format_coloring(self) -> str:
        """Ex.: ``{v_3: Cor 1, v_7: Cor 2}``."""
        parts = (f"v_{v + 1}: Cor {c}" for v, c in zip(self.selection, self.colors))
        return "{" + ", ".join(parts) + "}"


def _preview(items: Sequence[Any], limit: int = 10) -> str:
    shown = ", ".join(map(str, items[:limit]))
    return shown + (f", ... (+{len(items) - limit})" if len(items) > limit else "")
