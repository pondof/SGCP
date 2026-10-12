import random
from pathlib import Path

import networkx as nx
import pytest

from src import generator as gen
from src.instance_io import format_text, load_instance, parse_text
from src.model import iter_bits

ROOT = Path(__file__).resolve().parents[1]


def edge_set(adj):
    return {(u, v) for u, row in enumerate(adj) for v in iter_bits(row) if u < v}


def to_nx(adj):
    g = nx.Graph()
    g.add_nodes_from(range(len(adj)))
    g.add_edges_from(edge_set(adj))
    return g


def assert_simple(adj):
    for v, row in enumerate(adj):
        assert not (row >> v) & 1, f"laço em {v}"
        assert row >> len(adj) == 0, f"vizinho fora do intervalo em {v}"
        for u in iter_bits(row):
            assert (adj[u] >> v) & 1, f"assimetria entre {u} e {v}"


@pytest.fixture(scope="module")
def pool():
    return gen.default_pool()


class FixedRng:
    """Substitui ``random.Random`` devolvendo valores pré-definidos em ``randrange``."""

    def __init__(self, *values):
        self.values = list(values)

    def randrange(self, _n):
        return self.values.pop(0)


# --- graph6 e coleção-semente ------------------------------------------------


@pytest.mark.parametrize("size", [5, 6, 7])
def test_decode_graph6_matches_networkx(size):
    for line in (gen.DATA_DIR / f"perfect{size}.g6").read_bytes().split():
        assert edge_set(gen.decode_graph6(line)) == {
            tuple(sorted(e)) for e in nx.from_graph6_bytes(line).edges()
        }


def test_decode_graph6_matches_networkx_on_9_vertex_sample():
    lines = (gen.DATA_DIR / "perfect9.g6").read_bytes().split()
    for line in random.Random(0).sample(lines, 2000):
        assert edge_set(gen.decode_graph6(line)) == {
            tuple(sorted(e)) for e in nx.from_graph6_bytes(line).edges()
        }


@pytest.mark.parametrize("bad", [b"", b"D?", b"D??\x7f", b"~?@d", b"D? "])
def test_decode_graph6_rejects_malformed(bad):
    with pytest.raises(ValueError):
        gen.decode_graph6(bad)


def test_small_connected_constant_is_complete():
    decoded = [to_nx(gen.decode_graph6(code)) for code in gen.SMALL_CONNECTED_GRAPH6]
    atlas = [g for g in nx.graph_atlas_g() if 1 <= g.number_of_nodes() <= 4 and nx.is_connected(g)]
    assert len(decoded) == len(atlas) == 10
    for g in atlas:
        assert sum(nx.is_isomorphic(g, h) for h in decoded) == 1


def test_pool_counts_match_mckay(pool):
    # McKay: 33, 148, 906, 8887 e 136756 grafos perfeitos com 5..9 vértices.
    assert pool.sizes == tuple(range(1, 10))
    assert pool.count() == 10 + 33 + 148 + 906 + 8887 + 136756
    assert pool.count(4) == 10 and pool.count(0) == 0


def test_pool_sample_respects_size_and_connectivity(pool):
    rng = random.Random(1)
    for max_vertices in range(1, 10):
        for _ in range(30):
            g = pool.sample(max_vertices, rng)
            assert 1 <= len(g) <= max_vertices
            assert gen.is_connected(g)
            assert_simple(g)


def test_is_connected():
    assert gen.is_connected([0])
    assert gen.is_connected([0b10, 0b01])
    assert not gen.is_connected([0, 0])
    assert not gen.is_connected([])


# --- operações -----------------------------------------------------------------

P3 = [0b010, 0b101, 0b010]  # caminho 0-1-2
K2 = [0b10, 0b01]


def test_union_join_complement_exact():
    assert edge_set(gen.disjoint_union(K2, K2)) == {(0, 1), (2, 3)}
    assert edge_set(gen.join(K2, K2)) == {(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)}
    assert edge_set(gen.complement(P3)) == {(0, 2)}


def test_substitution_exact():
    # O vértice central de P3 vira um K2 ligado às duas pontas: K4 sem a aresta {0, 1}.
    out = gen.substitution(P3, K2, FixedRng(1))
    assert edge_set(out) == {(0, 2), (0, 3), (1, 2), (1, 3), (2, 3)}


def test_composition_exact():
    # Remover o centro de dois P3 e ligar as pontas entre si forma um C4.
    out = gen.composition(P3, P3, FixedRng(1, 1))
    assert edge_set(out) == {(0, 2), (0, 3), (1, 2), (1, 3)}
    with pytest.raises(ValueError):
        gen.composition(P3, K2, FixedRng(0, 0))


def apply_operation(op, g, h, rng):
    if op == "complement":
        return gen.complement(g)
    if op in ("disjoint_union", "join"):
        return getattr(gen, op)(g, h)
    return getattr(gen, op)(g, h, rng)


@pytest.mark.parametrize("op", gen.OPERATIONS)
def test_operation_preserves_perfection(pool, op):
    rng = random.Random(op)
    for _ in range(40):
        g, h = pool.sample(7, rng), pool.sample(7, rng)
        if op == "composition" and (len(g) < 3 or len(h) < 3):
            continue
        g_copy, h_copy = list(g), list(h)
        out = apply_operation(op, g, h, rng)
        assert (g, h) == (g_copy, h_copy), "entradas não podem ser alteradas"
        assert_simple(out)
        expected = {
            "clique_identification": range(max(len(g), len(h)), len(g) + len(h)),
            "substitution": [len(g) + len(h) - 1],
            "composition": [len(g) + len(h) - 2],
            "disjoint_union": [len(g) + len(h)],
            "join": [len(g) + len(h)],
            "complement": [len(g)],
        }[op]
        assert len(out) in expected
        assert nx.is_perfect_graph(to_nx(out))


# --- PerfectGen ----------------------------------------------------------------


@pytest.mark.parametrize("density", [0.1, 0.3, 0.5, 0.7])
def test_perfect_gen_small_graphs(pool, density):
    # Com n < 20, δ = 0,1 quase nunca é aceito: ~94% das sementes são grafos
    # conexos de 9 vértices, que já têm arestas demais.
    for seed in range(4):
        n = 20 + seed
        adj, stats = gen.perfect_gen(n, density, random.Random(seed), pool=pool)
        assert len(adj) == n
        assert_simple(adj)
        assert abs(gen.edge_density(adj) - density) < 0.025
        assert stats.attempts >= 1 and set(stats.ops) == set(gen.OPERATIONS)
        assert nx.is_perfect_graph(to_nx(adj))


def test_perfect_gen_original_uniform_choice(pool):
    adj, stats = gen.perfect_gen(30, 0.5, random.Random(3), steer=1, pool=pool)
    assert len(adj) == 30 and abs(gen.edge_density(adj) - 0.5) < 0.025


def test_perfect_gen_reaches_low_density_at_scale(pool):
    adj, _ = gen.perfect_gen(300, 0.1, random.Random(5), pool=pool)
    assert len(adj) == 300 and abs(gen.edge_density(adj) - 0.1) < 0.025


def test_perfect_gen_gives_up_after_max_attempts(pool):
    # Com n = 40 há 780 pares: nenhuma contagem de arestas dá densidade 0,123456 ± 1e-6.
    with pytest.raises(gen.GenerationError, match="2 tentativas"):
        gen.perfect_gen(40, 0.123456, random.Random(0), epsilon=1e-6, max_attempts=2, pool=pool)


@pytest.mark.parametrize(
    "kwargs",
    [dict(n=1, density=0.5), dict(n=10, density=1.5), dict(n=10, density=0.5, steer=0),
     dict(n=10, density=0.5, epsilon=0)],
)
def test_perfect_gen_rejects_bad_arguments(pool, kwargs):
    n, density = kwargs.pop("n"), kwargs.pop("density")
    with pytest.raises(ValueError):
        gen.perfect_gen(n, density, random.Random(0), pool=pool, **kwargs)


# --- partição, sementes e instâncias ---------------------------------------------


def test_random_partition_covers_everything_once():
    for seed in range(20):
        clusters = gen.random_partition(97, 2, 5, random.Random(seed))
        assert sorted(v for c in clusters for v in c) == list(range(97))
        assert all(2 <= len(c) <= 5 for c in clusters[:-1])
        assert 1 <= len(clusters[-1]) <= 5
        assert all(c == sorted(c) for c in clusters)


def test_random_partition_rejects_bad_range():
    for lo, hi in [(0, 3), (4, 3)]:
        with pytest.raises(ValueError):
            gen.random_partition(10, lo, hi, random.Random(0))


def test_derive_seed_is_stable_and_distinct():
    assert gen.derive_seed(2021, 50, 0.1, 1) == gen.derive_seed(2021, 50, 0.1, 1)
    assert gen.derive_seed(2021, 50, 0.1, 1) != gen.derive_seed(2021, 50, 0.1, 2)
    assert 0 <= gen.derive_seed("x") < 2**64


def test_generate_instance_is_deterministic(pool):
    make = lambda pseed: gen.generate_instance(60, 0.3, (2, 5), 11, pseed, pool=pool, name="t")
    a, b, c = make(7), make(7), make(8)
    assert format_text(a) == format_text(b)
    assert a.adj == c.adj and a.clusters != c.clusters  # mesmo grafo, outra partição


def test_meta_round_trip_allows_regeneration(pool):
    inst = gen.generate_instance(40, 0.5, (4, 7), 5, 6, pool=pool, name="rt")
    back = parse_text(format_text(inst))
    assert back == inst and back.meta == inst.meta
    assert format_text(gen.regenerate(back, pool)) == format_text(inst)
    assert inst.meta["generator"] == "perfectgen"
    assert sum(len(c) for c in inst.clusters) == 40


def test_suite_names_and_tiers():
    assert gen.suite_name(50, 0.1, (2, 5), 1) == "pg_n050_d0.1_c2-5_s1"
    all_n = [n for ns in gen.TIERS.values() for n in ns]
    assert all_n == list(range(50, 501, 50))


@pytest.mark.parametrize(
    "rel", ["small/pg_n050_d0.1_c2-5_s1.txt", "small/pg_n050_d0.7_c6-9_s5.txt",
            "medium/pg_n100_d0.3_c4-7_s2.txt"],
)
def test_committed_instances_are_reproducible(pool, rel):
    path = ROOT / "instances" / rel
    if not path.exists():
        pytest.skip(f"{rel} não gerada (rode `make instances`)")
    inst = load_instance(path)
    assert format_text(gen.regenerate(inst, pool)) == path.read_text(encoding="utf-8")


def test_cli_single(tmp_path):
    out = tmp_path / "x.txt"
    args = ["single", "--n", "30", "--density", "0.3", "--clusters", "2", "4", "--seed", "9",
            "--output", str(out)]
    assert gen.main(args) == 0
    first = out.read_bytes()
    inst = load_instance(out)
    assert (inst.n, inst.name) == (30, "x")
    assert all(1 <= len(c) <= 4 for c in inst.clusters)
    gen.main(args)
    assert out.read_bytes() == first
