# app/analysis/size_analysis.py
# ============================================================
# "Where is the space going" -- master spec section 5 + 6.
# Migrated from the original app.py mod_sum logic, extended with
# a Pareto/status banding and a "primary lever" recommendation
# per module, generalized from the real Tridant Module Sizing
# report (rank / % of model / cumulative % / avg cells per line
# item / Status / Primary Lever).
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from app.data.normalization import NormalizedData
from app.data.field_parsers import classify_module_type

CELLS_PER_GB = 132_000_000.0  # matches the original app.py's Size(GB) conversion


@dataclass
class ModuleSizeRow:
    rank: int
    module: str
    cell_count: float
    pct_of_model: float
    cumulative_pct: float
    line_items: int
    avg_cells_per_item: float
    module_type: str
    status: str
    primary_lever: str


@dataclass
class SizeSummary:
    total_cells: float
    modules_count: int
    line_items_count: int
    largest_module: Optional[str]
    largest_module_cells: Optional[float]
    avg_module_size: float
    median_module_size: float
    top_n_actual: int
    top_n_pct: Optional[float]
    top_n_cells: float
    module_rows: List[ModuleSizeRow] = field(default_factory=list)
    neg_cell_count_rows: int = 0
    cell_count_available: bool = True


def _status_band(cumulative_pct: float) -> str:
    if cumulative_pct <= 0.50:
        return "CRITICAL"
    if cumulative_pct <= 0.80:
        return "HIGH"
    if cumulative_pct <= 0.95:
        return "WATCH"
    return "OK"


def _primary_lever(avg_cells_per_item: float, module_pct: float, all_avgs: pd.Series) -> str:
    """A best-effort, data-driven recommendation per module. This is an
    INFERENCE from shape (avg cells/line item, share of model), not a
    guarantee -- always surfaced with confidence=Estimated downstream."""
    high_avg = all_avgs.quantile(0.75) if len(all_avgs) >= 4 else all_avgs.max()
    if avg_cells_per_item >= high_avg and avg_cells_per_item > 0:
        return "Re-dimension / split grain"
    if module_pct >= 0.03:
        return "Apply Time Ranges"
    return "Review for consolidation"


def analyze_size(nd: NormalizedData, agg_method: str = "max", top_n: int = 5) -> SizeSummary:
    df = nd.df
    modules_count = df["_ModuleResolved_"].nunique()
    line_items_count = len(df)

    if not nd.cell_count_available:
        return SizeSummary(
            total_cells=0.0, modules_count=modules_count, line_items_count=line_items_count,
            largest_module=None, largest_module_cells=None, avg_module_size=0.0, median_module_size=0.0,
            top_n_actual=0, top_n_pct=None, top_n_cells=0.0, cell_count_available=False,
        )

    cell_num = pd.to_numeric(df[nd.cell_count_col], errors="coerce")
    neg_count = int((cell_num < 0).sum())

    work = pd.DataFrame({"Module": df["_ModuleResolved_"], "Cell": cell_num}).dropna(subset=["Cell"])
    work = work[work["Cell"] >= 0]

    line_item_counts = df.groupby("_ModuleResolved_").size()
    mod_sum = work.groupby("Module", as_index=False)["Cell"].agg(agg_method).sort_values("Cell", ascending=False)
    total_cells = float(mod_sum["Cell"].sum())

    mod_sum["line_items"] = mod_sum["Module"].map(line_item_counts).fillna(0).astype(int)
    mod_sum["avg_cells_per_item"] = np.where(
        mod_sum["line_items"] > 0, mod_sum["Cell"] / mod_sum["line_items"].replace(0, np.nan), 0.0
    )
    mod_sum["module_type"] = mod_sum["Module"].apply(classify_module_type)
    mod_sum["pct"] = mod_sum["Cell"] / total_cells if total_cells > 0 else 0.0
    mod_sum["cumulative_pct"] = mod_sum["pct"].cumsum()

    all_avgs = mod_sum["avg_cells_per_item"]
    rows: List[ModuleSizeRow] = []
    for i, r in enumerate(mod_sum.itertuples(index=False), start=1):
        rows.append(ModuleSizeRow(
            rank=i, module=r.Module, cell_count=float(r.Cell), pct_of_model=float(r.pct),
            cumulative_pct=float(r.cumulative_pct), line_items=int(r.line_items),
            avg_cells_per_item=float(r.avg_cells_per_item), module_type=r.module_type,
            status=_status_band(float(r.cumulative_pct)),
            primary_lever=_primary_lever(float(r.avg_cells_per_item), float(r.pct), all_avgs),
        ))

    largest = rows[0] if rows else None
    top_n_actual = min(top_n, len(rows))
    top_n_cells = float(sum(r.cell_count for r in rows[:top_n_actual]))
    top_n_pct = (top_n_cells / total_cells * 100.0) if total_cells > 0 else None

    module_sizes = mod_sum["Cell"].values
    avg_module_size = float(np.mean(module_sizes)) if len(module_sizes) else 0.0
    median_module_size = float(np.median(module_sizes)) if len(module_sizes) else 0.0

    return SizeSummary(
        total_cells=total_cells, modules_count=modules_count, line_items_count=line_items_count,
        largest_module=largest.module if largest else None,
        largest_module_cells=largest.cell_count if largest else None,
        avg_module_size=avg_module_size, median_module_size=median_module_size,
        top_n_actual=top_n_actual, top_n_pct=top_n_pct, top_n_cells=top_n_cells,
        module_rows=rows, neg_cell_count_rows=neg_count, cell_count_available=True,
    )


def cells_to_gb(cells: float) -> float:
    return cells / CELLS_PER_GB
