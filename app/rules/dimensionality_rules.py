# app/rules/dimensionality_rules.py
# ============================================================
# RULE-DIM-00x. Only meaningful when the export carries an
# "Applies To" / "Time Range" column -- the registry only wires
# these in when that column was actually detected (see
# rules/registry.py), so a model without that column simply
# never surfaces these findings instead of guessing.
# ============================================================
from __future__ import annotations

from typing import List

from app.rules.base import Rule, CONFIDENCE_MEASURED


def build_dimensionality_rules() -> List[Rule]:
    return [
        Rule(
            rule_id="RULE-DIM-001", name="Subsidiary view", category="Dimensionality",
            description="Avoid subsidiary views -- a line item should not be dimensioned differently from its "
                        "own module (an 'Applies To' override) except in a genuine edge case.",
            detect=lambda f: f["is_subsidiary_view"],
            severity="medium",
            recommendation="Move the line item into a module whose native dimensionality already matches it.",
            confidence=CONFIDENCE_MEASURED, affects_size=True,
            why_it_matters="A subsidiary-view line item hides its real dimensionality from the module it lives "
                            "in, making the model harder to reason about and often forcing an unnecessary "
                            "cross-module reference just to reach it.",
        ),
        Rule(
            rule_id="RULE-DIM-002", name="Full Model Calendar", category="Dimensionality",
            description="Apply Time Ranges to limit line items to the periods they actually need, rather than "
                        "leaving them on the full model calendar.",
            detect=lambda f: f["is_full_calendar"],
            severity="high",
            recommendation="Create a scoped Time Range (e.g. Actuals history + current/next FY) and reassign it.",
            confidence=CONFIDENCE_MEASURED, affects_size=True,
            why_it_matters="Every extra period on the calendar multiplies that line item's cell count -- a "
                            "line item that only needs 24 months but sits on a 10-year calendar is paying for "
                            "periods it will never use.",
        ),
    ]
