# app/rules/formula_rules.py
# ============================================================
# RULE-FORMULA-001.. : detections that only need the formula text
# itself (via analysis.formula_analysis.build_formula_features),
# so they run on every export regardless of which optional
# columns are present. Migrated from the original app.py
# detect_row()/REFACTOR/RULE_DESCRIPTIONS, plus the SELECT
# hardcoded-member rule added from the real PLANUAL report.
# ============================================================
from __future__ import annotations

from typing import List

from app.rules.base import Rule, CONFIDENCE_MEASURED
from app.rules.thresholds import RuleThresholds


def build_formula_rules(t: RuleThresholds) -> List[Rule]:
    return [
        Rule(
            rule_id="RULE-FORMULA-001", name="Multiple LOOKUP", category="Formula",
            description="Avoid chaining multiple LOOKUPs in a single formula.",
            detect=lambda r: bool(r["count_lookup"] > t.lookup_multi_threshold),
            severity="high",
            recommendation="Split LOOKUP into a helper line item before aggregation.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
            why_it_matters="Each LOOKUP re-scans a target module at calculation time; chaining several in one "
                            "formula multiplies that cost every time the line item recalculates.",
        ),
        Rule(
            rule_id="RULE-FORMULA-002", name="Deep Nested IF", category="Formula",
            description="Keep IF logic shallow -- long chains should become a mapping module.",
            detect=lambda r: bool(r["count_if"] >= t.nested_if_high),
            severity="high",
            recommendation="Replace IF chains with a mapping module.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
            why_it_matters="Deeply nested IF/THEN/ELSE branches are hard to test, hard to maintain, and force "
                            "Anaplan to evaluate every branch's dependencies even when only one path is taken.",
        ),
        Rule(
            rule_id="RULE-FORMULA-002B", name="Nested IF", category="Formula",
            description="Keep IF logic shallow -- long chains should become a mapping module.",
            detect=lambda r: bool(t.nested_if_med <= r["count_if"] < t.nested_if_high),
            severity="medium",
            recommendation="Replace IF chains with a mapping module.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-003", name="LOOKUP & SUM in one mapping", category="Formula",
            description="Don't combine LOOKUP and SUM inside the same dimension mapping.",
            detect=lambda r: bool(r["map_has_lookup_sum"]),
            severity="high",
            recommendation="Stage the aggregation and the lookup into separate line items.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-004", name="LOOKUP & SELECT in one mapping", category="Formula",
            description="Don't combine LOOKUP and SELECT inside the same dimension mapping.",
            detect=lambda r: bool(r["map_has_lookup_select"]),
            severity="high",
            recommendation="Stage the lookup and the select into separate line items.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-005", name="SELECT & SUM in one mapping", category="Formula",
            description="Don't combine SELECT and SUM inside the same dimension mapping.",
            detect=lambda r: bool(r["map_has_select_sum"]),
            severity="high",
            recommendation="Stage the select and the aggregation into separate line items.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-006", name="High Function Density", category="Formula",
            description="Keep formulas short and single-purpose rather than function-dense.",
            detect=lambda r: bool(r["func_density_count"] >= t.daisy_chain_threshold),
            severity="high",
            recommendation="Stage the calculation across multiple line items.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-007", name="POST + LOOKUP (nested)", category="Formula",
            description="Keep the POST target mapping outside the POST statement itself.",
            detect=lambda r: bool(r["has_post_lookup_nested"]),
            severity="high",
            recommendation="Separate POST and LOOKUP into different staged line items / modules.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True, affects_size=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-008", name="POST + SUM (nested)", category="Formula",
            description="Keep the POST source aggregation outside the POST statement itself.",
            detect=lambda r: bool(r["has_post_sum_nested"]),
            severity="high",
            recommendation="Separate POST and SUM into different staged line items / modules.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True, affects_size=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-009", name="POST inside IF", category="Formula",
            description="Move POST outside conditional branches into a dedicated output line item.",
            detect=lambda r: bool(r["has_post_inside_if"]),
            severity="high",
            recommendation="Move POST outside IF; calculate POST in a dedicated output line item/module.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-010", name="TIMESUM without range", category="Formula",
            description="Always scope TIMESUM with a START/END range.",
            detect=lambda r: bool(r["has_timesum"] and not r["has_start_or_end"]),
            severity="high",
            recommendation="Add START/END or replace with cumulative logic (PREVIOUS-based module).",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-011", name="TIMESUM", category="Formula",
            description="Prefer a cumulative module using PREVIOUS over TIMESUM.",
            detect=lambda r: bool(r["has_timesum"] and r["has_start_or_end"]),
            severity="medium",
            recommendation="Replace TIMESUM with a cumulative module using PREVIOUS.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
        ),
        Rule(
            rule_id="RULE-FORMULA-012", name="Hardcoded SELECT", category="Formula",
            description="SELECT is only acceptable when scoped to TIME.All Periods -- a hardcoded member "
                        "select should be replaced with a mapping/lookup so it doesn't need manual upkeep.",
            detect=lambda r: bool(r["has_select_hardcoded"]),
            severity="medium",
            recommendation="Replace the hardcoded SELECT member with a SYS-driven mapping/lookup module.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
            why_it_matters="A SELECT on a hardcoded member silently goes stale as list items change, and each "
                            "one is a manual maintenance point future modelers won't know to check.",
        ),
        Rule(
            rule_id="RULE-FORMULA-013", name="Long formula", category="Formula",
            description="Prefer short, single-purpose formulas over very long ones.",
            detect=lambda r: bool(r["formula_length"] >= t.formula_length_high),
            severity="medium",
            recommendation="Split into staged line items, each with a single calculation step.",
            confidence=CONFIDENCE_MEASURED, affects_performance=True,
            why_it_matters="A very long formula usually means several calculation steps are fused into one "
                            "line item, which makes it harder to isolate what's slow or wrong later.",
        ),
    ]
