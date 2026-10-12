"""Gerador de instâncias do SGCP em grafos perfeitos (Şeker, Ekim & Taşkın, 2021).

Grafo — *Algorithm PerfectGen* (§5 do artigo): parte de um grafo perfeito
pequeno e conexo, sorteado da coleção P de McKay (grafos perfeitos com até 9
vértices, em ``data/perfect_graphs/``), e o estende com operações que preservam
perfeição até ter exatamente n vértices. Se a densidade final d está a menos de
ε da densidade desejada δ, o grafo é aceito; se 1 - d está, aceita-se o
complemento; senão, recomeça do zero. As seis operações são: identificação de
cliques, substituição, composição, união disjunta, junção e complemento.

Desvio documentado (``steer``): com a escolha uniforme do artigo, densidades
como δ = 0,1 praticamente nunca são atingidas para n >= 200 (0% de aceitação
nos nossos testes). Por isso, a cada passo são gerados ``steer`` candidatos
independentes e fica o de densidade mais próxima do alvo (δ ou 1 - δ, o que
estiver mais perto). Como toda operação preserva perfeição, a saída continua
perfeita; muda só a distribuição. Com ``steer=1`` o algoritmo é o do artigo.

Partição (§5): permutação aleatória dos vértices cortada em blocos
consecutivos de tamanho r ~ U{lo..hi}; o último bloco fica com o que sobrar
(pode ter menos de ``lo`` vértices, como no artigo).

Todos os grafos são manipulados como listas de bitsets (``adj[v]`` é um
``int``), a mesma representação de ``model.Instance``.

Uso::

    python -m src.generator single --n 100 --density 0.3 --clusters 2 5 \\
        --seed 42 --output instances/exemplo.txt
    python -m src.generator suite --tiers small medium large
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import random
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .instance_io import format_text, load_instance, save_instance
from .model import Instance, iter_bits

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "perfect_graphs"
REFERENCE = "Şeker, Ekim & Taşkın (2021)"

OPERATIONS = (
    "clique_identification",
    "substitution",
    "composition",
    "disjoint_union",
    "join",
    "complement",
)

# Grafos conexos com 1 a 4 vértices (todos são perfeitos), em graph6. Os
# arquivos de McKay começam em 5 vértices; sem estes, não haveria G' quando
# faltam menos de 5 vértices para chegar a n.
SMALL_CONNECTED_GRAPH6 = ("@", "A_", "Bo", "Bw", "CF", "Ck", "CN", "Cl", "C|", "C~")


class GenerationError(RuntimeError):
    """O gerador não atingiu a densidade pedida dentro do limite de tentativas."""


# ---------------------------------------------------------------------------
# Coleção-semente P
# ---------------------------------------------------------------------------


def decode_graph6(line: bytes | str) -> list[int]:
    """Decodifica uma linha graph6 (n <= 62) em adjacência por bitsets."""
    data = line.encode("ascii") if isinstance(line, str) else line
    data = data.strip()
    if data.startswith(b">>graph6<<"):
        data = data[10:]
    if not data or not 63 <= data[0] <= 125:
        raise ValueError(f"graph6 inválido ou com n > 62: {data[:10]!r}")
    n = data[0] - 63
    body = data[1:]
    num_bits = n * (n - 1) // 2
    if len(body) != (num_bits + 5) // 6 or any(not 63 <= c <= 126 for c in body):
        raise ValueError(f"graph6 malformado: {data!r}")
    word = 0
    for c in body:
        word = (word << 6) | (c - 63)
    shift = 6 * len(body)
    adj = [0] * n
    # Triângulo superior coluna a coluna: x(0,1), x(0,2), x(1,2), x(0,3), ...
    for j in range(1, n):
        for i in range(j):
            shift -= 1
            if (word >> shift) & 1:
                adj[i] |= 1 << j
                adj[j] |= 1 << i
    return adj


def is_connected(adj: Sequence[int]) -> bool:
    """BFS por bitsets: verdadeiro se o grafo tem exatamente uma componente."""
    if not adj:
        return False
    seen = frontier = 1
    while frontier:
        reached = 0
        for v in iter_bits(frontier):
            reached |= adj[v]
        frontier = reached & ~seen
        seen |= reached
    return seen == (1 << len(adj)) - 1


class SeedPool:
    """Coleção P de grafos perfeitos pequenos, agrupados por número de vértices.

    ``sample`` sorteia uniformemente entre os grafos *conexos* de P com até
    ``max_vertices`` vértices: sorteia entre todos e rejeita os desconexos. As
    linhas graph6 são decodificadas só quando sorteadas.
    """

    def __init__(self, groups: dict[int, Sequence[bytes]]) -> None:
        self._sizes = sorted(s for s, g in groups.items() if g)
        self._groups = [list(groups[s]) for s in self._sizes]
        self._cumulative: list[int] = []
        total = 0
        for g in self._groups:
            total += len(g)
            self._cumulative.append(total)

    @classmethod
    def from_directory(cls, directory: Path = DATA_DIR, max_size: int = 9) -> SeedPool:
        groups: dict[int, list[bytes]] = {}
        for code in SMALL_CONNECTED_GRAPH6:
            raw = code.encode("ascii")
            groups.setdefault(raw[0] - 63, []).append(raw)
        for size in range(5, max_size + 1):
            path = directory / f"perfect{size}.g6"
            groups[size] = path.read_bytes().split()
        return cls(groups)

    @property
    def sizes(self) -> tuple[int, ...]:
        return tuple(self._sizes)

    def count(self, max_vertices: int | None = None) -> int:
        """Número de grafos (conexos ou não) com até ``max_vertices`` vértices."""
        i = len(self._sizes) if max_vertices is None else bisect.bisect_right(self._sizes, max_vertices)
        return self._cumulative[i - 1] if i else 0

    def sample(self, max_vertices: int, rng: random.Random) -> list[int]:
        total = self.count(max_vertices)
        if total == 0:
            raise ValueError(f"nenhum grafo-semente com até {max_vertices} vértices")
        while True:
            idx = rng.randrange(total)
            group = bisect.bisect_right(self._cumulative, idx)
            offset = idx - (self._cumulative[group - 1] if group else 0)
            adj = decode_graph6(self._groups[group][offset])
            if is_connected(adj):
                return adj


@lru_cache(maxsize=1)
def default_pool() -> SeedPool:
    return SeedPool.from_directory()


# ---------------------------------------------------------------------------
# Operações que preservam perfeição (funções puras: não alteram as entradas)
# ---------------------------------------------------------------------------


def disjoint_union(g: Sequence[int], h: Sequence[int]) -> list[int]:
    """G ∪ H; os vértices de H passam a ser len(g), len(g)+1, ..."""
    s = len(g)
    return list(g) + [row << s for row in h]


def join(g: Sequence[int], h: Sequence[int]) -> list[int]:
    """União disjunta mais todas as arestas entre G e H."""
    s = len(g)
    all_g = (1 << s) - 1
    all_h = ((1 << len(h)) - 1) << s
    return [row | all_h for row in g] + [(row << s) | all_g for row in h]


def complement(g: Sequence[int]) -> list[int]:
    full = (1 << len(g)) - 1
    return [full & ~row & ~(1 << v) for v, row in enumerate(g)]


def _remove_vertex(g: Sequence[int], v: int) -> list[int]:
    """Remove v e renumera os vértices seguintes (u > v vira u - 1)."""
    low = (1 << v) - 1
    return [(row & low) | ((row >> (v + 1)) << v) for u, row in enumerate(g) if u != v]


def substitution(g: Sequence[int], h: Sequence[int], rng: random.Random) -> list[int]:
    """Troca um vértice aleatório v de G por H; todo vértice de H herda N(v)."""
    v = rng.randrange(len(g))
    s = len(g)
    nbrs = g[v]
    all_h = ((1 << len(h)) - 1) << s
    out = disjoint_union(g, h)
    for u in iter_bits(nbrs):
        out[u] |= all_h
    for w in range(s, s + len(h)):
        out[w] |= nbrs
    return _remove_vertex(out, v)


def composition(g: Sequence[int], h: Sequence[int], rng: random.Random) -> list[int]:
    """Remove v1 ∈ G e v2 ∈ H (aleatórios) e liga N(v1) a N(v2). Exige |G|, |H| >= 3."""
    if len(g) < 3 or len(h) < 3:
        raise ValueError("composição exige dois grafos com ao menos 3 vértices")
    v1, v2 = rng.randrange(len(g)), rng.randrange(len(h))
    s = len(g)
    n1, n2 = g[v1], h[v2] << s
    out = disjoint_union(g, h)
    for u in iter_bits(n1):
        out[u] |= n2
    for u in iter_bits(n2):
        out[u] |= n1
    return _remove_vertex(_remove_vertex(out, s + v2), v1)


def _random_maximal_clique(g: Sequence[int], v: int, rng: random.Random) -> list[int]:
    """Estende {v} a uma clique maximal acrescentando vizinhos comuns ao acaso."""
    clique, candidates = [v], g[v]
    while candidates:
        u = rng.choice(list(iter_bits(candidates)))
        clique.append(u)
        candidates &= g[u]
    return clique


def clique_identification(g: Sequence[int], h: Sequence[int], rng: random.Random) -> list[int]:
    """Identifica uma clique de G com uma de H (mesmo tamanho) por bijeção aleatória.

    Como no artigo: cada grafo tem um vértice aleatório estendido a uma clique
    maximal (K1 em G, K2 em H); da maior, sorteiam-se tantos vértices quanto a
    menor tem, e esses vértices são unificados aos da menor.
    """
    k1 = _random_maximal_clique(g, rng.randrange(len(g)), rng)
    k2 = _random_maximal_clique(h, rng.randrange(len(h)), rng)
    if len(k1) <= len(k2):
        target = dict(zip(rng.sample(k2, len(k1)), k1))  # vértice de H -> vértice de G
    else:
        target = dict(zip(k2, rng.sample(k1, len(k2))))
    mapping, nxt = [], len(g)
    for w in range(len(h)):
        if w in target:
            mapping.append(target[w])
        else:
            mapping.append(nxt)
            nxt += 1
    out = list(g) + [0] * (nxt - len(g))
    for w, row in enumerate(h):
        mw = mapping[w]
        for x in iter_bits(row):
            out[mw] |= 1 << mapping[x]
    return out


# ---------------------------------------------------------------------------
# PerfectGen
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationStats:
    attempts: int  # grafos construídos até o aceito (inclusive)
    complemented: bool  # o grafo aceito foi o complemento do construído
    ops: dict[str, int]  # quantas vezes cada operação foi aplicada no grafo aceito


def edge_density(adj: Sequence[int]) -> float:
    n = len(adj)
    return sum(row.bit_count() for row in adj) / (n * (n - 1)) if n > 1 else 0.0


def _random_step(
    g: list[int], n: int, pool: SeedPool, rng: random.Random
) -> tuple[str, list[int]] | None:
    """Aplica uma operação uniforme a G (e a um G' de P que caiba em n); None se inválida."""
    op = OPERATIONS[rng.randrange(len(OPERATIONS))]
    if op == "complement":
        return op, complement(g)
    h = pool.sample(n - len(g), rng)
    if op == "clique_identification":
        return op, clique_identification(g, h, rng)
    if op == "substitution":
        return op, substitution(g, h, rng)
    if op == "composition":
        if len(g) < 3 or len(h) < 3:
            return None
        return op, composition(g, h, rng)
    if op == "disjoint_union":
        return op, disjoint_union(g, h)
    return op, join(g, h)


def _relabel(adj: Sequence[int], rng: random.Random) -> list[int]:
    """Permuta os rótulos dos vértices ao acaso."""
    perm = list(range(len(adj)))
    rng.shuffle(perm)
    out = [0] * len(adj)
    for v, row in enumerate(adj):
        out[perm[v]] = sum(1 << perm[u] for u in iter_bits(row))
    return out


def perfect_gen(
    n: int,
    density: float,
    rng: random.Random,
    *,
    epsilon: float = 0.025,
    steer: int = 3,
    max_attempts: int = 1000,
    pool: SeedPool | None = None,
) -> tuple[list[int], GenerationStats]:
    """Gera um grafo perfeito com n vértices e densidade em (δ - ε, δ + ε)."""
    if n < 2:
        raise ValueError(f"n deve ser >= 2 (n = {n})")
    if not 0.0 <= density <= 1.0:
        raise ValueError(f"densidade fora de [0, 1]: {density}")
    if epsilon <= 0 or steer < 1 or max_attempts < 1:
        raise ValueError("epsilon deve ser > 0; steer e max_attempts devem ser >= 1")
    pool = pool or default_pool()

    for attempt in range(1, max_attempts + 1):
        ops: Counter[str] = Counter()
        g = pool.sample(n, rng)
        while len(g) < n:
            candidates = [c for c in (_random_step(g, n, pool, rng) for _ in range(steer)) if c]
            if not candidates:
                continue
            if len(candidates) > 1:
                d = edge_density(g)
                goal = density if abs(d - density) <= abs(d - (1 - density)) else 1 - density
                op, g = min(candidates, key=lambda c: abs(edge_density(c[1]) - goal))
            else:
                op, g = candidates[0]
            ops[op] += 1

        d = edge_density(g)
        if abs(d - density) < epsilon:
            complemented = False
        elif abs((1 - d) - density) < epsilon:
            g, complemented = complement(g), True
        else:
            continue
        stats = GenerationStats(attempt, complemented, {op: ops[op] for op in OPERATIONS})
        return _relabel(g, rng), stats

    raise GenerationError(
        f"densidade {density} ± {epsilon} não atingida com n = {n} em {max_attempts} "
        f"tentativas; aumente steer (atual: {steer}), epsilon ou max_attempts"
    )


# ---------------------------------------------------------------------------
# Partição e montagem da instância
# ---------------------------------------------------------------------------


def random_partition(n: int, lo: int, hi: int, rng: random.Random) -> list[list[int]]:
    """Permutação aleatória cortada em blocos de tamanho U{lo..hi} (o último leva o resto)."""
    if not 1 <= lo <= hi:
        raise ValueError(f"faixa de tamanhos de cluster inválida: [{lo}, {hi}]")
    order = list(range(n))
    rng.shuffle(order)
    clusters, start = [], 0
    while start < n:
        size = rng.randint(lo, hi)
        clusters.append(sorted(order[start : start + size]))
        start += size
    return clusters


def derive_seed(*parts: object) -> int:
    """Semente de 64 bits derivada de ``parts`` (sha256), estável entre plataformas."""
    key = ":".join(map(str, parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


def generate_graph(
    n: int,
    density: float,
    graph_seed: int,
    *,
    epsilon: float = 0.025,
    steer: int = 3,
    max_attempts: int = 1000,
    pool: SeedPool | None = None,
) -> tuple[list[int], GenerationStats]:
    return perfect_gen(
        n,
        density,
        random.Random(graph_seed),
        epsilon=epsilon,
        steer=steer,
        max_attempts=max_attempts,
        pool=pool,
    )


def build_instance(
    adj: Sequence[int],
    stats: GenerationStats,
    density: float,
    cluster_range: tuple[int, int],
    graph_seed: int,
    partition_seed: int,
    *,
    epsilon: float = 0.025,
    steer: int = 3,
    name: str = "",
) -> Instance:
    """Combina um grafo gerado por ``perfect_gen`` com uma partição aleatória."""
    lo, hi = cluster_range
    clusters = random_partition(len(adj), lo, hi, random.Random(partition_seed))
    meta = {
        "generator": "perfectgen",
        "graph_class": "perfect",
        "reference": REFERENCE,
        "density_target": density,
        "density": round(edge_density(adj), 4),
        "epsilon": epsilon,
        "steer": steer,
        "complemented": stats.complemented,
        "attempts": stats.attempts,
        "ops": stats.ops,
        "cluster_min": lo,
        "cluster_max": hi,
        "graph_seed": graph_seed,
        "partition_seed": partition_seed,
    }
    return Instance(
        n=len(adj),
        clusters=tuple(tuple(c) for c in clusters),
        adj=tuple(adj),
        name=name,
        meta=meta,
    )


def generate_instance(
    n: int,
    density: float,
    cluster_range: tuple[int, int],
    graph_seed: int,
    partition_seed: int,
    *,
    epsilon: float = 0.025,
    steer: int = 3,
    max_attempts: int = 1000,
    pool: SeedPool | None = None,
    name: str = "",
) -> Instance:
    """Gera uma instância completa; os metadados bastam para regenerá-la."""
    adj, stats = generate_graph(
        n, density, graph_seed, epsilon=epsilon, steer=steer, max_attempts=max_attempts, pool=pool
    )
    return build_instance(
        adj, stats, density, cluster_range, graph_seed, partition_seed,
        epsilon=epsilon, steer=steer, name=name,
    )


def regenerate(inst: Instance, pool: SeedPool | None = None) -> Instance:
    """Regenera uma instância do PerfectGen a partir dos seus metadados."""
    meta = inst.meta
    return generate_instance(
        inst.n,
        meta["density_target"],
        (meta["cluster_min"], meta["cluster_max"]),
        meta["graph_seed"],
        meta["partition_seed"],
        epsilon=meta["epsilon"],
        steer=meta["steer"],
        pool=pool,
        name=inst.name,
    )


# ---------------------------------------------------------------------------
# Suíte de instâncias (grade do artigo)
# ---------------------------------------------------------------------------

DEFAULT_MASTER_SEED = 2021
SUITE_DENSITIES = (0.1, 0.3, 0.5, 0.7)
SUITE_CLUSTER_RANGES = ((2, 5), (4, 7), (6, 9))
SUITE_REPLICATES = 5
TIERS = {
    "small": (50,),
    "medium": (100, 150, 200, 250),
    "large": (300, 350, 400, 450, 500),
}
MANIFEST_FIELDS = (
    "path", "tier", "n", "m", "k", "density_target", "density", "cluster_min",
    "cluster_max", "rep", "graph_seed", "partition_seed", "attempts", "complemented",
    "sha256",
)


def suite_name(n: int, density: float, cluster_range: tuple[int, int], rep: int) -> str:
    lo, hi = cluster_range
    return f"pg_n{n:03d}_d{density}_c{lo}-{hi}_s{rep}"


def build_suite(
    out_dir: Path,
    tiers: Sequence[str] = tuple(TIERS),
    master_seed: int = DEFAULT_MASTER_SEED,
    *,
    epsilon: float = 0.025,
    steer: int = 3,
    log: Callable[[str], None] = print,
) -> list[dict[str, object]]:
    """Gera a grade do artigo nas faixas pedidas e atualiza ``manifest.csv``.

    Cada grafo (n, δ, rep) é gerado uma vez e pareado com as três faixas de
    tamanho de cluster, como no artigo. Linhas do manifesto de faixas não
    geradas nesta chamada são preservadas.
    """
    pool = default_pool()
    rows: list[dict[str, object]] = []
    for tier in tiers:
        (out_dir / tier).mkdir(parents=True, exist_ok=True)
        for n in TIERS[tier]:
            start = time.perf_counter()
            for density in SUITE_DENSITIES:
                for rep in range(1, SUITE_REPLICATES + 1):
                    graph_seed = derive_seed(master_seed, n, density, rep)
                    adj, stats = generate_graph(
                        n, density, graph_seed, epsilon=epsilon, steer=steer, pool=pool
                    )
                    for cluster_range in SUITE_CLUSTER_RANGES:
                        lo, hi = cluster_range
                        partition_seed = derive_seed(master_seed, n, density, rep, f"{lo}-{hi}")
                        name = suite_name(n, density, cluster_range, rep)
                        inst = build_instance(
                            adj, stats, density, cluster_range, graph_seed, partition_seed,
                            epsilon=epsilon, steer=steer, name=name,
                        )
                        content = format_text(inst).encode("utf-8")
                        rel = f"{tier}/{name}.txt"
                        (out_dir / rel).write_bytes(content)
                        rows.append({
                            "path": rel, "tier": tier, "n": n, "m": inst.m, "k": inst.k,
                            "density_target": density, "density": inst.meta["density"],
                            "cluster_min": lo, "cluster_max": hi, "rep": rep,
                            "graph_seed": graph_seed, "partition_seed": partition_seed,
                            "attempts": stats.attempts, "complemented": stats.complemented,
                            "sha256": hashlib.sha256(content).hexdigest(),
                        })
            log(f"{tier:>6}  n = {n:3d}: {len(SUITE_DENSITIES) * SUITE_REPLICATES} grafos, "
                f"{len(SUITE_DENSITIES) * SUITE_REPLICATES * len(SUITE_CLUSTER_RANGES)} "
                f"instâncias em {time.perf_counter() - start:.1f} s")
    _update_manifest(out_dir / "manifest.csv", rows)
    return rows


def _update_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    merged: dict[str, dict[str, object]] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            merged = {row["path"]: row for row in csv.DictReader(fh)}
    merged.update((str(row["path"]), row) for row in rows)
    tier_order = {t: i for i, t in enumerate(TIERS)}
    ordered = sorted(merged.values(), key=lambda r: (tier_order.get(str(r["tier"]), 99), str(r["path"])))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.generator",
        description="Gerador de instâncias do SGCP em grafos perfeitos (PerfectGen).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    one = sub.add_parser("single", help="gera uma instância")
    one.add_argument("--n", type=int, required=True, help="número de vértices")
    one.add_argument("--density", type=float, required=True, help="densidade desejada δ")
    one.add_argument("--clusters", type=int, nargs=2, metavar=("MIN", "MAX"), default=(2, 5),
                     help="faixa de tamanhos de cluster (padrão: 2 5)")
    one.add_argument("--seed", type=int, required=True, help="semente (grafo e partição)")
    one.add_argument("--output", type=Path, required=True, help="arquivo .txt ou .json")
    one.add_argument("--name", default="", help="nome da instância (padrão: nome do arquivo)")
    one.add_argument("--epsilon", type=float, default=0.025)
    one.add_argument("--steer", type=int, default=3, help="candidatos por passo (1 = artigo original)")
    one.add_argument("--max-attempts", type=int, default=1000)

    suite = sub.add_parser("suite", help="gera a grade de instâncias do artigo")
    suite.add_argument("--tiers", nargs="+", choices=tuple(TIERS), default=list(TIERS))
    suite.add_argument("--out-dir", type=Path, default=ROOT / "instances")
    suite.add_argument("--master-seed", type=int, default=DEFAULT_MASTER_SEED)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "single":
        name = args.name or args.output.stem
        lo, hi = args.clusters
        inst = generate_instance(
            args.n, args.density, (lo, hi),
            derive_seed(args.seed, "graph"), derive_seed(args.seed, "partition"),
            epsilon=args.epsilon, steer=args.steer, max_attempts=args.max_attempts, name=name,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        save_instance(inst, args.output)
        load_instance(args.output)  # confere a ida e volta
        print(f"{args.output}: n = {inst.n}, m = {inst.m}, k = {inst.k}, "
              f"densidade = {inst.meta['density']}, tentativas = {inst.meta['attempts']}")
    else:
        start = time.perf_counter()
        rows = build_suite(args.out_dir, args.tiers, args.master_seed)
        print(f"{len(rows)} instâncias em {args.out_dir} ({time.perf_counter() - start:.1f} s); "
              f"manifesto: {args.out_dir / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
