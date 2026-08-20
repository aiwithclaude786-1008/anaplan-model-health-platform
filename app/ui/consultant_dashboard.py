# app/ui/consultant_dashboard.py -- master spec section 16.
from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult

# Same relative cost weights as the original app.py's "Top 10 Worst
# Performance / Heavy Anaplan Functions" table.
_FUNC_COST = {
    "POST + LOOKUP (nested)": 15, "POST + SUM (nested)": 13, "POST inside IF": 14,
    "TIMESUM": 12, "POST": 11, "LOOKUP": 9, "SUM": 8, "OFFSET / MOVINGSUM": 8,
    "CUMULATE": 7, "SELECT": 6, "FINDITEM": 6, "RANK": 5, "IF": 4,
}


def render_consultant_dashboard(result: AnalysisResult):
    st.header("Consultant Dashboard")
    st.caption("Architect-facing rankings and distributions -- for a step-by-step guided view, use the other pages.")

    feats = result.feats

    st.subheader("Module size ranking")
    if result.size.cell_count_available:
        df = pd.DataFrame([{"Module": r.module, "Cell Count": r.cell_count, "Status": r.status} for r in result.size.module_rows])
        st.dataframe(df.head(30), width="stretch", hide_index=True)
    else:
        st.info("No Cell Count column -- module size ranking unavailable.")

    st.subheader("Formula risk ranking (by rule count)")
    rule_counts = Counter(f.rule_id for f in result.findings)
    if rule_counts:
        names = {f.rule_id: f.name for f in result.findings}
        risk_df = pd.DataFrame([{"Rule": names[rid], "Rule ID": rid, "Findings": n} for rid, n in rule_counts.most_common(15)])
        st.dataframe(risk_df, width="stretch", hide_index=True)
        st.bar_chart(risk_df.set_index("Rule")["Findings"])
    else:
        st.success("No findings at the current thresholds.")

    st.subheader("Function usage distribution")
    usage = {
        "IF": int(feats["count_if"].sum()), "LOOKUP": int(feats["count_lookup"].sum()),
        "SUM": int(feats["count_sum"].sum()), "SELECT": int(feats["count_select"].sum()),
        "FINDITEM": int(feats["count_finditem"].sum()), "RANK": int(feats["count_rank"].sum()),
        "CUMULATE": int(feats["count_cumulate"].sum()), "OFFSET / MOVINGSUM": int(feats["count_offsetlike"].sum()),
        "TIMESUM": int(feats["has_timesum"].sum()), "POST": int(feats["has_post"].sum()),
        "POST + LOOKUP (nested)": int(feats["has_post_lookup_nested"].sum()),
        "POST + SUM (nested)": int(feats["has_post_sum_nested"].sum()),
        "POST inside IF": int(feats["has_post_inside_if"].sum()),
    }
    func_df = pd.DataFrame([
        {"Function / Pattern": k, "Usage Count": v, "Cost Weight": _FUNC_COST.get(k, 1),
         "Total Impact Score": v * _FUNC_COST.get(k, 1)}
        for k, v in usage.items() if v > 0
    ]).sort_values("Total Impact Score", ascending=False)
    if not func_df.empty:
        st.dataframe(func_df.head(10), width="stretch", hide_index=True)
        st.bar_chart(func_df.set_index("Function / Pattern")["Total Impact Score"].head(10))

    st.subheader("Formula complexity distribution")
    st.bar_chart(feats["func_density_count"].value_counts().sort_index())

    st.subheader("Cell concentration")
    if result.size.cell_count_available:
        st.metric(f"Top {result.size.top_n_actual} modules' share of total cells", f"{result.size.top_n_pct:.0f}%")
