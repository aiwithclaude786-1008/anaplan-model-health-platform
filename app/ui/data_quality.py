# app/ui/data_quality.py -- master spec section 18.
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult


def render_data_quality(result: AnalysisResult):
    dq = result.data_quality
    st.header("Data Quality")
    st.caption("Checked before analysis so every downstream number can be trusted.")

    st.metric("Data Quality Score", f"{dq.score:.0f}/100")
    st.caption(f"{dq.total_rows:,} rows scanned.")

    if not dq.issues:
        st.success("No data quality issues detected.")
        return

    df = pd.DataFrame([{"Check": i.check, "Severity": i.severity, "Rows affected": i.count, "Detail": i.detail}
                        for i in dq.issues])
    st.dataframe(df, width="stretch", hide_index=True)
