# app/rules/architecture_rules.py
# ============================================================
# RULE-ARCH-00x / RULE-GOV-00x -- format/architecture choices
# (TEXT in a calc module) and governance/documentation gaps.
# ============================================================
from __future__ import annotations

from typing import List

from app.rules.base import Rule, CONFIDENCE_MEASURED


def build_architecture_rules() -> List[Rule]:
    return [
        Rule(
            rule_id="RULE-ARCH-001", name="TEXT in calc module", category="Architecture",
            description="TEXT is the heaviest storage format -- keep calculated text out of Calc modules "
                        "and push it to a dedicated SYS/output module.",
            detect=lambda f: f["is_text_in_calc"],
            severity="medium",
            recommendation="Convert to an ENTITY/list-formatted line item, or relocate the calculated text to a SYS module.",
            confidence=CONFIDENCE_MEASURED, affects_size=True,
            why_it_matters="A TEXT line item at a given grain uses substantially more memory per cell than a "
                            "NUMBER or BOOLEAN line item at the same grain.",
        ),
        Rule(
            rule_id="RULE-GOV-001", name="Undocumented complex line item", category="Governance",
            description="Complex line items (nested logic, long formulas) should carry a Note describing "
                        "purpose and source.",
            detect=lambda f: f["is_documentation_gap"],
            severity="low",
            recommendation="Add a one-line Note: purpose + data source.",
            confidence=CONFIDENCE_MEASURED,
            why_it_matters="An undocumented, complex formula becomes a key-person risk -- only the original "
                            "builder can safely change it.",
        ),
    ]
