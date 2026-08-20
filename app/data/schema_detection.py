# app/data/schema_detection.py
# ============================================================
# Column detection, migrated from the original app.py find_col()
# and expanded per master spec section 19: the tool should
# recognize many possible Anaplan export column-naming schemes,
# not just one fixed set of headers.
# ============================================================
from __future__ import annotations
from typing import List, Optional, Sequence


def find_col(cols: Sequence[str], keys: Sequence[str]) -> Optional[str]:
    """Exact (case-insensitive) match first, then substring match."""
    cl = [str(c).lower() for c in cols]
    for k in keys:
        if k in cl:
            return cols[cl.index(k)]
    for k in keys:
        for i, low in enumerate(cl):
            if k in low:
                return cols[i]
    return None


# Extensible synonym map. Add new keys here, not in UI code.
# The "applies_to"/"time_scale"/"time_range"/"summary"/"notes"/
# "referenced_by" keys match columns that real Anaplan "Module List
# Export" files carry (confirmed against a live client export) and
# power the dimensionality/subsidiary-view/time-range/summary-method/
# governance rule categories.
FIELD_SYNONYMS = {
    "module": ["module name", "module"],
    "line_item": ["line item", "line item name", "item name"],
    "formula": ["formula", "expression", "formula text", "line item formula",
                "item formula", "calc formula", "formula string"],
    "format": ["format", "data format", "line item format"],
    "cell_count": ["cell count", "cell_count", "cell", "cells", "total cells"],
    "calc_effort": ["calculation effort", "calc effort", "calculation",
                     "calc time", "calculation time", "compute effort"],
    "summary": ["summary"],
    "list": ["list", "lists", "applies to list"],
    "applies_to": ["applies to (override)", "applies to"],
    "dimension": ["dimension", "dimensions"],
    "time_scale": ["time scale"],
    "time_range": ["time range"],
    "version": ["versions", "version"],
    "notes": ["notes"],
    "dependencies": ["dependencies", "depends on"],
    "referenced_by": ["referenced by"],
    "parent_module": ["parent module", "source module", "parent"],
    "reference_count": ["reference count", "usage count"],
}


def detect_schema(cols: Sequence[str]) -> dict:
    """Best-effort column map. Returns {field_key: column_name_or_None}."""
    cols = list(cols)
    return {field: find_col(cols, keys) for field, keys in FIELD_SYNONYMS.items()}


def available_fields(schema_map: dict) -> List[str]:
    return [k for k, v in schema_map.items() if v]
