# app/ui/dependency_view.py -- master spec section 10.
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult


def render_dependency_view(result: AnalysisResult):
    dep = result.dependency
    st.header("Dependency / Daisy-Chain Analysis")

    if not dep.available:
        st.info(dep.note or "Not available in current dataset.")
        return

    badge = "Measured (from Referenced By column)" if dep.source == "measured" else "Inferred from formula text references"
    st.caption(badge)
    st.warning(dep.note) if dep.source == "inferred" else st.caption(dep.note)

    c1, c2 = st.columns(2)
    c1.metric("Longest dependency chain", dep.longest_chain_length)
    c2.metric("Modules in graph", len(set(dep.module_in_degree) | set(dep.module_out_degree)))

    if dep.longest_chain_example:
        st.markdown("**Example chain:** " + " -> ".join(dep.longest_chain_example))

    st.subheader("Bottleneck modules (highest inbound references)")
    bottleneck_df = pd.DataFrame([
        {"Module": m, "Inbound refs": dep.module_in_degree.get(m, 0), "Outbound refs": dep.module_out_degree.get(m, 0)}
        for m in dep.top_bottleneck_modules
    ])
    if not bottleneck_df.empty:
        st.dataframe(bottleneck_df, width="stretch", hide_index=True)

    st.subheader("Module-to-module edges")
    edges_df = pd.DataFrame([{"From": e.from_module, "To": e.to_module, "Weight": e.weight} for e in dep.edges])
    st.dataframe(edges_df.head(100), width="stretch", hide_index=True)
