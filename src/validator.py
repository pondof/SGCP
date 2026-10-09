"""Validador formal de soluções do SGCP.

Toda solução produzida por qualquer algoritmo deve passar por ``validate`` (ou
``ensure_valid``) antes de ser aceita. O validador não reaproveita nada do
código dos algoritmos: tudo é recalculado a partir da instância.

Verificações:

1. Representatividade estrita: exatamente um vértice por cluster, com
   ``selection[i]`` pertencendo a V_i.
2. Cores bem formadas: uma cor (inteiro positivo) por representante.
3. Coloração própria: nenhuma aresta de G[S] tem as duas pontas com a mesma cor.
4. Custo: número de cores distintas, que deve coincidir com o valor declarado
   pelo algoritmo (se fornecido). Cores fora de 1..c geram apenas aviso.

Complexidade: O(n + k · n / w) operações de palavra, onde w é o tamanho da
palavra de máquina (os testes de conflito usam bitsets).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Instance, Solution, iter_bits

_MAX_LISTED_CONFLICTS = 10


@dataclass
class ValidationReport:
    """Resultado da validação.

    ``conflicts`` lista os pares (u, v), 0-indexados e com u < v, de vértices
    selecionados adjacentes com a mesma cor. As mensagens em ``errors`` e
    ``warnings`` usam a numeração 1-indexada exibida ao usuário.
    """

    valid: bool
    num_colors: int
    contiguous: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[tuple[int, int]] = field(default_factory=list)


class InvalidSolutionError(ValueError):
    """Levantada por ``ensure_valid`` quando a solução é rejeitada."""

    def __init__(self, report: ValidationReport) -> None:
        super().__init__("solução inválida: " + "; ".join(report.errors))
        self.report = report


def _is_color(c: object) -> bool:
    return isinstance(c, int) and not isinstance(c, bool) and c >= 1


def validate(
    inst: Instance, sol: Solution, claimed_value: int | None = None
) -> ValidationReport:
    """Valida ``sol`` contra ``inst``; nunca levanta exceção por solução ruim."""
    errors: list[str] = []
    warnings: list[str] = []
    selection, colors = sol.selection, sol.colors

    # 1. Representatividade estrita.
    if len(selection) != inst.k:
        errors.append(
            f"{len(selection)} representantes informados; esperado exatamente "
            f"{inst.k} (um por cluster)"
        )
    for i, v in enumerate(selection[: inst.k]):
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < inst.n:
            errors.append(f"cluster {i + 1}: representante {v!r} não é um vértice do grafo")
        elif v not in inst.clusters[i]:
            errors.append(f"cluster {i + 1}: vértice v_{v + 1} não pertence a este cluster")

    # 2. Cores bem formadas.
    if len(colors) != len(selection):
        errors.append(f"{len(colors)} cores para {len(selection)} representantes")
    bad_colors = [c for c in colors if not _is_color(c)]
    if bad_colors:
        errors.append(f"cores devem ser inteiros positivos; encontradas: {bad_colors[:5]!r}")

    distinct = set(colors)
    num_colors = len(distinct)
    contiguous = not bad_colors and distinct == set(range(1, num_colors + 1))

    # 3. Coloração própria (só faz sentido se a estrutura estiver correta).
    conflicts: list[tuple[int, int]] = []
    if not errors:
        class_mask: dict[int, int] = {}
        for v, c in zip(selection, colors):
            class_mask[c] = class_mask.get(c, 0) | (1 << v)
        for v, c in zip(selection, colors):
            for u in iter_bits(inst.adj[v] & class_mask[c]):
                if v < u:
                    conflicts.append((v, u))
        conflicts.sort()
        color_of = dict(zip(selection, colors))
        for u, v in conflicts[:_MAX_LISTED_CONFLICTS]:
            errors.append(f"aresta {{v_{u + 1}, v_{v + 1}}} com as duas pontas na Cor {color_of[u]}")
        if len(conflicts) > _MAX_LISTED_CONFLICTS:
            errors.append(f"... e mais {len(conflicts) - _MAX_LISTED_CONFLICTS} arestas em conflito")

    # 4. Custo.
    if claimed_value is not None and claimed_value != num_colors:
        errors.append(
            f"valor declarado ({claimed_value}) difere do número de cores distintas ({num_colors})"
        )
    if not bad_colors and not contiguous:
        warnings.append(
            f"cores não contíguas {sorted(distinct)}; custo considerado = "
            f"{num_colors} cores distintas"
        )

    return ValidationReport(
        valid=not errors,
        num_colors=num_colors,
        contiguous=contiguous,
        errors=errors,
        warnings=warnings,
        conflicts=conflicts,
    )


def ensure_valid(
    inst: Instance, sol: Solution, claimed_value: int | None = None
) -> ValidationReport:
    """Como ``validate``, mas levanta ``InvalidSolutionError`` se a solução for inválida."""
    report = validate(inst, sol, claimed_value)
    if not report.valid:
        raise InvalidSolutionError(report)
    return report
