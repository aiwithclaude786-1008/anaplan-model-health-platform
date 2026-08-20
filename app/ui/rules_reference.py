# app/ui/rules_reference.py -- master spec section 17.
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.rules.registry import get_all_rules
from app.rules.thresholds import RuleThresholds


def render_rules_reference(thresholds: RuleThresholds, active_rule_ids: set = None):
    st.header("Rules Reference")
    st.caption("Every rule the platform knows about -- ID, category, description, severity, recommendation, "
               "confidence, and whether it affects size and/or performance. Rules whose required column isn't "
               "in the currently loaded file are shown greyed out (not run) rather than silently skipped.")

    rules = get_all_rules(thresholds)
    rows = []
    for r in rules:
        rows.append({
            "Rule ID": r.rule_id, "Name": r.name, "Category": r.category, "Severity": r.severity,
            "Description": r.description, "Recommendation": r.recommendation, "Confidence": r.confidence,
            "Affects Size": "Yes" if r.affects_size else "", "Affects Performance": "Yes" if r.affects_performance else "",
            "Active on loaded file": "Yes" if (active_rule_ids is None or r.rule_id in active_rule_ids) else "No (column not in export)",
            "Doc reference": r.doc_ref,
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True, height=560)
