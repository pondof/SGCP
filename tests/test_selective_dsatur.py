import itertools
from pathlib import Path

import pytest

from src.algorithms import color_upper_bound, selective_dsatur
from src.instance_io import load_instance
from src.model import Instance
from src.validator import ensure_valid

ROOT = Path(__file__).resolve().parents[1]
VERSIONED = sorted(
    [*(ROOT / "instances" / "small").glob("*.txt")]
    + [*(ROOT / "instances" / "literature" / "random").glob("*.txt")]
    + [*(ROOT / "instances" / "literature" / "nsfnet").glob("*.txt")]
    + [*(ROOT / "instances" / "literature" / "ring").glob("*s1.txt")]
)


def _singletons(n, edges):
    """Clusters unitários: o SGCP vira a coloração clássica."""
    return Instance.from_edges(n, [[v] for v in range(n)], edges)


def test_toy_reaches_optimum(toy):
    sol = selective_dsatur(toy)
    ensure_valid(toy, sol, claimed_value=2)
    assert sol.num_colors == toy.meta["optimum"] == 2


@pytest.mark.parametrize("path", VERSIONED, ids=lambda p: p.stem)
def test_valid_and_within_bound(path):
    inst = load_instance(path)
    sol = selective_dsatur(inst)
    report = ensure_valid(inst, sol, claimed_value=sol.num_colors)
    assert report.contiguous  # first fit usa as cores 1..c
    assert sol.num_colors <= color_upper_bound(inst) <= inst.k


def test_deterministic():
    inst = load_instance(VERSIONED[0])
    assert selective_dsatur(inst) == selective_dsatur(inst)


def test_complete_graph_with_singletons_needs_n_colors():
    inst = _singletons(5, itertools.combinations(range(5), 2))
    assert selective_dsatur(inst).num_colors == 5 == color_upper_bound(inst)


def test_even_cycle_with_singletons_is_bipartite():
    # O DSATUR é exato em grafos bipartidos.
    n = 8
    inst = _singletons(n, [(v, (v + 1) % n) for v in range(n)])
    assert selective_dsatur(inst).num_colors == 2


def test_edgeless_graph_uses_one_color():
    inst = Instance.from_edges(6, [[0, 1], [2, 3, 4], [5]], [])
    assert selective_dsatur(inst).num_colors == 1


def test_picks_vertex_that_avoids_conflicts():
    # V1 = {0}, V2 = {1, 2}: 1 é vizinho de 0, 2 não. Basta uma cor.
    inst = Instance.from_edges(3, [[0], [1, 2]], [(0, 1)])
    sol = selective_dsatur(inst)
    assert sol.selection == (0, 2) and sol.num_colors == 1
    assert color_upper_bound(inst) == 2  # δ(0) = 1: o limite não é justo aqui


def test_single_cluster():
    inst = Instance.from_edges(3, [[0, 1, 2]], [(0, 1), (1, 2)])
    sol = selective_dsatur(inst)
    assert len(sol.selection) == 1 and sol.colors == (1,)
