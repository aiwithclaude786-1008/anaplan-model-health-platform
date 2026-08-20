# app/ui/formula_optimization_center.py -- master spec section 8.
from __future__ import annotations

from collections import defaultdict

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult
from app.ui.formula_detail import render_formula_detail


def render_formula_optimization_center(result: AnalysisResult):
    st.header("Formula Optimization Center")
    st.caption("Every flagged line item, ranked by Formula Impact Score (complexity x cell exposure x performance risk).")

    findings_by_row = defaultdict(list)
    for f in result.findings:
        findings_by_row[(f.module, f.line_item)].append(f)

    if not findings_by_row:
        st.success("No rule violations detected at the current thresholds.")
        return

    feats = result.feats
    rows = []
    for (module, line_item), fs in findings_by_row.items():
        match = feats[(feats["module"] == module) & (feats["line_item"] == line_item)]
        cell_count = float(match["cell_count"].iloc[0]) if len(match) and pd.notna(match["cell_count"].iloc[0]) else None
        impact = float(match["impact_score"].iloc[0]) if len(match) else 0.0
        formula = fs[0].formula
        severities = {f.severity for f in fs}
        top_sev = "critical" if "critical" in severities else "high" if "high" in severities else \
                  "medium" if "medium" in severities else "low"
        rows.append({
            "Module": module, "Line Item": line_item, "Cell Count": cell_count, "Impact Score": impact,
            "Severity": top_sev, "Issues": ", ".join(sorted({f.name for f in fs})),
            "Formula Type": ", ".join(sorted({f.category for f in fs})),
            "Recommended Refactor": fs[0].recommendation,
        })
    df = pd.DataFrame(rows).sort_values("Impact Score", ascending=False)

    c1, c2, c3 = st.columns(3)
    module_filter = c1.multiselect("Module", sorted(df["Module"].unique()))
    severity_filter = c2.multiselect("Severity", ["critical", "high", "medium", "low"])
    search = c3.text_input("Search line item / module")

    filtered = df.copy()
    if module_filter:
        filtered = filtered[filtered["Module"].isin(module_filter)]
    if severity_filter:
        filtered = filtered[filtered["Severity"].isin(severity_filter)]
    if search:
        s = search.lower()
        filtered = filtered[filtered["Module"].str.lower().str.contains(s) | filtered["Line Item"].str.lower().str.contains(s)]

    filtered.insert(0, "Priority", range(1, len(filtered) + 1))
    st.dataframe(filtered, width="stretch", hide_index=True, height=420)

    st.divider()
    st.subheader("Line item detail")
    if filtered.empty:
        st.info("No rows match the current filters.")
        return

    options = [f"{m} | {li}" for m, li in zip(filtered["Module"], filtered["Line Item"])]
    selected = st.selectbox("Select a line item", options=options)
    if selected:
        sel_module, sel_item = [s.strip() for s in selected.split("|", 1)]
        fs = findings_by_row.get((sel_module, sel_item), [])
        match = feats[(feats["module"] == sel_module) & (feats["line_item"] == sel_item)]
        cell_count = float(match["cell_count"].iloc[0]) if len(match) and pd.notna(match["cell_count"].iloc[0]) else None
        impact = float(match["impact_score"].iloc[0]) if len(match) else None
        formula = fs[0].formula if fs else (match["formula"].iloc[0] if len(match) else "")
        render_formula_detail(sel_module, sel_item, formula, fs, cell_count, impact)
