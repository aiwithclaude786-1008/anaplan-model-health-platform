from app.data.normalization import normalize
from app.analysis.formula_analysis import build_feature_table, evaluate_rules, compute_formula_impact_score
from app.analysis.size_analysis import analyze_size
from app.analysis.optimization_engine import build_top_opportunities, build_size_reduction_opportunities
from app.rules.registry import get_active_rules
from app.rules.thresholds import RuleThresholds


def _analyze(raw_export_df):
    nd = normalize(raw_export_df)
    feats = build_feature_table(nd)
    feats["impact_score"] = compute_formula_impact_score(feats)
    rules = get_active_rules(set(nd.optional_cols.keys()), nd.cell_count_available, RuleThresholds())
    findings = evaluate_rules(rules, feats)
    size = analyze_size(nd)
    return findings, size


def test_top_opportunities_are_ranked_and_capped(raw_export_df):
    findings, size = _analyze(raw_export_df)
    top = build_top_opportunities(findings, size.total_cells, limit=10)

    assert len(top) <= 10
    scores = [o.score for o in top]
    assert scores == sorted(scores, reverse=True)
    assert [o.priority for o in top] == list(range(1, len(top) + 1))


def test_size_reduction_opportunities_only_include_size_affecting_findings(raw_export_df):
    findings, size = _analyze(raw_export_df)
    opps = build_size_reduction_opportunities(findings, size.total_cells)

    assert len(opps) > 0
    size_rule_ids = {f.rule_id for f in findings if f.affects_size}
    assert all(any(rid in o.issue for rid in size_rule_ids) for o in opps)


def test_formula_impact_score_bounded(raw_export_df):
    nd = normalize(raw_export_df)
    feats = build_feature_table(nd)
    scores = compute_formula_impact_score(feats)
    assert (scores >= 0).all()
    assert (scores <= 100).all()
