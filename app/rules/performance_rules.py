# app/rules/performance_rules.py
# ============================================================
# RULE-PERF-00x. "Summary on big item" needs a Summary column;
# only wired in by the registry when that column is present.
# ============================================================
from __future__ import annotations

from typing import List

from app.rules.base import Rule, CONFIDENCE_MEASURED, CONFIDENCE_ESTIMATED


def build_performance_rules() -> List[Rule]:
    return [
        Rule(
            rule_id="RULE-PERF-001", name="Summary set on a large calc item", category="Performance",
            description="Calculation modules should set Summary = NONE -- a summary method on a large line "
                        "item in a Calc module forces Anaplan to aggregate it on every recalculation.",
            detect=lambda r: bool(r.get("has_summary_on_big_item", False)),
            severity="high",
            recommendation="Set Summary = NONE on this line item (or move the aggregation to a dedicated output module).",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
            why_it_matters="Summary aggregation on a large, calc-heavy line item repeats work the model rarely "
                            "needs at every level of every dimension it's summarized over.",
        ),
        Rule(
            rule_id="RULE-PERF-002", name="Long calculation chain", category="Performance",
            description="Long cross-module dependency chains slow recalculation and make impact analysis hard.",
            detect=lambda r: False,  # module-level; see analysis/dependency_analysis.py
            severity="high",
            recommendation="Break the chain into staged calculations closer to where the data is sourced.",
            confidence=CONFIDENCE_ESTIMATED, affects_performance=True,
        ),
    ]
