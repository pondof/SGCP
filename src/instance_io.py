"""Leitura e escrita de instâncias do SGCP (texto ``.txt`` e JSON ``.json``).

Formato texto (``sgcp_dimacs``), com vértices e clusters indexados a partir de 1::

    # format: sgcp_dimacs
    # name: toy
    # seed: 42
    p edge <n> <m> <k>
    c <cluster_id> <v1> <v2> ...
    e <u> <v>

- Linhas iniciadas por ``#`` são comentários. O bloco contíguo de linhas
  ``# chave: valor`` no topo do arquivo contém os metadados (``name`` vira o
  nome da instância; os demais vão para ``meta``, interpretados como JSON
  quando possível — ``42`` vira ``int``, ``true`` vira ``bool``). A primeira
  linha de outro tipo encerra o bloco; comentários seguintes são livres.
- Ao contrário do DIMACS clássico, ``c`` aqui declara um cluster, não um
  comentário.

Formato JSON (``sgcp_json``)::

    {"format": "sgcp_json", "name": ..., "n": ..., "m": ..., "k": ...,
     "meta": {...}, "clusters": [[1, 2], ...], "edges": [[1, 3], ...]}

A leitura é estrita: qualquer inconsistência gera ``InstanceFormatError``
indicando a linha (texto) ou o campo (JSON) do problema.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .model import Instance, InstanceError

TEXT_FORMAT = "sgcp_dimacs"
JSON_FORMAT = "sgcp_json"

_META_LINE = re.compile(r"#\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$")


class InstanceFormatError(InstanceError):
    """Arquivo de instância malformado."""


def load_instance(path: str | os.PathLike[str]) -> Instance:
    """Lê uma instância, escolhendo o formato pela extensão (.txt ou .json)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return parse_text(text, default_name=path.stem)
    if suffix == ".json":
        return parse_json(text, default_name=path.stem)
    raise InstanceFormatError(f"{path}: extensão não suportada (use .txt ou .json)")


def save_instance(inst: Instance, path: str | os.PathLike[str]) -> None:
    """Grava uma instância, escolhendo o formato pela extensão (.txt ou .json)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        content = format_text(inst)
    elif suffix == ".json":
        content = format_json(inst)
    else:
        raise InstanceFormatError(f"{path}: extensão não suportada (use .txt ou .json)")
    path.write_text(content, encoding="utf-8")


class _Builder:
    """Acumula clusters e arestas (1-indexados) checando cada item ao chegar."""

    def __init__(self, n: int, k: int) -> None:
        self.n, self.k = n, k
        self.clusters: dict[int, list[int]] = {}
        self.owner: dict[int, int] = {}
        self.edges: list[tuple[int, int]] = []
        self.seen_edges: set[tuple[int, int]] = set()

    def _vertex(self, v: int, where: str) -> int:
        if not 1 <= v <= self.n:
            raise InstanceFormatError(f"{where}: vértice {v} fora do intervalo [1, {self.n}]")
        return v

    def add_cluster(self, cid: int, vertices: list[int], where: str) -> None:
        if not 1 <= cid <= self.k:
            raise InstanceFormatError(f"{where}: id de cluster {cid} fora do intervalo [1, {self.k}]")
        if cid in self.clusters:
            raise InstanceFormatError(f"{where}: cluster {cid} declarado mais de uma vez")
        if not vertices:
            raise InstanceFormatError(f"{where}: cluster {cid} está vazio")
        for v in vertices:
            self._vertex(v, where)
            if v in self.owner:
                raise InstanceFormatError(
                    f"{where}: vértice {v} já pertence ao cluster {self.owner[v]}"
                )
            self.owner[v] = cid
        self.clusters[cid] = vertices

    def add_edge(self, u: int, v: int, where: str) -> None:
        self._vertex(u, where)
        self._vertex(v, where)
        if u == v:
            raise InstanceFormatError(f"{where}: laço no vértice {u}")
        key = (min(u, v), max(u, v))
        if key in self.seen_edges:
            raise InstanceFormatError(f"{where}: aresta {{{u}, {v}}} repetida")
        self.seen_edges.add(key)
        self.edges.append((u, v))

    def build(self, m: int | None, name: str, meta: dict[str, Any]) -> Instance:
        if m is not None and len(self.edges) != m:
            raise InstanceFormatError(f"cabeçalho declara m = {m}, mas há {len(self.edges)} arestas")
        missing = [i for i in range(1, self.k + 1) if i not in self.clusters]
        if missing:
            raise InstanceFormatError(f"clusters declarados (k = {self.k}) mas ausentes: {missing}")
        uncovered = [v for v in range(1, self.n + 1) if v not in self.owner]
        if uncovered:
            shown = uncovered[:10]
            more = f" (+{len(uncovered) - 10})" if len(uncovered) > 10 else ""
            raise InstanceFormatError(f"vértices fora de qualquer cluster: {shown}{more}")
        return Instance.from_edges(
            n=self.n,
            clusters=[[v - 1 for v in self.clusters[i]] for i in range(1, self.k + 1)],
            edges=[(u - 1, v - 1) for u, v in self.edges],
            name=name,
            meta=meta,
        )


def _ints(tokens: list[str], where: str) -> list[int]:
    try:
        return [int(t) for t in tokens]
    except ValueError:
        raise InstanceFormatError(f"{where}: esperado inteiro, encontrado {tokens!r}") from None


def _parse_meta_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_text(text: str, default_name: str = "") -> Instance:
    """Interpreta o conteúdo de um arquivo no formato ``sgcp_dimacs``."""
    name, meta = default_name, {}
    builder: _Builder | None = None
    m = None
    in_meta_block = True
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        where = f"linha {lineno}"
        match = _META_LINE.fullmatch(line) if in_meta_block else None
        if match:
            key, value = match.groups()
            if key == "name":
                name = value or default_name
            elif key != "format":
                meta[key] = _parse_meta_value(value)
            continue
        in_meta_block = False
        if not line or line.startswith("#"):
            continue

        kind, *rest = line.split()
        if kind == "p":
            if builder is not None:
                raise InstanceFormatError(f"{where}: cabeçalho 'p' repetido")
            if len(rest) != 4 or rest[0] != "edge":
                raise InstanceFormatError(f"{where}: cabeçalho deve ser 'p edge <n> <m> <k>'")
            n, m, k = _ints(rest[1:], where)
            if n < 1 or m < 0 or k < 1:
                raise InstanceFormatError(f"{where}: valores inválidos no cabeçalho (n={n}, m={m}, k={k})")
            builder = _Builder(n, k)
        elif builder is None:
            raise InstanceFormatError(f"{where}: linha '{kind}' antes do cabeçalho 'p edge ...'")
        elif kind == "c":
            values = _ints(rest, where)
            if not values:
                raise InstanceFormatError(f"{where}: linha 'c' sem id de cluster")
            builder.add_cluster(values[0], values[1:], where)
        elif kind == "e":
            if len(rest) != 2:
                raise InstanceFormatError(f"{where}: aresta deve ser 'e <u> <v>'")
            u, v = _ints(rest, where)
            builder.add_edge(u, v, where)
        else:
            raise InstanceFormatError(f"{where}: tipo de linha desconhecido '{kind}'")

    if builder is None:
        raise InstanceFormatError("cabeçalho 'p edge <n> <m> <k>' não encontrado")
    return builder.build(m, name, meta)


def format_text(inst: Instance) -> str:
    """Serializa a instância no formato ``sgcp_dimacs``."""
    lines = [f"# format: {TEXT_FORMAT}"]
    if inst.name:
        lines.append(f"# name: {inst.name}")
    for key, value in inst.meta.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise InstanceFormatError(f"chave de metadado inválida para o formato texto: {key!r}")
        # Strings que seriam relidas como outro tipo (ex.: "42") vão entre aspas.
        if isinstance(value, str) and _parse_meta_value(value) == value:
            rendered = value
        else:
            rendered = json.dumps(value, ensure_ascii=False)
        if "\n" in rendered:
            raise InstanceFormatError(f"metadado {key!r} contém quebra de linha")
        lines.append(f"# {key}: {rendered}")
    lines.append(f"p edge {inst.n} {inst.m} {inst.k}")
    for i, cluster in enumerate(inst.clusters, start=1):
        lines.append(f"c {i} " + " ".join(str(v + 1) for v in cluster))
    lines.extend(f"e {u + 1} {v + 1}" for u, v in inst.edges())
    return "\n".join(lines) + "\n"


def _field(obj: dict[str, Any], key: str, kind: type) -> Any:
    if key not in obj:
        raise InstanceFormatError(f"campo obrigatório '{key}' ausente")
    value = obj[key]
    if not isinstance(value, kind) or isinstance(value, bool):
        raise InstanceFormatError(f"campo '{key}' deveria ser {kind.__name__}")
    return value


def _int_list(value: Any, where: str, length: int | None = None) -> list[int]:
    if not isinstance(value, list) or not all(
        isinstance(x, int) and not isinstance(x, bool) for x in value
    ):
        raise InstanceFormatError(f"{where}: esperada lista de inteiros")
    if length is not None and len(value) != length:
        raise InstanceFormatError(f"{where}: esperados {length} inteiros, encontrados {len(value)}")
    return value


def parse_json(text: str, default_name: str = "") -> Instance:
    """Interpreta o conteúdo de um arquivo no formato ``sgcp_json``."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InstanceFormatError(f"JSON inválido: {exc}") from None
    if not isinstance(obj, dict):
        raise InstanceFormatError("o documento JSON deve ser um objeto")
    if obj.get("format", JSON_FORMAT) != JSON_FORMAT:
        raise InstanceFormatError(f"formato '{obj['format']}' não suportado (esperado '{JSON_FORMAT}')")

    n = _field(obj, "n", int)
    k = _field(obj, "k", int)
    clusters = _field(obj, "clusters", list)
    edges = _field(obj, "edges", list)
    m = _field(obj, "m", int) if "m" in obj else None
    meta = _field(obj, "meta", dict) if "meta" in obj else {}
    name = (_field(obj, "name", str) if "name" in obj else "") or default_name
    if n < 1 or k < 1:
        raise InstanceFormatError(f"valores inválidos (n={n}, k={k})")
    if len(clusters) != k:
        raise InstanceFormatError(f"k = {k}, mas 'clusters' tem {len(clusters)} entradas")

    builder = _Builder(n, k)
    for i, cluster in enumerate(clusters):
        builder.add_cluster(i + 1, _int_list(cluster, f"clusters[{i}]"), f"clusters[{i}]")
    for j, edge in enumerate(edges):
        u, v = _int_list(edge, f"edges[{j}]", length=2)
        builder.add_edge(u, v, f"edges[{j}]")
    return builder.build(m, name, meta)


def format_json(inst: Instance) -> str:
    """Serializa a instância no formato ``sgcp_json``.

    Cada campo de topo fica em uma linha; listas ficam compactas para que
    instâncias com milhões de arestas continuem com tamanho razoável.
    """
    fields = {
        "format": JSON_FORMAT,
        "name": inst.name,
        "n": inst.n,
        "m": inst.m,
        "k": inst.k,
        "meta": inst.meta,
        "clusters": [[v + 1 for v in c] for c in inst.clusters],
        "edges": [[u + 1, v + 1] for u, v in inst.edges()],
    }
    body = ",\n".join(
        f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
        for key, value in fields.items()
    )
    return "{\n" + body + "\n}\n"
