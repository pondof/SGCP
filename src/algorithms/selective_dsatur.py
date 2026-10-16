"""Heurística construtiva DSATUR Seletivo para o SGCP.

Adapta a regra de saturação do DSATUR (Brélaz, 1979) à escolha de
representantes, no espírito das heurísticas *onestep* de Li & Simha (2000):
seleção e coloração acontecem juntas, um cluster por iteração.

Para cada vértice v de um cluster ainda aberto, mantém-se:

- ``forb[v]``: bitset das cores já usadas por representantes vizinhos de v.
  A saturação é ``sat(v) = |forb[v]|`` e a menor cor livre é ``b(v)``.
- ``d(v)``: grau dinâmico, o número de vizinhos de v em *outros* clusters
  ainda abertos (quanto v ainda pode atrapalhar os clusters restantes).

A cada iteração:

1. Em cada cluster aberto V_i, o candidato é o vértice de menor
   ``(sat, d, índice)``: o que fica menos restringido e menos restringe.
2. Entre os clusters abertos, fecha-se o de candidato mais saturado; empates
   vão para o maior ``d`` e depois para o menor índice do cluster. Como no
   DSATUR, o cluster mais difícil é tratado enquanto ainda há folga.
3. O candidato recebe a menor cor livre (*first fit*). O cluster é fechado e
   ``forb``/``d`` dos vértices abertos são atualizados.

Escolher o candidato de menor saturação garante que uma cor nova só é aberta
quando nenhum vértice do cluster cabe em uma cor existente: se
``sat(v) < q`` (com q cores em uso), alguma cor de 1..q está livre para v.

Complexidade: O(n·k + m) operações sobre bitsets. São k iterações, cada uma
varre os vértices abertos (O(n)); as atualizações de ``forb`` e ``d`` tocam
cada aresta no máximo duas vezes ao longo de toda a execução (O(m)).

Limite superior: o número de cores é no máximo
``1 + max_i min_{v ∈ V_i} δ(v)``, onde δ(v) é o número de clusters
(distintos do de v) com algum vizinho de v; ver ``color_upper_bound``. O
SGCP generaliza a coloração clássica (clusters unitários), então não existe
aproximação com razão n^(1-ε) para nenhum ε > 0, a menos que P = NP
(Zuckerman, 2007); a heurística não tem garantia de razão constante.
"""

from __future__ import annotations

from ..model import Instance, Solution, iter_bits


def _lowest_free_color(forb: int) -> int:
    """Menor cor c >= 1 cujo bit c não está em ``forb`` (o bit 0 não é usado)."""
    x = forb | 1
    return (~x & (x + 1)).bit_length() - 1


def selective_dsatur(inst: Instance) -> Solution:
    """Constrói uma solução do SGCP com o DSATUR Seletivo (determinístico)."""
    n, adj, clusters = inst.n, inst.adj, inst.clusters
    cluster_mask, cluster_of = inst.cluster_mask, inst.cluster_of

    forb = [0] * n
    open_mask = (1 << n) - 1
    deg = [(adj[v] & ~cluster_mask[cluster_of[v]]).bit_count() for v in range(n)]
    open_clusters = set(range(inst.k))
    selection = [-1] * inst.k
    colors = [0] * inst.k

    while open_clusters:
        best_key = None
        for i in open_clusters:
            # Candidato do cluster: menor (sat, d, índice).
            v = min(clusters[i], key=lambda u: (forb[u].bit_count(), deg[u], u))
            # Cluster: maior saturação, depois maior d, depois menor índice.
            key = (-forb[v].bit_count(), -deg[v], i)
            if best_key is None or key < best_key:
                best_key, best_cluster, best_vertex = key, i, v

        i, v = best_cluster, best_vertex
        c = _lowest_free_color(forb[v])
        selection[i], colors[i] = v, c
        open_clusters.remove(i)

        # Fecha o cluster: seus vértices deixam de contar no grau dinâmico.
        open_mask &= ~cluster_mask[i]
        for u in clusters[i]:
            for w in iter_bits(adj[u] & open_mask):
                deg[w] -= 1
        # A cor c fica proibida para os vizinhos abertos do representante.
        bit = 1 << c
        for w in iter_bits(adj[v] & open_mask):
            forb[w] |= bit

    return Solution(tuple(selection), tuple(colors))


def color_upper_bound(inst: Instance) -> int:
    """Limite ``1 + max_i min_{v ∈ V_i} δ(v)`` para as cores do DSATUR Seletivo.

    δ(v) é o número de clusters, distintos do de v, que contêm vizinhos de v.
    Quando V_i é fechado, o candidato escolhido tem saturação mínima em V_i;
    cada cor proibida para v vem de um representante vizinho, e há no máximo
    um representante por cluster, então sat(v) <= δ(v) e a cor atribuída é
    no máximo sat(v) + 1 <= min_{u ∈ V_i} δ(u) + 1.
    """
    cluster_of, cluster_mask = inst.cluster_of, inst.cluster_mask
    worst = 0
    for cluster in inst.clusters:
        best = min(
            sum(1 for j, mask in enumerate(cluster_mask) if j != cluster_of[v] and inst.adj[v] & mask)
            for v in cluster
        )
        worst = max(worst, best)
    return 1 + worst
