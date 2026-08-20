# app/ui/action_plan.py -- master spec section 13.
from __future__ import annotations

import streamlit as st

from app.analysis.pipeline import AnalysisResult

_HORIZON_LABEL = {"0-30": "0-30 Days -- Quick wins", "31-60": "31-60 Days -- Structural improvements",
                   "61-90": "61-90 Days -- Architecture improvements"}


def render_action_plan(result: AnalysisResult):
    st.header("Consultant Action Plan")
    st.caption("Auto-generated from this model's actual findings, sequenced by effort.")

    if not result.action_plan:
        st.success("No action items -- nothing was flagged at the current thresholds.")
        return

    for horizon in ("0-30", "31-60", "61-90"):
        items = [i for i in result.action_plan if i.horizon == horizon]
        st.subheader(_HORIZON_LABEL[horizon])
        if not items:
            st.caption("Nothing queued for this horizon.")
            continue
        for item in items:
            st.markdown(f"- **{item.title}** -- {item.detail}")
