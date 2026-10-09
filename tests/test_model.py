import pytest

from src.model import Instance, InstanceError, Solution, iter_bits


def small():
    # Caminho 0-1-2-3 com clusters {0,1} e {2,3}.
    return Instance.from_edges(4, [[0, 1], [2, 3]], [(0, 1), (1, 2), (2, 3)], name="p4")


def test_iter_bits():
    assert list(iter_bits(0)) == []
    assert list(iter_bits(0b10110)) == [1, 2, 4]
    assert list(iter_bits(1 << 2000)) == [2000]


def test_basic_accessors():
    inst = small()
    assert (inst.n, inst.m, inst.k) == (4, 3, 2)
    assert inst.density == pytest.approx(3 / 6)
    assert [inst.degree(v) for v in range(4)] == [1, 2, 2, 1]
    assert inst.neighbors(1) == [0, 2]
    assert inst.has_edge(1, 2) and inst.has_edge(2, 1)
    assert not inst.has_edge(0, 3)
    assert list(inst.edges()) == [(0, 1), (1, 2), (2, 3)]
    assert inst.cluster_sizes() == (2, 2)
    assert inst.cluster_of == (0, 0, 1, 1)
    assert inst.cluster_mask == (0b0011, 0b1100)


def test_intra_cluster_edges_are_allowed():
    inst = Instance.from_edges(3, [[0, 1], [2]], [(0, 1)])
    assert inst.has_edge(0, 1)


def test_equality_ignores_name_and_meta():
    a = small()
    b = Instance.from_edges(4, [[0, 1], [2, 3]], [(2, 3), (1, 0), (2, 1)], name="x", meta={"s": 1})
    assert a == b and hash(a) == hash(b)
    assert a != Instance.from_edges(4, [[0, 1], [2, 3]], [(0, 1)])


@pytest.mark.parametrize(
    "n, clusters, match",
    [
        (3, [], "ao menos 1 cluster"),
        (3, [[0, 1], [], [2]], "vazio"),
        (3, [[0, 1], [1, 2]], "aparece nos clusters"),
        (3, [[0, 0], [1, 2]], "aparece nos clusters"),
        (3, [[0], [1]], "fora de qualquer cluster"),
        (3, [[0, 1], [2, 3]], "fora do intervalo"),
        (3, [[0, 1.5], [2]], "não é um inteiro"),
        (0, [[0]], "ao menos 1 vértice"),
    ],
)
def test_rejects_invalid_partition(n, clusters, match):
    with pytest.raises(InstanceError, match=match):
        Instance.from_edges(n, clusters, [])


@pytest.mark.parametrize(
    "edges, match",
    [
        ([(1, 1)], "laço"),
        ([(0, 5)], "fora do intervalo"),
        ([(0, 1), (0, 1)], "repetida"),
        ([(0, 1), (1, 0)], "repetida"),
    ],
)
def test_rejects_invalid_edges(edges, match):
    with pytest.raises(InstanceError, match=match):
        Instance.from_edges(3, [[0, 1], [2]], edges)


@pytest.mark.parametrize(
    "adj, match",
    [
        ((0b010, 0b000, 0b000), "assimétrica"),
        ((0b001, 0b000, 0b000), "laço"),
        ((0b1000, 0b000, 0b000), "fora de"),
        ((0b000, 0b000), "entradas"),
    ],
)
def test_constructor_checks_raw_adjacency(adj, match):
    with pytest.raises(InstanceError, match=match):
        Instance(n=3, clusters=((0, 1), (2,)), adj=adj)


def test_accepts_numpy_integers_beyond_64_bits():
    np = pytest.importorskip("numpy")
    n = np.int64(70)
    inst = Instance.from_edges(n, [np.arange(65), np.arange(65, 70)], [(np.int64(0), np.int64(69))])
    assert all(type(v) is int for c in inst.clusters for v in c)
    assert inst.has_edge(0, 69) and inst.n == 70
    assert inst.cluster_mask[1] == sum(1 << v for v in range(65, 70))


def test_solution_coerces_and_counts():
    sol = Solution([1, 3], [5, 5])
    assert sol.selection == (1, 3) and sol.colors == (5, 5)
    assert sol.num_colors == 1


def test_solution_normalized():
    sol = Solution((0, 2, 4, 6), (5, 2, 5, 9)).normalized()
    assert sol.colors == (1, 2, 1, 3)
    assert sol.selection == (0, 2, 4, 6)


def test_solution_formatting_is_one_based():
    sol = Solution((2, 6), (1, 2))
    assert sol.format_selection() == "[(Cluster 1: v_3), (Cluster 2: v_7)]"
    assert sol.format_coloring() == "{v_3: Cor 1, v_7: Cor 2}"


def test_to_networkx(toy):
    pytest.importorskip("networkx")
    g = toy.to_networkx()
    assert g.number_of_nodes() == toy.n and g.number_of_edges() == toy.m
    assert g.nodes[7]["cluster"] == 3
