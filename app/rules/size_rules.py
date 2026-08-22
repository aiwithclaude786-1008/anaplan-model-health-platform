# app/rules/size_rules.py
# ============================================================
# RULE-SIZE-00x. "Size concentration" (module/model-level Pareto)
# is documented here for the Rules Reference page but is actually
# computed directly by analysis/size_analysis.py, since it's a
# model-level finding, not a per-line-item one -- its detect()
# is a stub that's never called by the per-row rule pass.
# ============================================================
from __future__ import annotations

from typing import List

import pandas as pd

from app.rules.base import Rule, CONFIDENCE_MEASURED
from app.rules.thresholds import RuleThresholds


def build_size_rules(t: RuleThresholds) -> List[Rule]:
    return [
        Rule(
            rule_id="RULE-SIZE-001", name="Full-grain calc cluster", category="Size",
            description="Line items must not all inherit the module's maximum grain by default -- a cluster "
                        "of items sharing an identical cell count usually means the whole module was built at "
                        "one uniform (often maximal) dimensionality.",
            detect=lambda f: f["in_full_grain_cluster"],
            severity="critical",
            recommendation="Re-dimension or split the module; move rate/driver/lookup line items to a lower grain.",
            confidence=CONFIDENCE_MEASURED, affects_size=True,
            why_it_matters="Every line item in the module pays the full cell cost of the widest dimension, even "
                            "line items that logically don't need that grain (e.g. a flat rate repeated per SKU).",
        ),
        Rule(
            rule_id="RULE-SIZE-002", name="Size concentration", category="Size",
            description="A few modules should not dominate the model's total cell count.",
            detect=lambda f: pd.Series(False, index=f.index),  # model-level; see analysis/size_analysis.py
            severity="critical",
            recommendation="Attack the top of the module ranking first -- re-dimension or split the largest modules.",
            confidence=CONFIDENCE_MEASURED, affects_size=True,
        ),
    ]
