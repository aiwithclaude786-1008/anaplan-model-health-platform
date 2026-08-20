# app/analysis/model_health.py
# ============================================================
# Master spec section 4 -- seven named sub-scores plus an overall
# score, each with a `detail` string a drill-down panel can show
# directly (score -> category -> rule -> module -> line item, per
# the spec's "do not hide the calculation" requirement).
# ============================================================
from __future__ import annotations

from typing import List

from app.models.schemas import Finding, HealthDimension, HealthScoreBreakdown
from app.analysis.size_analysis import SizeSummary
from app.analysis.dimensionality_analysis import DimensionalityReport

_WEIGHTS = {
    "size": 0.25,
    "formula_efficiency": 0.20,
    "calculation_performance": 0.20,
    "dimensionality": 0.15,
    "architecture": 0.10,
    "governance": 0.10,
}


def _band(score: float) -> str:
    if score > 85:
        return "Excellent"
    if score > 70:
        return "Good"
    if score > 50:
        return "Fair"
    return "Critical"


def _cell_weighted_penalty(findings: List[Finding], total_cells: float, category: str, max_penalty: float = 60.0) -> float:
    if total_cells <= 0:
        # No cell-count data: fall back to a simple count-based penalty so
        # formula-only exports still get a meaningful (if coarser) score.
        n = sum(1 for f in findings if f.category == category)
        return min(max_penalty, n * 1.5)
    impact = sum((f.cell_impact or 0.0) for f in findings if f.category == category)
    share = min(1.0, impact / total_cells)
    return share * max_penalty


def compute_model_health(findings: List[Finding], size: SizeSummary, dim: DimensionalityReport) -> HealthScoreBreakdown:
    total_cells = size.total_cells

    size_penalty = 0.0
    size_detail = "No Cell Count data available -- size score defaults to neutral."
    if size.cell_count_available and total_cells > 0:
        conc_penalty = min(50.0, (size.top_n_pct or 0.0) * 0.6)
        cluster_penalty = _cell_weighted_penalty(findings, total_cells, "Size", max_penalty=30.0)
        size_penalty = conc_penalty + cluster_penalty
        size_detail = (
            f"Top {size.top_n_actual} modules hold {size.top_n_pct:.0f}% of {total_cells:,.0f} total cells; "
            f"full-grain clusters and other Size findings add further penalty."
        )
    size_score = max(0.0, 100.0 - size_penalty)

    formula_findings = [f for f in findings if f.category == "Formula"]
    formula_penalty = min(60.0, len(formula_findings) * 0.8) if not (size.cell_count_available and total_cells > 0) \
        else _cell_weighted_penalty(findings, total_cells, "Formula", max_penalty=60.0)
    formula_score = max(0.0, 100.0 - formula_penalty)
    formula_detail = f"{len(formula_findings)} formula-rule findings across the model."

    perf_findings = [f for f in findings if f.affects_performance]
    perf_penalty = min(60.0, len(perf_findings) * 0.6) if not (size.cell_count_available and total_cells > 0) \
        else min(60.0, sum((f.performance_impact or 0.0) for f in perf_findings) / max(total_cells, 1) * 60.0)
    perf_score = max(0.0, 100.0 - perf_penalty)
    perf_detail = f"{len(perf_findings)} findings flagged as performance-affecting."

    if dim.waste_score is not None:
        dim_score = max(0.0, 100.0 - dim.waste_score)
        dim_detail = dim.note
    else:
        dim_score = 70.0  # neutral default -- explicitly not claiming a measured score
        dim_detail = dim.note

    arch_findings = [f for f in findings if f.category == "Architecture"]
    arch_penalty = _cell_weighted_penalty(findings, total_cells, "Architecture", max_penalty=40.0)
    arch_score = max(0.0, 100.0 - arch_penalty)
    arch_detail = f"{len(arch_findings)} architecture findings (e.g. TEXT stored in Calc modules)."

    gov_findings = [f for f in findings if f.category == "Governance"]
    gov_penalty = min(40.0, len(gov_findings) * 0.3)
    gov_score = max(0.0, 100.0 - gov_penalty)
    gov_detail = f"{len(gov_findings)} complex line items missing documentation."

    dims = [
        HealthDimension("size", "Model Size Score", round(size_score, 1), _WEIGHTS["size"], size_detail),
        HealthDimension("formula_efficiency", "Formula Efficiency Score", round(formula_score, 1), _WEIGHTS["formula_efficiency"], formula_detail),
        HealthDimension("calculation_performance", "Calculation Performance Score", round(perf_score, 1), _WEIGHTS["calculation_performance"], perf_detail),
        HealthDimension("dimensionality", "Dimensionality Score", round(dim_score, 1), _WEIGHTS["dimensionality"], dim_detail),
        HealthDimension("architecture", "Model Architecture Score", round(arch_score, 1), _WEIGHTS["architecture"], arch_detail),
        HealthDimension("governance", "Documentation / Governance Score", round(gov_score, 1), _WEIGHTS["governance"], gov_detail),
    ]
    overall = sum(d.score * d.weight for d in dims) / sum(d.weight for d in dims)

    # Optimization Opportunity is reported separately -- it's an upside
    # measure (higher = more available headroom), not a health measure,
    # so it is not folded into the weighted overall average above.
    size_and_perf_findings = [f for f in findings if f.affects_size or f.affects_performance]
    if size.cell_count_available and total_cells > 0:
        opp_cells = sum((f.cell_impact or 0.0) for f in size_and_perf_findings)
        optimization_opportunity = round(min(100.0, opp_cells / total_cells * 100.0), 1)
    else:
        optimization_opportunity = round(min(100.0, len(size_and_perf_findings) * 1.2), 1)
    dims.append(HealthDimension(
        "optimization_opportunity", "Potential Optimization Score", optimization_opportunity,
        0.0, "Share of model cells touched by at least one size- or performance-affecting finding."
    ))

    return HealthScoreBreakdown(overall=round(overall, 1), band=_band(overall), dimensions=dims)
