import csv
from pathlib import Path

import pytest

from src.instance_io import InstanceFormatError, format_text, load_instance, parse_text
from src.literature import convert, parse_santini

ROOT = Path(__file__).resolve().parents[1]

# Conteúdo de base-sgcp/instances/ring/ring_n10p0.1s1.txt (repositório de Santini).
RING = """8
11
4
0 2
0 4
0 6
1 3
1 5
1 7
2 4
3 5
3 7
4 6
5 7
0 1
2 3
4 5
6 7
"""


def test_parse_ring_sample():
    inst = parse_santini(RING, name="ring_n10p0.1s1")
    assert (inst.n, inst.m, inst.k) == (8, 11, 4)
    assert inst.clusters == ((0, 1), (2, 3), (4, 5), (6, 7))
    assert inst.has_edge(0, 2) and inst.has_edge(5, 7) and not inst.has_edge(0, 1)
    assert inst.name == "ring_n10p0.1s1"


def test_intra_cluster_edges_and_singletons_are_kept():
    inst = parse_santini("3\n2\n2\n0 1\n1 2\n0 1\n2\n")
    assert inst.has_edge(0, 1) and inst.clusters == ((0, 1), (2,))


def test_convert_round_trip_and_meta():
    inst = convert("ring", "base-sgcp/instances/ring/ring_n10p0.1s1.txt", RING)
    assert inst.meta["source_set"] == "ring" and inst.meta["source_commit"]
    back = parse_text(format_text(inst))
    assert back == inst and back.meta == inst.meta and back.name == "ring_n10p0.1s1"


@pytest.mark.parametrize(
    "text, match",
    [
        ("3\n1\n", "cabeçalho"),
        ("3 1\n1\n2\n0 1\n0 1\n2\n", "cabeçalho"),
        ("0\n0\n1\n0\n", "valores inválidos"),
        ("3\n2\n2\n0 1\n0 1\n2\n", "esperadas 2 arestas"),
        ("3\n1\n2\n0 1\n0 1\n", "esperadas 1 arestas"),
        ("3\n1\n2\n0 x\n0 1\n2\n", "linha 4: esperado inteiro"),
        ("3\n1\n2\n0 1 2\n0 1\n2\n", "linha 4: aresta deve ser"),
        ("3\n1\n2\n0 3\n0 1\n2\n", "linha 4: vértice 3 fora do intervalo"),
        ("3\n1\n2\n1 1\n0 1\n2\n", "linha 4: laço"),
        ("3\n2\n2\n0 1\n1 0\n0 1\n2\n", "linha 5: aresta {1, 0} repetida"),
        ("3\n1\n2\n0 1\n0 1\n1 2\n", "linha 6: vértice 1 já pertence ao cluster 0"),
        ("3\n1\n2\n0 1\n0\n2\n", r"fora de qualquer cluster: \[1\]"),
    ],
)
def test_rejects_malformed(text, match):
    with pytest.raises(InstanceFormatError, match=match):
        parse_santini(text)


def test_committed_literature_matches_manifest():
    manifest = ROOT / "instances" / "literature" / "manifest.csv"
    if not manifest.exists():
        pytest.skip("instâncias da literatura não importadas (rode `make literature`)")
    with manifest.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["set"] in ("random", "nsfnet")]
    for row in rows:
        inst = load_instance(manifest.parent / row["path"])
        assert (inst.n, inst.m, inst.k) == (int(row["n"]), int(row["m"]), int(row["k"]))
