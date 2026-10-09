import pytest

from src.instance_io import (
    InstanceFormatError,
    format_text,
    load_instance,
    parse_json,
    parse_text,
    save_instance,
)
from src.model import Instance


def test_load_toy(toy):
    assert (toy.n, toy.m, toy.k) == (8, 12, 4)
    assert toy.name == "toy"
    assert toy.meta == {"optimum": 2}  # comentários livres após o bloco não viram meta
    assert toy.clusters == ((0, 1), (2, 3), (4, 5), (6, 7))
    assert toy.has_edge(0, 2) and toy.has_edge(2, 7)  # "e 1 3" e "e 3 8"


def test_round_trip_txt_json_txt(toy, tmp_path):
    save_instance(toy, tmp_path / "a.json")
    from_json = load_instance(tmp_path / "a.json")
    save_instance(from_json, tmp_path / "b.txt")
    back = load_instance(tmp_path / "b.txt")
    for inst in (from_json, back):
        assert inst == toy
        assert inst.name == toy.name and inst.meta == toy.meta
    assert (tmp_path / "b.txt").read_text() == format_text(toy)


def test_meta_types_survive_text_round_trip():
    meta = {"seed": 42, "p": 0.3, "balanced": True, "kind": "perfect", "tag": "42"}
    inst = Instance.from_edges(2, [[0], [1]], [(0, 1)], name="m", meta=meta)
    back = parse_text(format_text(inst))
    assert back.meta == meta
    assert type(back.meta["tag"]) is str


def test_name_falls_back_to_file_stem(tmp_path):
    path = tmp_path / "sem_nome.txt"
    path.write_text("p edge 1 0 1\nc 1 1\n")
    assert load_instance(path).name == "sem_nome"


def test_unsupported_extension(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("")
    with pytest.raises(InstanceFormatError, match="extensão"):
        load_instance(path)


VALID = "p edge 3 1 2\nc 1 1 2\nc 2 3\ne 1 3\n"


def test_valid_reference_text_parses():
    inst = parse_text(VALID)
    assert (inst.n, inst.m, inst.k) == (3, 1, 2)


@pytest.mark.parametrize(
    "text, match",
    [
        ("c 1 1\n", "linha 1: linha 'c' antes do cabeçalho"),
        ("# só comentário\n", "não encontrado"),
        ("p edge 3 1\n", "linha 1: cabeçalho deve ser"),
        ("p col 3 1 2\n", "linha 1: cabeçalho deve ser"),
        ("p edge 0 0 1\n", "valores inválidos"),
        (VALID + "p edge 3 1 2\n", "linha 5: cabeçalho 'p' repetido"),
        ("p edge 3 1 2\nc 3 1 2\nc 2 3\ne 1 3\n", "linha 2: id de cluster 3"),
        ("p edge 3 1 2\nc 1 1 2\nc 1 3\ne 1 3\n", "linha 3: cluster 1 declarado mais de uma vez"),
        ("p edge 3 1 2\nc 1\nc 2 1 2 3\ne 1 3\n", "linha 2: cluster 1 está vazio"),
        ("p edge 3 1 2\nc 1 1 4\nc 2 3\ne 1 3\n", "linha 2: vértice 4 fora do intervalo"),
        ("p edge 3 1 2\nc 1 1 2\nc 2 2 3\ne 1 3\n", "linha 3: vértice 2 já pertence ao cluster 1"),
        ("p edge 3 1 2\nc 1 1\nc 2 3\ne 1 3\n", r"fora de qualquer cluster: \[2\]"),
        ("p edge 3 1 2\nc 1 1 2 3\ne 1 3\n", r"ausentes: \[2\]"),
        ("p edge 3 2 2\nc 1 1 2\nc 2 3\ne 1 3\n", "m = 2, mas há 1"),
        (VALID + "e 1 3\n", "linha 5: aresta {1, 3} repetida"),
        (VALID + "e 3 1\n", "linha 5: aresta {3, 1} repetida"),
        ("p edge 3 1 2\nc 1 1 2\nc 2 3\ne 2 2\n", "linha 4: laço"),
        ("p edge 3 1 2\nc 1 1 2\nc 2 3\ne 1\n", "linha 4: aresta deve ser"),
        ("p edge 3 1 2\nc 1 1 2\nc 2 3\ne 1 x\n", "linha 4: esperado inteiro"),
        (VALID + "x 1 2\n", "linha 5: tipo de linha desconhecido"),
    ],
)
def test_rejects_malformed_text(text, match):
    with pytest.raises(InstanceFormatError, match=match):
        parse_text(text)


JSON_OK = '{"n": 3, "k": 2, "clusters": [[1, 2], [3]], "edges": [[1, 3]]}'


def test_valid_reference_json_parses():
    inst = parse_json(JSON_OK, default_name="d")
    assert (inst.n, inst.m, inst.k, inst.name) == (3, 1, 2, "d")


@pytest.mark.parametrize(
    "text, match",
    [
        ("{not json", "JSON inválido"),
        ("[1, 2]", "deve ser um objeto"),
        ('{"k": 1, "clusters": [[1]], "edges": []}', "'n' ausente"),
        ('{"n": true, "k": 1, "clusters": [[1]], "edges": []}', "'n' deveria ser int"),
        ('{"n": 3, "k": 3, "clusters": [[1, 2], [3]], "edges": []}', "k = 3, mas"),
        ('{"n": 3, "k": 2, "clusters": [[1, 2], [3]], "edges": [[1, 4]]}', r"edges\[0\]: vértice 4"),
        ('{"n": 3, "k": 2, "clusters": [[1, 2], [3]], "edges": [[1]]}', r"edges\[0\]: esperados 2"),
        ('{"n": 3, "k": 2, "clusters": [[1, "2"], [3]], "edges": []}', r"clusters\[0\]: esperada lista"),
        ('{"n": 3, "m": 5, "k": 2, "clusters": [[1, 2], [3]], "edges": []}', "m = 5"),
        ('{"format": "outro", "n": 1, "k": 1, "clusters": [[1]], "edges": []}', "não suportado"),
    ],
)
def test_rejects_malformed_json(text, match):
    with pytest.raises(InstanceFormatError, match=match):
        parse_json(text)
