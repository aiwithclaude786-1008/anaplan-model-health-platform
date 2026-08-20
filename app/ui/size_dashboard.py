# app/ui/size_dashboard.py -- master spec section 5.
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult
from app.analysis.size_analysis import cells_to_gb
from app.ui.components import kpi_row, fmt_num, fmt_pct, section_header


def render_size_dashboard(result: AnalysisResult):
    size = result.size
    st.header("Model Size")
    st.caption("Where the space lives, and how concentrated it is.")

    if not size.cell_count_available:
        st.info("This export has no Cell Count column -- size analysis needs one to run.")
        return

    kpi_row([
        (fmt_num(size.total_cells), "Total cells", None),
        (f"{cells_to_gb(size.total_cells):,.2f} GB", "Estimated model size", "Cells / 132,000,000 -- a common Anaplan cells-per-GB rule of thumb."),
        (size.largest_module or "N/A", "Largest module", None),
        (fmt_pct(size.top_n_pct), f"Top {size.top_n_actual} modules' share", None),
        (fmt_num(size.avg_module_size), "Avg module size (cells)", None),
        (fmt_num(size.median_module_size), "Median module size (cells)", None),
    ])

    if size.neg_cell_count_rows:
        st.warning(f"{size.neg_cell_count_rows} row(s) have a negative Cell Count -- excluded from totals above.")

    st.subheader("Pareto: cell concentration by module")
    df = pd.DataFrame([{
        "Rank": r.rank, "Module": r.module, "Cell Count": r.cell_count, "% of Model": r.pct_of_model * 100,
        "Cumulative %": r.cumulative_pct * 100, "Line Items": r.line_items,
        "Avg Cells / Item": r.avg_cells_per_item, "Type": r.module_type, "Status": r.status,
        "Primary Lever": r.primary_lever,
    } for r in size.module_rows])
    st.dataframe(df, width="stretch", hide_index=True)

    st.bar_chart(df.set_index("Module")["Cell Count"].head(20), width="stretch")

    top20_n = max(1, round(len(df) * 0.2))
    top20_pct = df.head(top20_n)["Cell Count"].sum() / size.total_cells * 100 if size.total_cells else 0
    st.info(f"Top 20% of modules ({top20_n} of {len(df)}) hold **{top20_pct:.0f}%** of total model cells.")

    section_header("Status bands", "CRITICAL/HIGH/WATCH/OK reflect each module's position in the cumulative "
                                     "cell-count Pareto -- modules pushing the running total past 50% are CRITICAL, "
                                     "past 80% are HIGH, past 95% WATCH, the remainder OK.")
