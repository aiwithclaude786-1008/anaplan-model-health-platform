# app/rules/registry.py
# ============================================================
# Assembles every Rule into one list. get_all_rules() with no
# arguments (defaults + no optional columns assumed) powers the
# Rules Reference page, which documents every rule the platform
# knows about regardless of what's in the currently loaded file.
# get_active_rules() is what the analysis pipeline actually runs
# against a specific upload -- it drops rules whose required
# optional column wasn't detected, per master spec section 25/26
# (never fabricate a finding from data that isn't there).
# ============================================================
from __future__ import annotations

from typing import List, Optional, Set

from app.rules.base import Rule
from app.rules.thresholds import RuleThresholds
from app.rules.formula_rules import build_formula_rules
from app.rules.size_rules import build_size_rules
from app.rules.dimensionality_rules import build_dimensionality_rules
from app.rules.performance_rules import build_performance_rules
from app.rules.architecture_rules import build_architecture_rules

# rule_id -> optional field key that must be present in the export
# for the rule to be evaluated. Rules not listed here only need the
# mandatory Module/Line Item/Formula columns.
REQUIRES_OPTIONAL_FIELD = {
    "RULE-SIZE-001": "cell_count",
    "RULE-DIM-001": "applies_to",
    "RULE-DIM-002": "time_range",
    "RULE-PERF-001": "summary",
    "RULE-ARCH-001": "format",
    "RULE-GOV-001": "notes",
}


def get_all_rules(thresholds: Optional[RuleThresholds] = None) -> List[Rule]:
    t = thresholds or RuleThresholds()
    rules: List[Rule] = []
    rules += build_formula_rules(t)
    rules += build_size_rules(t)
    rules += build_dimensionality_rules()
    rules += build_performance_rules()
    rules += build_architecture_rules()
    return rules


def get_active_rules(available_fields: Set[str], cell_count_available: bool,
                      thresholds: Optional[RuleThresholds] = None) -> List[Rule]:
    fields = set(available_fields)
    if cell_count_available:
        fields.add("cell_count")

    active = []
    for rule in get_all_rules(thresholds):
        required = REQUIRES_OPTIONAL_FIELD.get(rule.rule_id)
        if required is None or required in fields:
            active.append(rule)
    return active


def get_rule(rule_id: str) -> Optional[Rule]:
    for r in get_all_rules():
        if r.rule_id == rule_id:
            return r
    return None
