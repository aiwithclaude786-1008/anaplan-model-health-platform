# app/ui/dimensionality_dashboard.py -- master spec section 7.
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult
from app.ui.components import kpi_row, fmt_num, fmt_pct


def render_dimensionality_dashboard(result: AnalysisResult):
    dim = result.dimensionality
    st.header("Dimensionality")
    st.caption("Structural sparsity, subsidiary views, and unscoped time ranges.")

    if dim.waste_score is None:
        st.warning(dim.note)
        return

    kpi_row([
        (fmt_pct(dim.waste_score), "Dimensionality waste score", dim.note),
        (fmt_num(dim.total_subsidiary_view_items), "Subsidiary-view line items",
         "Line items dimensioned differently from their own module (Applies To override)."),
        (fmt_num(dim.total_full_calendar_items), "Items on full Model Calendar",
         "Line items left on the unscoped/full calendar instead of a Time Range."),
        (fmt_num(dim.total_full_calendar_cells), "Cells on full calendar", None),
    ])

    st.caption(
        "Theoretical cell space (product of list cardinalities) isn't derivable from a module-list export -- "
        "this view uses only what the export actually carries (Applies To / Time Range), consistent with the "
        "platform's FACT-vs-ESTIMATE principle."
    )

    if dim.module_rows:
        df = pd.DataFrame([{
            "Module": r.module, "Distinct Applies To": r.distinct_applies_to,
            "Subsidiary-view items": r.subsidiary_view_items, "Full-calendar items": r.full_calendar_items,
            "Full-calendar cells": r.full_calendar_cells,
        } for r in dim.module_rows])
        st.subheader("By module")
        st.dataframe(df.head(50), width="stretch", hide_index=True)
