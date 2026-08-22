import time

import pandas as pd

from app.analysis.dependency_analysis import _longest_chain, analyze_dependencies
from app.data.normalization import normalize


def test_longest_chain_terminates_quickly_on_a_dense_graph():
    """A near-complete directed graph is the pathological case for a
    naive 'every simple path' DFS -- branching_factor ** depth blows
    up combinatorially. This used to hang for minutes on graphs this
    small; the step-budget bound must keep it well under a second."""
    nodes = [f"M{i}" for i in range(40)]
    adjacency = {n: set(nodes) - {n} for n in nodes}  # every node points to every other node

    start = time.time()
    chain = _longest_chain(adjacency, max_depth=25)
    elapsed = time.time() - start

    assert elapsed < 5.0, f"longest-chain search took {elapsed:.1f}s on a dense graph -- budget cap isn't working"
    assert len(chain) > 0


def test_longest_chain_on_a_simple_line_is_exact():
    adjacency = {"A": {"B"}, "B": {"C"}, "C": {"D"}, "D": set()}
    chain = _longest_chain(adjacency)
    assert chain == ["A", "B", "C", "D"]


def test_inferred_dependency_analysis_on_dense_synthetic_export_does_not_hang():
    """End-to-end version of the same regression: a real export shaped
    with heavy cross-module references must analyze in bounded time."""
    modules = [f"MOD{i:02d}" for i in range(40)]
    rows = []
    for i in range(600):
        mod = modules[i % len(modules)]
        other = modules[(i * 7 + 3) % len(modules)]
        rows.append({
            "Line Item": f"Item {i}",
            "Formula": f"{other}.SomeItem + X[LOOKUP: Y]",
            "Cell Count": 1000,
            "Module": mod,
        })
    df = pd.DataFrame(rows)
    nd = normalize(df)

    from app.analysis.formula_analysis import build_feature_table
    feats = build_feature_table(nd)

    start = time.time()
    dep = analyze_dependencies(nd, feats)
    elapsed = time.time() - start

    assert elapsed < 10.0
    assert dep.available is True
    assert dep.source == "inferred"
