# app/data/validation.py
# ============================================================
# Data Quality Check (master spec section 18). Runs before
# analysis so every downstream number can be trusted, or at
# least so problems are visible instead of silently discarded.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from app.data.normalization import NormalizedData


@dataclass
class DataQualityIssue:
    check: str
    severity: str  # high | medium | low
    count: int
    detail: str


@dataclass
class DataQualityReport:
    score: float
    issues: List[DataQualityIssue] = field(default_factory=list)
    total_rows: int = 0
    separator_rows: int = 0


_SEVERITY_PENALTY = {"high": 12.0, "medium": 6.0, "low": 2.0}


def run_data_quality_checks(nd: NormalizedData) -> DataQualityReport:
    df = nd.df
    issues: List[DataQualityIssue] = []
    total_rows = len(df)

    # Missing formulas (blank is normal for a header/input row, so this
    # is informational, not necessarily a defect -- only "unsupported
    # columns" and outright bad values count as real quality problems.)
    formula_blank = df[nd.formula_col].isna() | (df[nd.formula_col].astype(str).str.strip() == "")
    n_blank_formula = int(formula_blank.sum())

    # Duplicate (Module, Line Item) pairs -- a real duplicate export row.
    dup_mask = df.duplicated(subset=[nd.module_col, nd.line_col], keep=False)
    n_dupes = int(dup_mask.sum())
    if n_dupes > 0:
        issues.append(DataQualityIssue(
            "Duplicate Module + Line Item rows", "medium", n_dupes,
            f"{n_dupes} rows share the same Module and Line Item name -- check for a duplicated export."
        ))

    # Missing line-item names
    n_missing_name = int((df[nd.line_col].isna() | (df[nd.line_col].astype(str).str.strip() == "")).sum())
    if n_missing_name > 0:
        issues.append(DataQualityIssue(
            "Missing line-item names", "medium", n_missing_name,
            f"{n_missing_name} rows have no value in the Line Item column."
        ))

    # Missing modules (before forward-fill)
    n_missing_module = int((df[nd.module_col].isna() | (df[nd.module_col].astype(str).str.strip() == "")).sum())
    if n_missing_module > 0:
        issues.append(DataQualityIssue(
            "Missing module on some rows", "low", n_missing_module,
            f"{n_missing_module} rows had a blank Module value -- forward-filled from the row above, "
            "consistent with how Anaplan module-list exports repeat the module header only on the first line item."
        ))

    # Negative / invalid cell counts
    n_negative_cells = 0
    if nd.cell_count_available:
        cell_num = pd.to_numeric(df[nd.cell_count_col], errors="coerce")
        n_negative_cells = int((cell_num < 0).sum())
        if n_negative_cells > 0:
            issues.append(DataQualityIssue(
                "Negative Cell Count values", "high", n_negative_cells,
                f"{n_negative_cells} rows have a negative Cell Count -- excluded from size totals; check the source export."
            ))
        n_unparsable = int(cell_num.isna().sum() - df[nd.cell_count_col].isna().sum())
        if n_unparsable > 0:
            issues.append(DataQualityIssue(
                "Non-numeric Cell Count values", "medium", n_unparsable,
                f"{n_unparsable} rows have a Cell Count value that couldn't be parsed as a number."
            ))

    # Separator / section-header rows: no formula, zero (or missing) cell
    # count, and typically a decorative name. Common in real Anaplan
    # exports (module-group banners, "DATA" section dividers). These
    # are not "invalid" -- flagged so line-item counts aren't inflated
    # by non-data rows.
    if nd.cell_count_available:
        cell_num = pd.to_numeric(df[nd.cell_count_col], errors="coerce").fillna(0)
        separator_mask = formula_blank & (cell_num == 0)
    else:
        separator_mask = pd.Series(False, index=df.index)
    n_separator = int(separator_mask.sum())
    if n_separator > 0:
        issues.append(DataQualityIssue(
            "Section-header / separator rows", "low", n_separator,
            f"{n_separator} rows look like decorative section headers (no formula, zero cells) rather than "
            "real line items -- included in raw counts but excluded from formula-risk analysis."
        ))

    if not nd.cell_count_available:
        issues.append(DataQualityIssue(
            "No Cell Count column found", "high", 1,
            "Size, Pareto, and hotspot analysis cannot run without a Cell Count column in the export."
        ))

    penalty = sum(_SEVERITY_PENALTY.get(i.severity, 0) for i in issues)
    # Scale penalty by how much of the file is affected, so one bad row
    # in a 50,000-row file doesn't tank the score the same as one bad
    # row in a 20-row file.
    if total_rows > 0:
        affected = sum(i.count for i in issues if i.check != "No Cell Count column found")
        severity_component = penalty
        volume_component = min(30.0, (affected / total_rows) * 100.0 * 0.5)
        score = max(0.0, 100.0 - severity_component - volume_component)
    else:
        score = 0.0

    return DataQualityReport(score=round(score, 1), issues=issues, total_rows=total_rows, separator_rows=n_separator)
