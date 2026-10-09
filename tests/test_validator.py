import itertools

import pytest

from src.model import Solution
from src.validator import InvalidSolutionError, ensure_valid, validate

# Na toy (1-indexada): V1={1,2}, V2={3,4}, V3={5,6}, V4={7,8}.
# Aqui os vértices são 0-indexados: v_2 -> 1, v_4 -> 3, v_6 -> 5, v_8 -> 7.
OPTIMAL = Solution((1, 3, 5, 7), (1, 2, 1, 2))  # {2,4,6,8}: arestas {2,4} e {6,8}
NAIVE = Solution((0, 2, 4, 6), (1, 2, 3, 4))  # {1,3,5,7} = K4


def test_optimal_solution_is_valid(toy):
    report = validate(toy, OPTIMAL, claimed_value=2)
    assert report.valid and report.errors == [] and report.warnings == []
    assert report.num_colors == 2 and report.contiguous
    assert report.conflicts == []


def test_naive_solution_is_valid_with_four_colors(toy):
    report = validate(toy, NAIVE)
    assert report.valid and report.num_colors == 4


def test_monochromatic_edge_is_reported(toy):
    report = validate(toy, Solution((1, 3, 5, 7), (1, 1, 1, 2)))
    assert not report.valid
    assert report.conflicts == [(1, 3)]
    assert any("{v_2, v_4}" in e and "Cor 1" in e for e in report.errors)


def test_every_conflict_is_listed(toy):
    report = validate(toy, Solution((0, 2, 4, 6), (1, 1, 1, 1)))
    assert report.conflicts == [(0, 2), (0, 4), (0, 6), (2, 4), (2, 6), (4, 6)]


@pytest.mark.parametrize(
    "selection, colors, match",
    [
        ((0, 1, 4, 6), (1, 2, 3, 4), "cluster 2: vértice v_2 não pertence"),  # dois de V1
        ((1, 3, 5), (1, 2, 1), "3 representantes informados; esperado exatamente 4"),
        ((1, 3, 5, 7, 0), (1, 2, 1, 2, 3), "5 representantes"),
        ((1, 3, 99, 7), (1, 2, 1, 2), "cluster 3: representante 99 não é um vértice"),
        ((1, 3, -1, 7), (1, 2, 1, 2), "representante -1"),
        ((1, 3, 5, 7), (1, 2, 1), "3 cores para 4 representantes"),
        ((1, 3, 5, 7), (1, 2, 0, 2), "inteiros positivos"),
        ((1, 3, 5, 7), (1, 2, True, 2), "inteiros positivos"),
        ((1, 3, 5, 7), (1, 2, 1.0, 2), "inteiros positivos"),
    ],
)
def test_structural_errors(toy, selection, colors, match):
    report = validate(toy, Solution(selection, colors))
    assert not report.valid
    assert any(match in e for e in report.errors), report.errors


def test_wrong_claimed_value(toy):
    report = validate(toy, OPTIMAL, claimed_value=1)
    assert not report.valid
    assert any("valor declarado (1)" in e for e in report.errors)


def test_non_contiguous_colors_only_warn(toy):
    report = validate(toy, Solution((1, 3, 5, 7), (1, 3, 1, 3)), claimed_value=2)
    assert report.valid and not report.contiguous
    assert report.num_colors == 2
    assert len(report.warnings) == 1


def test_ensure_valid(toy):
    assert ensure_valid(toy, OPTIMAL).valid
    with pytest.raises(InvalidSolutionError) as exc:
        ensure_valid(toy, Solution((1, 3, 5, 7), (1, 1, 1, 2)))
    assert exc.value.report.conflicts == [(1, 3)]


def _proper_by_brute_force(inst, selection, colors):
    return all(
        colors[i] != colors[j]
        for i, j in itertools.combinations(range(len(selection)), 2)
        if inst.has_edge(selection[i], selection[j])
    )


def test_validator_agrees_with_brute_force_and_toy_optimum_is_2(toy):
    # Para toda seleção e toda coloração com até k cores, o validador deve
    # concordar com a checagem par-a-par; de quebra, confirma o ótimo da toy.
    best = None
    for selection in itertools.product(*toy.clusters):
        for c in range(1, toy.k + 1):
            for colors in itertools.product(range(1, c + 1), repeat=toy.k):
                report = validate(toy, Solution(selection, colors))
                assert report.valid == _proper_by_brute_force(toy, selection, colors)
                if report.valid and (best is None or report.num_colors < best):
                    best = report.num_colors
    assert best == toy.meta["optimum"] == 2
