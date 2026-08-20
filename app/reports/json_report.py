# app/reports/json_report.py -- master spec section 27 (AI-ready structure).
from __future__ import annotations

import json

from app.analysis.pipeline import AnalysisResult
from app.analysis.size_analysis import cells_to_gb


def build_json_report(result: AnalysisResult, client_name: str = "", model_label: str = "") -> bytes:
    size = result.size
    health = result.health
    payload = {
        "client": client_name or None,
        "model": model_label or None,
        "health": {
            "overall": health.overall, "band": health.band,
            "dimensions": [{"key": d.key, "label": d.label, "score": d.score, "detail": d.detail} for d in health.dimensions],
        },
        "size": {
            "total_cells": size.total_cells if size.cell_count_available else None,
            "estimated_gb": round(cells_to_gb(size.total_cells), 2) if size.cell_count_available else None,
            "modules": size.modules_count, "line_items": size.line_items_count,
            "top_n_pct": size.top_n_pct,
        },
        "data_quality": {"score": result.data_quality.score,
                          "issues": [{"check": i.check, "severity": i.severity, "count": i.count, "detail": i.detail}
                                     for i in result.data_quality.issues]},
        "findings": [f.to_dict() for f in result.findings],
        "top_opportunities": [{
            "priority": o.priority, "module": o.module, "issue": o.issue,
            "recommended_action": o.recommended_action, "expected_benefit": o.expected_benefit,
            "confidence": o.confidence, "effort": o.effort, "validation_required": o.validation_required,
        } for o in result.top_opportunities],
        "action_plan": [{"horizon": i.horizon, "title": i.title, "detail": i.detail} for i in result.action_plan],
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")
