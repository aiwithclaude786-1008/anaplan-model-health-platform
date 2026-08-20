# app/analysis/action_plan.py
# ============================================================
# Master spec section 13 -- a 30/60/90 day plan built from the
# same opportunities already ranked by optimization_engine, not a
# separate, disconnected narrative.
# ============================================================
from __future__ import annotations

from typing import List

from app.models.schemas import ActionPlanItem, OptimizationOpportunity

_HORIZON_BY_EFFORT = {"Low": "0-30", "Medium": "31-60", "High": "61-90"}


def build_action_plan(opportunities: List[OptimizationOpportunity], limit_per_horizon: int = 8) -> List[ActionPlanItem]:
    buckets = {"0-30": [], "31-60": [], "61-90": []}
    for opp in opportunities:
        horizon = _HORIZON_BY_EFFORT.get(opp.effort, "31-60")
        if len(buckets[horizon]) >= limit_per_horizon:
            continue
        buckets[horizon].append(ActionPlanItem(
            horizon=horizon,
            title=f"{opp.issue} -- {opp.module}",
            detail=f"{opp.recommended_action} ({opp.current_impact}; confidence: {opp.confidence})",
            source_module=opp.module,
            source_rule=opp.issue,
        ))

    plan: List[ActionPlanItem] = []
    for horizon in ("0-30", "31-60", "61-90"):
        plan.extend(buckets[horizon])
    return plan
