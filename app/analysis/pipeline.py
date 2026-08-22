# app/analysis/pipeline.py
# ============================================================
# Runs the whole analysis exactly once per upload (master spec
# section 22: "the analysis pipeline should execute once and
# feed all dashboards"). Every UI page and every report reads
# from the AnalysisResult this returns -- nothing recomputes
# findings, size, or scores independently.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pandas as pd
import streamlit as st

from app.data.normalization import normalize, NormalizedData
from app.data.validation import run_data_quality_checks, DataQualityReport
from app.rules.thresholds import RuleThresholds
from app.rules.registry import get_active_rules
from app.analysis.formula_analysis import (
    build_feature_table, evaluate_rules, compute_formula_impact_score,
)
from app.analysis.size_analysis import analyze_size, SizeSummary
from app.analysis.dimensionality_analysis import analyze_dimensionality, DimensionalityReport
from app.analysis.model_health import compute_model_health
from app.analysis.optimization_engine import (
    build_size_reduction_opportunities, build_top_opportunities, build_hotspot_matrix, HotspotPoint,
)
from app.analysis.action_plan import build_action_plan
from app.models.schemas import Finding, HealthScoreBreakdown, OptimizationOpportunity, ActionPlanItem


@dataclass
class AnalysisResult:
    nd: NormalizedData
    feats: pd.DataFrame
    findings: List[Finding]
    # Rule IDs only (not the Rule objects themselves) -- a Rule carries a
    # `detect` lambda, which isn't pickleable, and st.cache_data pickles
    # the whole AnalysisResult to cache it.
    active_rule_ids: List[str]
    size: SizeSummary
    dimensionality: DimensionalityReport
    # Dependency/daisy-chain analysis is deliberately NOT computed here.
    # Its inferred-mode cross-reference regex scan is the most expensive
    # step in the whole pipeline, and only one page (Dependency
    # Analysis) needs it -- so it's computed on demand there instead
    # (app/ui/dependency_view.py), keeping upload-to-first-render fast
    # for every other page.
    health: HealthScoreBreakdown
    data_quality: DataQualityReport
    top_opportunities: List[OptimizationOpportunity]
    size_opportunities: List[OptimizationOpportunity]
    action_plan: List[ActionPlanItem]
    hotspots: List[HotspotPoint] = field(default_factory=list)


def _run(df: pd.DataFrame, thresholds: RuleThresholds, agg_method: str, top_n_modules: int) -> AnalysisResult:
    nd = normalize(df)
    data_quality = run_data_quality_checks(nd)

    feats = build_feature_table(nd)
    feats["impact_score"] = compute_formula_impact_score(feats)

    active_rules = get_active_rules(set(nd.optional_cols.keys()), nd.cell_count_available, thresholds)
    findings = evaluate_rules(active_rules, feats)

    size = analyze_size(nd, agg_method=agg_method, top_n=top_n_modules)
    dimensionality = analyze_dimensionality(nd, feats)
    health = compute_model_health(findings, size, dimensionality)

    size_opportunities = build_size_reduction_opportunities(findings, size.total_cells)
    top_opportunities = build_top_opportunities(findings, size.total_cells)
    action_plan = build_action_plan(top_opportunities + size_opportunities)
    hotspots = build_hotspot_matrix(feats, feats["impact_score"]) if nd.cell_count_available else []

    return AnalysisResult(
        nd=nd, feats=feats, findings=findings, active_rule_ids=[r.rule_id for r in active_rules],
        size=size, dimensionality=dimensionality, health=health,
        data_quality=data_quality, top_opportunities=top_opportunities,
        size_opportunities=size_opportunities, action_plan=action_plan, hotspots=hotspots,
    )


@st.cache_data(show_spinner="Running model health analysis...")
def run_pipeline(df: pd.DataFrame, thresholds: RuleThresholds, agg_method: str = "max",
                  top_n_modules: int = 5) -> AnalysisResult:
    return _run(df, thresholds, agg_method, top_n_modules)
