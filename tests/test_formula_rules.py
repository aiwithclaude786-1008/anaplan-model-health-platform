import pandas as pd

from app.data.normalization import normalize
from app.analysis.formula_analysis import build_feature_table, build_formula_features, evaluate_rules
from app.rules.registry import get_active_rules
from app.rules.thresholds import RuleThresholds


def _feats_for_formulas(formulas):
    return build_formula_features(pd.Series(formulas))


def test_multiple_lookup_detected():
    feats = _feats_for_formulas(["A[LOOKUP: X] + B[LOOKUP: Y]"])
    assert feats.loc[0, "count_lookup"] == 2


def test_post_lookup_nested_detected():
    feats = _feats_for_formulas(["POST(Inv.Delta, Map.Tgt[LOOKUP: Map.Rule])"])
    assert bool(feats.loc[0, "has_post_lookup_nested"]) is True
    assert bool(feats.loc[0, "has_post_sum_nested"]) is False


def test_post_sum_nested_detected():
    feats = _feats_for_formulas(["POST(Inv.Delta[SUM: Dept.Map], Map.Tgt)"])
    assert bool(feats.loc[0, "has_post_sum_nested"]) is True


def test_post_inside_if_detected():
    feats = _feats_for_formulas(["IF Flag THEN POST(Inv.Delta, Map.Tgt[LOOKUP: Map.Rule]) ELSE 0"])
    assert bool(feats.loc[0, "has_post_inside_if"]) is True


def test_timesum_without_range_flagged():
    feats = _feats_for_formulas(["TIMESUM(Salary)"])
    assert bool(feats.loc[0, "has_timesum"]) is True
    assert bool(feats.loc[0, "has_start_or_end"]) is False


def test_timesum_with_range_not_flagged_as_missing_range():
    feats = _feats_for_formulas(["TIMESUM(Salary, START(), END())"])
    assert bool(feats.loc[0, "has_start_or_end"]) is True


def test_select_hardcoded_vs_time_scoped():
    feats = _feats_for_formulas(["Amount[SELECT: FY24]", "Revenue[SELECT: TIME.All Periods]"])
    assert bool(feats.loc[0, "has_select_hardcoded"]) is True
    assert bool(feats.loc[0, "has_select_time_scoped"]) is False
    assert bool(feats.loc[1, "has_select_hardcoded"]) is False
    assert bool(feats.loc[1, "has_select_time_scoped"]) is True


def test_case_insensitivity():
    feats = _feats_for_formulas(["a[lookup: x] + b[Lookup: y]"])
    assert feats.loc[0, "count_lookup"] == 2


def test_empty_formula_flags_nothing():
    feats = _feats_for_formulas([""])
    assert feats.loc[0, "count_if"] == 0
    assert feats.loc[0, "has_post"] == False  # noqa: E712 (numpy bool)


def test_evaluate_rules_on_full_export(raw_export_df):
    nd = normalize(raw_export_df)
    feats = build_feature_table(nd)
    rules = get_active_rules(set(nd.optional_cols.keys()), nd.cell_count_available, RuleThresholds())
    findings = evaluate_rules(rules, feats)

    rule_ids = {f.rule_id for f in findings}
    assert "RULE-FORMULA-007" in rule_ids  # POST + LOOKUP nested (Transfer Post)
    assert "RULE-SIZE-001" in rule_ids     # full-grain cluster (Revenue A-D)
    assert "RULE-DIM-001" in rule_ids      # subsidiary view (Filter Flag)
    assert "RULE-DIM-002" in rule_ids      # full model calendar
    assert "RULE-FORMULA-012" in rule_ids  # hardcoded SELECT
    assert "RULE-ARCH-001" in rule_ids     # TEXT in calc (Account Code)

    # Time-scoped SELECT and the clean constant line item must not be flagged.
    time_scoped_findings = [f for f in findings if f.line_item == "Time Scoped Select" and f.rule_id == "RULE-FORMULA-012"]
    assert time_scoped_findings == []
