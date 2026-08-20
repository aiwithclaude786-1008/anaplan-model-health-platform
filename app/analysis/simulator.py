# app/analysis/simulator.py -- master spec section 14.
# ============================================================
# Before/After Simulator: a consultant selects opportunities from
# the Size Reduction Opportunity Engine and sees a projected,
# step-by-step reduction. Every step is driven by the SAME
# cell-impact numbers already computed for that opportunity
# (analysis/optimization_engine.py) -- nothing here invents a new
# figure. The percentage applied per step comes from a documented,
# per-rule-category range (not a measurement), so every result is
# surfaced as an Estimate/Potential range, never a guaranteed
# saving, per section 26.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.models.schemas import OptimizationOpportunity
from app.analysis.size_analysis import cells_to_gb

# (low%, high%) indicative reduction range applied to the cell impact
# already attributed to that finding. Ranges reflect the mechanism:
# re-dimensioning a full-grain cluster removes real duplicated cells;
# a Time Range mirrors the real Tridant report's own "~30% indicative
# saving" convention for unscoped-calendar items; TEXT/subsidiary-view
# fixes mostly reduce memory density rather than cell count, so their
# range is narrower and conservative.
_REDUCTION_RANGE_BY_RULE = {
    "RULE-SIZE-001": (25.0, 40.0),
    "RULE-DIM-002": (20.0, 35.0),
    "RULE-DIM-001": (10.0, 20.0),
    "RULE-ARCH-001": (10.0, 20.0),
}
_DEFAULT_RANGE = (5.0, 15.0)


@dataclass
class SimulationStep:
    label: str
    rule_id: str
    cells_before: float
    cells_after: float
    reduction_low_pct: float
    reduction_high_pct: float


@dataclass
class SimulationResult:
    starting_cells: float
    starting_gb: float
    ending_cells_low: float   # using the high end of each range (most optimistic -> lowest ending size)
    ending_cells_high: float  # using the low end of each range (most conservative -> highest ending size)
    steps: List[SimulationStep]
    total_reduction_pct_low: float
    total_reduction_pct_high: float


def _extract_rule_id(issue_label: str) -> str:
    if "(" in issue_label and issue_label.endswith(")"):
        return issue_label.rsplit("(", 1)[1][:-1]
    return ""


def simulate(selected: List[OptimizationOpportunity], starting_cells: float) -> SimulationResult:
    # "conservative" applies each step's low_pct (the smaller, safer
    # reduction) so it ends with MORE cells remaining; "optimistic"
    # applies high_pct so it ends with FEWER cells remaining. The
    # step-by-step waterfall shown in the UI follows the conservative
    # path (cells_after below), while the headline range spans both.
    cells_conservative = starting_cells
    cells_optimistic = starting_cells
    steps: List[SimulationStep] = []

    for opp in selected:
        rule_id = _extract_rule_id(opp.issue)
        low_pct, high_pct = _REDUCTION_RANGE_BY_RULE.get(rule_id, _DEFAULT_RANGE)
        cell_impact = opp.cell_impact
        if cell_impact is None or cell_impact <= 0:
            continue
        cell_impact = min(cell_impact, cells_conservative)  # never remove more than what's left

        before = cells_conservative
        cells_conservative = max(0.0, cells_conservative - cell_impact * (low_pct / 100.0))
        cells_optimistic = max(0.0, cells_optimistic - cell_impact * (high_pct / 100.0))

        steps.append(SimulationStep(
            label=f"{opp.issue} -- {opp.module}", rule_id=rule_id,
            cells_before=before, cells_after=cells_conservative,
            reduction_low_pct=low_pct, reduction_high_pct=high_pct,
        ))

    total_reduction_low = (starting_cells - cells_conservative) / starting_cells * 100.0 if starting_cells > 0 else 0.0
    total_reduction_high = (starting_cells - cells_optimistic) / starting_cells * 100.0 if starting_cells > 0 else 0.0

    return SimulationResult(
        starting_cells=starting_cells, starting_gb=cells_to_gb(starting_cells),
        ending_cells_low=cells_optimistic, ending_cells_high=cells_conservative,
        steps=steps, total_reduction_pct_low=total_reduction_low, total_reduction_pct_high=total_reduction_high,
    )
