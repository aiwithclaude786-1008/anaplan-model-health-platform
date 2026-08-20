# app/ui/formula_detail.py -- master spec section 9.
from __future__ import annotations

from typing import List

import streamlit as st

from app.models.schemas import Finding
from app.rules.registry import get_rule
from app.ui.components import format_anaplan_formula, severity_badge, confidence_badge, render_badges_html


def render_formula_detail(module: str, line_item: str, formula: str, findings: List[Finding],
                           cell_count: float = None, impact_score: float = None):
    st.markdown(f"**Module:** {module}  \n**Line Item:** {line_item}")
    if cell_count is not None:
        st.markdown(f"**Cell Count:** {cell_count:,.0f}" + (f"  \n**Formula Impact Score:** {impact_score:.0f}/100" if impact_score is not None else ""))

    with st.expander("Formula", expanded=True):
        st.code(format_anaplan_formula(formula), language="text")

    if not findings:
        st.success("No rule violations detected on this line item.")
        return

    st.markdown("#### Detected patterns")
    for f in findings:
        render_badges_html([severity_badge(f.severity), confidence_badge(f.confidence)])
        st.markdown(f"**{f.name}** ({f.rule_id})")
        rule = get_rule(f.rule_id)
        if rule and rule.why_it_matters:
            st.caption(f"Why it matters: {rule.why_it_matters}")
        st.markdown(f"Recommended redesign: {f.recommendation}")
        st.divider()

    st.markdown("#### Expected benefit")
    benefits = []
    if any(f.affects_performance for f in findings):
        benefits.append("Lower calculation complexity")
        benefits.append("Better dependency management")
    if any(f.affects_size for f in findings):
        benefits.append("Reduced model footprint")
    benefits.append("Easier maintenance")
    st.markdown("\n".join(f"- {b}" for b in dict.fromkeys(benefits)))
