# app/analysis/optimization_engine.py
# ============================================================
# Master spec sections 6, 11, 12: size reduction opportunities,
# the Top 10 prioritized list (Impact x Confidence / Effort), and
# the data behind the Calculation Hotspot Matrix.
# ============================================================
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import List

import pandas as pd

from app.models.schemas import Finding, OptimizationOpportunity

# Effort is a structural judgment about how invasive the fix is, not
# derived from the data -- documented per rule category so it's
# transparent and easy to tune later.
_EFFORT_BY_CATEGORY = {
    "Formula": "Low",
    "Governance": "Low",
    "Architecture": "Medium",
    "Dimensionality": "Medium",
    "Size": "High",
    "Performance": "Medium",
}
_EFFORT_WEIGHT = {"Low": 1.0, "Medium": 1.8, "High": 2.6}
_CONFIDENCE_WEIGHT = {"Measured": 1.0, "Estimated": 0.75, "Potential": 0.55, "Requires validation": 0.4}


def build_size_reduction_opportunities(findings: List[Finding], total_cells: float) -> List[OptimizationOpportunity]:
    """One structured opportunity per (module, rule) group -- mirrors
    the master spec's worked example (module, current size, problem,
    recommendation, potential impact, potential reduction range,
    confidence, validation-required)."""
    groups = defaultdict(list)
    for f in findings:
        if f.affects_size:
            groups[(f.module, f.rule_id)].append(f)

    opportunities = []
    for (module, rule_id), items in groups.items():
        cell_impact = sum((f.cell_impact or 0.0) for f in items)
        pct = (cell_impact / total_cells * 100.0) if total_cells > 0 else None
        sample = items[0]
        effort = _EFFORT_BY_CATEGORY.get(sample.category, "Medium")
        conf_weight = _CONFIDENCE_WEIGHT.get(sample.confidence, 0.6)
        impact_score = (pct or (len(items) * 0.5)) * conf_weight / _EFFORT_WEIGHT.get(effort, 1.8)
        current_impact = f"{cell_impact:,.0f} cells" + (f" ({pct:.1f}% of model)" if pct is not None else "")
        opportunities.append(OptimizationOpportunity(
            priority=0, module=module, line_item=f"{len(items)} line item(s)",
            issue=f"{sample.name} ({rule_id})",
            current_impact=current_impact,
            recommended_action=sample.recommendation,
            expected_benefit="Potentially significant -- requires model validation." if pct is None or pct < 1
                              else f"Estimated size reduction opportunity: ~{min(40, max(5, pct)):.0f}% of this finding's cell footprint.",
            confidence=sample.confidence,
            effort=effort,
            validation_required=sample.validation_required,
            score=round(impact_score, 3),
            severity=sample.severity,
            cell_impact=cell_impact,
        ))
    opportunities.sort(key=lambda o: o.score, reverse=True)
    for i, o in enumerate(opportunities, start=1):
        o.priority = i
    return opportunities


def build_top_opportunities(findings: List[Finding], total_cells: float, limit: int = 10) -> List[OptimizationOpportunity]:
    """Top N across ALL categories (size + performance + architecture +
    governance), scored by Impact x Confidence / Effort per section 12."""
    groups = defaultdict(list)
    for f in findings:
        groups[(f.module, f.rule_id)].append(f)

    opportunities = []
    for (module, rule_id), items in groups.items():
        sample = items[0]
        cell_impact = sum((f.cell_impact or 0.0) for f in items if f.cell_impact is not None)
        pct = (cell_impact / total_cells * 100.0) if total_cells > 0 and cell_impact else None
        effort = _EFFORT_BY_CATEGORY.get(sample.category, "Medium")
        conf_weight = _CONFIDENCE_WEIGHT.get(sample.confidence, 0.6)
        severity_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(sample.severity, 1)
        impact_component = (pct if pct is not None else len(items) * 0.4) * severity_weight
        score = impact_component * conf_weight / _EFFORT_WEIGHT.get(effort, 1.8)

        current_impact = f"{len(items)} line item(s)"
        if pct is not None:
            current_impact += f", {cell_impact:,.0f} cells ({pct:.1f}% of model)"

        opportunities.append(OptimizationOpportunity(
            priority=0, module=module, line_item=f"{len(items)} line item(s)",
            issue=f"{sample.name} ({rule_id})",
            current_impact=current_impact,
            recommended_action=sample.recommendation,
            expected_benefit=("Lower calculation complexity, easier maintenance" if sample.affects_performance
                               else "Reduced model footprint") + (f" -- ~{pct:.1f}% of model cells affected" if pct else ""),
            confidence=sample.confidence,
            effort=effort,
            validation_required=sample.validation_required,
            score=round(score, 3),
            severity=sample.severity,
            cell_impact=cell_impact if cell_impact else None,
        ))

    opportunities.sort(key=lambda o: o.score, reverse=True)
    top = opportunities[:limit]
    for i, o in enumerate(top, start=1):
        o.priority = i
    return top


@dataclass
class HotspotPoint:
    module: str
    line_item: str
    complexity: float  # 0-100
    cell_count: float
    quadrant: str
    impact_score: float


def build_hotspot_matrix(feats: pd.DataFrame, impact_score: pd.Series) -> List[HotspotPoint]:
    complexity = (
        feats["func_density_count"].clip(upper=15) / 15.0 * 60.0
        + feats["count_if"].clip(upper=10) / 10.0 * 40.0
    )
    cell = feats["cell_count"].fillna(0)
    complexity_median = complexity.median() if len(complexity) else 0.0
    cell_median = cell[cell > 0].median() if (cell > 0).any() else 0.0

    points = []
    for i in feats.index:
        c = float(complexity.at[i])
        n = float(cell.at[i])
        if c >= complexity_median and n >= cell_median and n > 0:
            quadrant = "Critical Optimization"
        elif c >= complexity_median:
            quadrant = "Watch"
        elif n >= cell_median and n > 0:
            quadrant = "Size Risk"
        else:
            quadrant = "Low Priority"
        points.append(HotspotPoint(
            module=str(feats.at[i, "module"]), line_item=str(feats.at[i, "line_item"]),
            complexity=round(c, 1), cell_count=n, quadrant=quadrant,
            impact_score=float(impact_score.at[i]) if i in impact_score.index else 0.0,
        ))
    return points
