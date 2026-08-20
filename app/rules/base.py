# app/rules/base.py
# ============================================================
# Rule engine core. Every detection in the platform -- formula,
# size, dimensionality, performance, architecture -- is expressed
# as a Rule with a stable ID and full metadata, per master spec
# section 17. detect() gets a pandas Series (one row of the
# feature table built by analysis/formula_analysis.py's
# build_features(), joined with size/dimensionality columns) and
# returns True/False. Rules never mutate state and never talk to
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
    detect: Callable[[pd.Series], bool]
    severity: str  # critical | high | medium | low
    recommendation: str
    confidence: str = CONFIDENCE_ESTIMATED
    doc_ref: str = "Anaplan PLANUAL best practice"
    affects_size: bool = False
    affects_performance: bool = False
    why_it_matters: str = ""
    redesign_example: Optional[str] = None
