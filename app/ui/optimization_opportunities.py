# app/ui/optimization_opportunities.py -- master spec sections 6 + 12.
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult
from app.ui.components import severity_badge, confidence_badge


def _opps_table(opps):
    return pd.DataFrame([{
        "Priority": o.priority, "Module": o.module, "Item(s)": o.line_item, "Issue": o.issue,
        "Current impact": o.current_impact, "Recommended action": o.recommended_action,
        "Expected benefit": o.expected_benefit, "Confidence": o.confidence, "Effort": o.effort,
        "Validation required": "Yes" if o.validation_required else "No", "Severity": o.severity,
    } for o in opps])


def render_optimization_opportunities(result: AnalysisResult):
    st.header("Top 10 Optimization Opportunities")
    st.caption("Prioritized by Impact x Confidence / Effort across every category -- size, performance, "
               "architecture, and governance.")

    if not result.top_opportunities:
        st.success("No optimization opportunities identified at the current thresholds.")
    else:
        for o in result.top_opportunities:
            with st.expander(f"#{o.priority} -- {o.issue} ({o.module})", expanded=(o.priority <= 3)):
                st.markdown(f"{severity_badge(o.severity)} &nbsp; {confidence_badge(o.confidence)}", unsafe_allow_html=True)
                st.markdown(f"**Current impact:** {o.current_impact}")
                st.markdown(f"**Recommended action:** {o.recommended_action}")
                st.markdown(f"**Expected benefit:** {o.expected_benefit}")
                st.markdown(f"**Effort:** {o.effort}  |  **Validation required:** {'Yes' if o.validation_required else 'No'}")

    st.divider()
    st.header("Size Reduction Opportunity Engine")
    st.caption("Section 6 -- structured, per-module findings with confidence-labeled potential impact. "
               "Never claims an exact GB saving unless the underlying cell-count arithmetic supports it.")
    if not result.size_opportunities:
        st.info("No size-affecting opportunities identified.")
        return
    st.dataframe(_opps_table(result.size_opportunities), width="stretch", hide_index=True)
