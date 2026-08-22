# app/rules/base.py
# ============================================================
# Rule engine core. Every detection in the platform -- formula,
# size, dimensionality, performance, architecture -- is expressed
# as a Rule with a stable ID and full metadata, per master spec
# section 17. detect() is VECTORIZED: it takes the whole feature
# table built by analysis/formula_analysis.build_feature_table()
# (one row per line item) and returns a boolean pandas Series
# aligned to it -- not a per-row callback -- so evaluating all
# rules against a large export is a handful of pandas column
# operations instead of a Python-level loop over every
# (row, rule) pair. Rules never mutate state and never talk to
# Streamlit -- they're pure and unit-testable.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

CONFIDENCE_MEASURED = "Measured"
CONFIDENCE_ESTIMATED = "Estimated"
CONFIDENCE_POTENTIAL = "Potential"
CONFIDENCE_REQUIRES_VALIDATION = "Requires validation"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    name: str
    category: str  # Formula | Size | Dimensionality | Performance | Architecture | Governance
    description: str  # the best-practice rule statement (PLANUAL-style)
    detect: Callable[[pd.DataFrame], pd.Series]  # vectorized: feats -> boolean mask aligned to feats.index
    severity: str  # critical | high | medium | low
    recommendation: str
    confidence: str = CONFIDENCE_ESTIMATED
    doc_ref: str = "Anaplan PLANUAL best practice"
    affects_size: bool = False
    affects_performance: bool = False
    why_it_matters: str = ""
    redesign_example: Optional[str] = None
