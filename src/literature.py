"""Importa instâncias da literatura do SGCP (também chamado *Partition Coloring Problem*).

Fonte: repositório de A. Santini, "Solvers for the Selective Graph Colouring
Problem and generalisations" (GPL-3.0), que distribui as instâncias usadas por
Furini, Malaguti & Santini (2018). O download é fixado em um commit para que a
importação seja reproduzível.

Conjuntos: ``random`` e ``ring`` (Frota et al., 2010), ``nsfnet`` (Li & Simha,
2000) e ``big-random`` (n = 1000; ~198 MB, importado só sob demanda).

Formato original (vértices 0-indexados)::

    n
    m
    k
    u v          (m linhas, uma aresta por linha)
    v1 v2 ...    (k linhas, um cluster por linha)

A conversão é estrita: contagens divergentes, vértice fora do intervalo, laço,
aresta repetida, cluster vazio, vértice em dois clusters ou vértice sem cluster
geram ``InstanceFormatError``, com a linha do arquivo original. Arestas
internas a um cluster são mantidas (o modelo as aceita).

Uso::

    python -m src.literature --sets random nsfnet ring
    python -m src.literature --sets big-random
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.request
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .instance_io import InstanceFormatError, format_text, parse_text
from .model import Instance

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "instances" / "literature"

REPO = "alberto-santini/selective-graph-colouring"
COMMIT = "731f99db29d5d20de9dc83ffada9f418b93100cf"
REPO_URL = f"https://github.com/{REPO}"
SETS = ("random", "nsfnet", "ring", "big-random")
DEFAULT_SETS = ("random", "nsfnet", "ring")
REFERENCE = "Furini, Malaguti & Santini (2018)"
MANIFEST_FIELDS = ("path", "set", "n", "m", "k", "density", "max_cluster", "source_file", "sha256")

_SAFE_NAME = re.compile(r"[A-Za-z0-9_.-]+\.txt")


def parse_santini(text: str, name: str = "", meta: dict[str, Any] | None = None) -> Instance:
    """Interpreta um arquivo no formato de Santini (ver docstring do módulo)."""
    lines = [(i, line.split()) for i, line in enumerate(text.splitlines(), start=1)]
    lines = [(i, tokens) for i, tokens in lines if tokens]

    def ints(lineno: int, tokens: list[str]) -> list[int]:
        try:
            return [int(t) for t in tokens]
        except ValueError:
            raise InstanceFormatError(f"linha {lineno}: esperado inteiro, encontrado {tokens!r}") from None

    if len(lines) < 3 or any(len(tokens) != 1 for _, tokens in lines[:3]):
        raise InstanceFormatError("cabeçalho deve ter n, m e k, um por linha")
    n, m, k = (ints(i, tokens)[0] for i, tokens in lines[:3])
    if n < 1 or m < 0 or k < 1:
        raise InstanceFormatError(f"valores inválidos no cabeçalho (n={n}, m={m}, k={k})")
    if len(lines) != 3 + m + k:
        raise InstanceFormatError(
            f"esperadas {m} arestas e {k} linhas de cluster após o cabeçalho; "
            f"encontradas {len(lines) - 3} linhas"
        )

    def vertex(v: int, lineno: int) -> int:
        if not 0 <= v < n:
            raise InstanceFormatError(f"linha {lineno}: vértice {v} fora do intervalo [0, {n})")
        return v

    edges, seen = [], set()
    for lineno, tokens in lines[3 : 3 + m]:
        if len(tokens) != 2:
            raise InstanceFormatError(f"linha {lineno}: aresta deve ser 'u v'")
        u, v = (vertex(x, lineno) for x in ints(lineno, tokens))
        if u == v:
            raise InstanceFormatError(f"linha {lineno}: laço no vértice {u}")
        key = (min(u, v), max(u, v))
        if key in seen:
            raise InstanceFormatError(f"linha {lineno}: aresta {{{u}, {v}}} repetida")
        seen.add(key)
        edges.append((u, v))

    clusters, owner = [], {}
    for idx, (lineno, tokens) in enumerate(lines[3 + m :]):
        cluster = [vertex(v, lineno) for v in ints(lineno, tokens)]
        for v in cluster:
            if v in owner:
                raise InstanceFormatError(
                    f"linha {lineno}: vértice {v} já pertence ao cluster {owner[v]}"
                )
            owner[v] = idx
        clusters.append(cluster)
    missing = [v for v in range(n) if v not in owner]
    if missing:
        raise InstanceFormatError(f"vértices fora de qualquer cluster: {missing[:10]}")
    return Instance.from_edges(n, clusters, edges, name=name, meta=meta)


def _fetch(url: str, timeout: float = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "sgcp-literature-importer"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def list_source_files(sets: Sequence[str]) -> dict[str, list[str]]:
    """Caminhos (no repositório de origem) dos arquivos de cada conjunto."""
    url = f"https://api.github.com/repos/{REPO}/git/trees/{COMMIT}?recursive=1"
    tree = json.loads(_fetch(url))["tree"]
    found: dict[str, list[str]] = {s: [] for s in sets}
    for item in tree:
        parts = item["path"].split("/")
        if (item["type"] == "blob" and len(parts) == 4 and parts[:2] == ["base-sgcp", "instances"]
                and parts[2] in found):
            if not _SAFE_NAME.fullmatch(parts[3]):
                raise InstanceFormatError(f"nome de arquivo inesperado na origem: {item['path']!r}")
            found[parts[2]].append(item["path"])
    for s, paths in found.items():
        if not paths:
            raise InstanceFormatError(f"conjunto '{s}' não encontrado no commit {COMMIT}")
        paths.sort()
    return found


def convert(set_name: str, source_path: str, text: str) -> Instance:
    stem = Path(source_path).stem
    meta = {
        "source_set": set_name,
        "source_file": source_path,
        "source_repo": REPO_URL,
        "source_commit": COMMIT,
        "reference": REFERENCE,
    }
    return parse_santini(text, name=stem, meta=meta)


def import_sets(
    sets: Sequence[str] = DEFAULT_SETS,
    out_dir: Path = OUT_DIR,
    *,
    workers: int = 8,
    log: Callable[[str], None] = print,
) -> list[dict[str, object]]:
    """Baixa, converte e grava os conjuntos pedidos; atualiza ``manifest.csv``."""
    sources = list_source_files(sets)
    rows: list[dict[str, object]] = []
    for set_name, paths in sources.items():
        start = time.perf_counter()
        (out_dir / set_name).mkdir(parents=True, exist_ok=True)
        raw_url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/"
        with ThreadPoolExecutor(workers) as pool:
            texts = pool.map(lambda p: _fetch(raw_url + p).decode("ascii"), paths)
            for source_path, text in zip(paths, texts):
                try:
                    inst = convert(set_name, source_path, text)
                except InstanceFormatError as exc:
                    raise InstanceFormatError(f"{source_path}: {exc}") from None
                content = format_text(inst)
                if parse_text(content) != inst:  # confere a ida e volta
                    raise InstanceFormatError(f"{source_path}: conversão não é reversível")
                rel = f"{set_name}/{inst.name}.txt"
                (out_dir / rel).write_text(content, encoding="utf-8")
                rows.append({
                    "path": rel, "set": set_name, "n": inst.n, "m": inst.m, "k": inst.k,
                    "density": round(inst.density, 4), "max_cluster": max(inst.cluster_sizes()),
                    "source_file": source_path,
                    "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                })
        log(f"{set_name:>10}: {len(paths)} instâncias em {time.perf_counter() - start:.1f} s")
    _update_manifest(out_dir / "manifest.csv", rows)
    return rows


def _update_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    merged: dict[str, dict[str, object]] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            merged = {row["path"]: row for row in csv.DictReader(fh)}
    merged.update((str(row["path"]), row) for row in rows)
    set_order = {s: i for i, s in enumerate(SETS)}
    ordered = sorted(merged.values(), key=lambda r: (set_order.get(str(r["set"]), 99), str(r["path"])))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m src.literature",
        description="Importa instâncias da literatura (Furini, Malaguti & Santini, 2018).",
    )
    p.add_argument("--sets", nargs="+", choices=SETS, default=list(DEFAULT_SETS))
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = p.parse_args(argv)
    rows = import_sets(args.sets, args.out_dir)
    print(f"{len(rows)} instâncias em {args.out_dir}; manifesto: {args.out_dir / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
