# app/analysis/dimensionality_analysis.py
# ============================================================
# Master spec section 7. Deliberately schema-adaptive: a typical
# Anaplan "Module List Export" does NOT carry per-list cardinality
# (how many members are in each list), so "theoretical cell space
# = product of dimensional cardinalities" cannot be computed from
# this file type -- claiming otherwise would violate section 26
# ("do not overpromise"). What the export DOES carry (when present)
# is Applies To / Time Scale / Time Range / Versions, which is
# enough for subsidiary-view detection and full-calendar detection
# (both already computed per-row in formula_analysis and turned
# into Findings by rules/dimensionality_rules.py) plus a module-
# level summary used here.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from app.data.normalization import NormalizedData


@dataclass
class ModuleDimensionality:
    module: str
    distinct_applies_to: int
    subsidiary_view_items: int
    full_calendar_items: int
    full_calendar_cells: float


@dataclass
class DimensionalityReport:
    has_applies_to: bool
    has_time_range: bool
    total_subsidiary_view_items: int
    total_subsidiary_view_cells: float
    total_full_calendar_items: int
    total_full_calendar_cells: float
    waste_score: Optional[float]  # 0-100, higher = more waste; None if no signal available
    module_rows: List[ModuleDimensionality] = field(default_factory=list)
    note: str = ""


def analyze_dimensionality(nd: NormalizedData, feats: pd.DataFrame) -> DimensionalityReport:
    has_applies_to = "applies_to" in nd.optional_cols
    has_time_range = "time_range" in nd.optional_cols

    if not has_applies_to and not has_time_range:
        return DimensionalityReport(
            has_applies_to=False, has_time_range=False,
            total_subsidiary_view_items=0, total_subsidiary_view_cells=0.0,
            total_full_calendar_items=0, total_full_calendar_cells=0.0,
            waste_score=None,
            note="This export has no Applies To / Time Range columns, so dimensionality waste can't be "
                 "measured directly -- theoretical cell space (product of list cardinalities) isn't derivable "
                 "from a module-list export either way. Requires validation against the live model.",
        )

    cell = feats["cell_count"].fillna(0)
    sub_mask = feats.get("is_subsidiary_view", pd.Series(False, index=feats.index))
    cal_mask = feats.get("is_full_calendar", pd.Series(False, index=feats.index))

    module_rows: List[ModuleDimensionality] = []
    for mod, g in feats.groupby("module"):
        g_cell = g["cell_count"].fillna(0)
        module_rows.append(ModuleDimensionality(
            module=str(mod),
            distinct_applies_to=int(g["applies_to"].nunique()) if has_applies_to else 0,
            subsidiary_view_items=int(g["is_subsidiary_view"].sum()) if has_applies_to else 0,
            full_calendar_items=int(g["is_full_calendar"].sum()) if has_time_range else 0,
            full_calendar_cells=float(g_cell[g["is_full_calendar"]].sum()) if has_time_range else 0.0,
        ))
    module_rows.sort(key=lambda r: r.full_calendar_cells + r.subsidiary_view_items, reverse=True)

    total_sub_items = int(sub_mask.sum())
    total_sub_cells = float(cell[sub_mask].sum())
    total_cal_items = int(cal_mask.sum())
    total_cal_cells = float(cell[cal_mask].sum())

    total_cells = float(cell.sum())
    waste_score = None
    if total_cells > 0:
        cal_share = total_cal_cells / total_cells if has_time_range else 0.0
        sub_share = (total_sub_items / max(1, len(feats))) if has_applies_to else 0.0
        waste_score = round(min(100.0, (cal_share * 70.0 + sub_share * 30.0) * 100.0), 1)

    return DimensionalityReport(
        has_applies_to=has_applies_to, has_time_range=has_time_range,
        total_subsidiary_view_items=total_sub_items, total_subsidiary_view_cells=total_sub_cells,
        total_full_calendar_items=total_cal_items, total_full_calendar_cells=total_cal_cells,
        waste_score=waste_score, module_rows=module_rows,
        note="Waste score blends the share of model cells left on the full/unscoped calendar and the share of "
             "line items using a subsidiary (Applies To override) view -- both measured from this export, "
             "not estimated.",
    )
