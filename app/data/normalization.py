# app/data/normalization.py
# ============================================================
# Turns a raw uploaded DataFrame into a normalized working frame.
# Preserves the original app.py convention: Line Item = FIRST
# column, Module = LAST column (this was an explicit, documented
# rule in the original tool and real Anaplan module-list exports
# follow it), while formula/cell-count/etc. are located via
# data.schema_detection synonym matching.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from app.data.schema_detection import detect_schema


@dataclass
class NormalizedData:
    df: pd.DataFrame
    line_col: str
    module_col: str
    formula_col: str
    cell_count_col: Optional[str]
    calc_effort_col: Optional[str]
    optional_cols: dict  # field_key -> column name, for list/dimension/time/version/etc.
    cell_count_available: bool
    module_resolved_col: str = "_ModuleResolved_"


class SchemaError(ValueError):
    pass


def normalize(df: pd.DataFrame) -> NormalizedData:
    df = df.dropna(how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]
    cols = list(df.columns)

    if len(cols) < 2:
        raise SchemaError("Your file must have at least 2 columns.")

    line_col = cols[0]
    module_col = cols[-1]

    schema = detect_schema(cols)
    formula_col = "Formula" if "Formula" in df.columns else schema.get("formula")
    if not formula_col or formula_col not in df.columns:
        raise SchemaError(
            "Formula column not found. Your export must include a Formula/Expression column. "
            f"Detected columns: {cols}"
        )

    cell_count_col = "Cell Count" if "Cell Count" in df.columns else schema.get("cell_count")
    if cell_count_col not in df.columns:
        cell_count_col = None
    calc_effort_col = "Calculation Effort" if "Calculation Effort" in df.columns else schema.get("calc_effort")
    if calc_effort_col not in df.columns:
        calc_effort_col = None

    optional_cols = {}
    for key in ("format", "summary", "list", "applies_to", "dimension", "time_scale", "time_range",
                "version", "notes", "dependencies", "referenced_by", "parent_module", "reference_count"):
        col = schema.get(key)
        if col and col in df.columns and col not in (line_col, module_col, formula_col):
            optional_cols[key] = col

    mod_series = (
        df[module_col].astype(str).str.strip()
        .replace({"": np.nan, "None": np.nan, "none": np.nan, "NaN": np.nan, "nan": np.nan, "-": np.nan})
        .ffill()
    )
    df["_ModuleResolved_"] = mod_series.fillna("Unknown")

    return NormalizedData(
        df=df,
        line_col=line_col,
        module_col=module_col,
        formula_col=formula_col,
        cell_count_col=cell_count_col,
        calc_effort_col=calc_effort_col,
        optional_cols=optional_cols,
        cell_count_available=cell_count_col is not None,
    )
