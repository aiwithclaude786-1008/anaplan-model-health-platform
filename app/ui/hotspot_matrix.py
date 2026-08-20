# app/ui/hotspot_matrix.py -- master spec section 11.
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult

_QUADRANT_DESC = {
    "Critical Optimization": "High complexity + high cell count -- fix first.",
    "Size Risk": "Low complexity + high cell count -- a simple formula running over too many cells.",
    "Watch": "High complexity + low cell count -- not urgent today, but expensive to maintain.",
    "Low Priority": "Low complexity + low cell count.",
}


def render_hotspot_matrix(result: AnalysisResult):
    st.header("Calculation Hotspot Matrix")
    st.caption("Formula complexity vs. cell count. The top-right quadrant is where optimization effort pays off fastest.")

    if not result.hotspots:
        st.info("Hotspot matrix needs a Cell Count column -- not available in this export.")
        return

    df = pd.DataFrame([{
        "Module": p.module, "Line Item": p.line_item, "Complexity": p.complexity,
        "Cell Count": p.cell_count, "Quadrant": p.quadrant, "Impact Score": p.impact_score,
    } for p in result.hotspots])

    st.scatter_chart(df, x="Complexity", y="Cell Count", color="Quadrant", size="Impact Score",
                      width="stretch", height=420)

    counts = df["Quadrant"].value_counts()
    cols = st.columns(4)
    for col, q in zip(cols, ["Critical Optimization", "Size Risk", "Watch", "Low Priority"]):
        col.metric(q, int(counts.get(q, 0)), help=_QUADRANT_DESC[q])

    st.subheader("Critical Optimization quadrant")
    critical = df[df["Quadrant"] == "Critical Optimization"].sort_values("Impact Score", ascending=False)
    if critical.empty:
        st.success("No line items fall in the Critical Optimization quadrant.")
    else:
        st.dataframe(critical.head(100), width="stretch", hide_index=True)
