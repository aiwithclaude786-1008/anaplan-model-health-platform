# app/reports/csv_report.py -- master spec section 20, optimization backlog CSV.
from __future__ import annotations

import pandas as pd

from app.analysis.pipeline import AnalysisResult


def build_optimization_backlog_csv(result: AnalysisResult) -> bytes:
    opps = result.top_opportunities + result.size_opportunities
    df = pd.DataFrame([{
        "Priority": o.priority, "Module": o.module, "Item(s)": o.line_item, "Issue": o.issue,
        "Current Impact": o.current_impact, "Recommended Action": o.recommended_action,
        "Expected Benefit": o.expected_benefit, "Confidence": o.confidence, "Effort": o.effort,
        "Validation Required": o.validation_required, "Severity": o.severity,
    } for o in opps])
    return df.to_csv(index=False).encode("utf-8")


def build_findings_csv(result: AnalysisResult) -> bytes:
    df = pd.DataFrame([f.to_dict() for f in result.findings])
    return df.to_csv(index=False).encode("utf-8")
