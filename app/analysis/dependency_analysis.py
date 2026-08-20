# app/analysis/dependency_analysis.py
# ============================================================
# Master spec section 10. Two data paths:
#
#   1. FACT path -- when the export has a "Referenced By" column
#      (a real Anaplan field listing which other modules/line
#      items reference this one), edges are parsed directly from
#      it. confidence = Measured.
#
#   2. INFERENCE path -- when it doesn't, this falls back to the
#      original app.py's cross-reference text scan (does formula
#      text elsewhere mention this module/line item by name).
#      confidence = Estimated, and every UI surface must label it
#      "inferred from formula text references", never presented
#      as ground truth (section 25/26).
#
# If neither is possible the report says so explicitly rather than
# inventing a graph (section 10: "Not available in current dataset").
# ============================================================
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set

import pandas as pd

from app.data.normalization import NormalizedData
from app.analysis.formula_analysis import build_entity_pattern
from app.models.schemas import DependencyEdge

_REF_SPLIT = re.compile(r"',\s*'|\"\s*,\s*\"|,\s*(?=')")
_REF_MODULE = re.compile(r"^\s*'?([^'.]+)'?\.")


@dataclass
class DependencyReport:
    available: bool
    source: str  # "measured" | "inferred" | "unavailable"
    edges: List[DependencyEdge] = field(default_factory=list)
    module_in_degree: Dict[str, int] = field(default_factory=dict)
    module_out_degree: Dict[str, int] = field(default_factory=dict)
    top_bottleneck_modules: List[str] = field(default_factory=list)
    longest_chain_length: int = 0
    longest_chain_example: List[str] = field(default_factory=list)
    note: str = ""


def _parse_referenced_by(value: str) -> Set[str]:
    modules = set()
    if not value or str(value).strip().lower() in ("nan", ""):
        return modules
    for part in _REF_SPLIT.split(str(value)):
        m = _REF_MODULE.match(part.strip())
        if m:
            modules.add(m.group(1).strip())
    return modules


def _longest_chain(adjacency: Dict[str, Set[str]], max_depth: int = 25) -> List[str]:
    best: List[str] = []

    def dfs(node: str, path: List[str], visited: Set[str]):
        nonlocal best
        if len(path) > len(best):
            best = list(path)
        if len(path) >= max_depth:
            return
        for nxt in adjacency.get(node, ()):
            if nxt in visited:
                continue
            visited.add(nxt)
            path.append(nxt)
            dfs(nxt, path, visited)
            path.pop()
            visited.discard(nxt)

    for start in adjacency:
        dfs(start, [start], {start})
    return best


def analyze_dependencies(nd: NormalizedData, feats: pd.DataFrame, max_scan_rows: int = 4000) -> DependencyReport:
    ref_col = nd.optional_cols.get("referenced_by")

    edge_weight: Dict[tuple, int] = defaultdict(int)

    if ref_col:
        df = nd.df
        for module, ref_value in zip(df["_ModuleResolved_"], df[ref_col]):
            for referencing_module in _parse_referenced_by(ref_value):
                if referencing_module and referencing_module != module:
                    edge_weight[(referencing_module, module)] += 1
        source = "measured"
        note = "Dependency edges parsed directly from the export's Referenced By column."
    else:
        modules = feats["module"].astype(str)
        if len(feats) > max_scan_rows:
            return DependencyReport(
                available=False, source="unavailable",
                note=f"Not available in current dataset -- this export has no Referenced By column, and "
                     f"{len(feats):,} rows is too large for a live text-reference scan to stay responsive. "
                     "Filter the export by module and re-upload if you need an inferred dependency view.",
            )
        all_modules = sorted(modules.unique().tolist())[:200]
        module_pattern = build_entity_pattern([m.upper() for m in all_modules])
        if module_pattern is None:
            return DependencyReport(available=False, source="unavailable",
                                     note="Not available in current dataset -- no module names to cross-reference.")
        formula_upper = feats["upper"]
        for module, formula in zip(modules, formula_upper):
            matches = set(module_pattern.findall(formula))
            matches.discard(module.upper())
            for m in matches:
                original = next((om for om in all_modules if om.upper() == m), m)
                if original != module:
                    edge_weight[(module, original)] += 1
        source = "inferred"
        note = ("Dependency edges INFERRED from formula text -- a module is linked to another whenever a "
                "formula in it mentions the other module's name. This is an approximation, not real Anaplan "
                "dependency metadata; treat directionality and completeness as indicative only.")

    if not edge_weight:
        return DependencyReport(available=False, source=source,
                                 note=note + " No cross-module references were detected in this export.")

    edges = [DependencyEdge(from_module=a, to_module=b, weight=w) for (a, b), w in edge_weight.items()]
    edges.sort(key=lambda e: e.weight, reverse=True)

    in_degree: Dict[str, int] = defaultdict(int)
    out_degree: Dict[str, int] = defaultdict(int)
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    for e in edges:
        out_degree[e.from_module] += 1
        in_degree[e.to_module] += 1
        adjacency[e.from_module].add(e.to_module)

    bottlenecks = sorted(in_degree.keys(), key=lambda m: in_degree[m], reverse=True)[:5]
    chain = _longest_chain(adjacency)

    return DependencyReport(
        available=True, source=source, edges=edges[:500],
        module_in_degree=dict(in_degree), module_out_degree=dict(out_degree),
        top_bottleneck_modules=bottlenecks,
        longest_chain_length=max(0, len(chain) - 1), longest_chain_example=chain,
        note=note,
    )
