# app/models/schemas.py
# ============================================================
# Shared data model for the platform. Every analysis module
# produces these dataclasses; every UI page and report reads
# them. Keeping the shape stable here is what makes the engine
# "AI-ready" per the master spec (section 27) -- a future LLM
# layer can consume Finding.to_dict() without touching analysis
# code.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

# Confidence vocabulary used everywhere a number or claim is
# surfaced to the user (master spec section 25/26).
CONFIDENCE_MEASURED = "Measured"
CONFIDENCE_ESTIMATED = "Estimated"
CONFIDENCE_POTENTIAL = "Potential"
CONFIDENCE_REQUIRES_VALIDATION = "Requires validation"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@dataclass
class Finding:
    """One rule violation on one line item. Mirrors section 27's schema exactly."""
    rule_id: str
    category: str
    module: str
    line_item: str
    formula: str
    severity: str  # critical | high | medium | low
    name: str = ""
    cell_impact: Optional[float] = None
    performance_impact: Optional[float] = None
    size_impact: Optional[float] = None
    recommendation: str = ""
    confidence: str = CONFIDENCE_ESTIMATED
    estimated_benefit: Optional[str] = None
    validation_required: bool = True
    affects_size: bool = False
    affects_performance: bool = False
    row_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModuleSizeInfo:
    module: str
    cell_count: float
    size_gb: float
    line_item_count: int = 0
    pct_of_model: Optional[float] = None


@dataclass
class OptimizationOpportunity:
    priority: int
    module: str
    line_item: str
    issue: str
    current_impact: str
    recommended_action: str
    expected_benefit: str
    confidence: str
    effort: str  # Low | Medium | High
    validation_required: bool
    score: float = 0.0
    severity: str = "medium"
    cell_impact: Optional[float] = None  # raw cell count behind current_impact's display string, for simulator use


@dataclass
class HealthDimension:
    key: str
    label: str
    score: float
    weight: float
    detail: str = ""


@dataclass
class HealthScoreBreakdown:
    overall: float
    band: str
    dimensions: List[HealthDimension] = field(default_factory=list)

    def dimension(self, key: str) -> Optional[HealthDimension]:
        for d in self.dimensions:
            if d.key == key:
                return d
        return None


@dataclass
class ActionPlanItem:
    horizon: str  # "0-30" | "31-60" | "61-90"
    title: str
    detail: str
    source_module: Optional[str] = None
    source_rule: Optional[str] = None


@dataclass
class DependencyEdge:
    from_module: str
    to_module: str
    weight: int
