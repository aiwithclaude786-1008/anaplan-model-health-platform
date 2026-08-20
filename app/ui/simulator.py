# app/ui/simulator.py -- master spec section 14.
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analysis.pipeline import AnalysisResult
from app.analysis.simulator import simulate
from app.analysis.size_analysis import cells_to_gb


def render_simulator(result: AnalysisResult):
    st.header("Before / After Simulator")
    st.caption("Select opportunities from the Size Reduction Opportunity Engine to see a projected, "
               "step-by-step size reduction. Percentages are indicative ranges tied to how each fix "
               "mechanism typically behaves -- not a guaranteed saving -- so every result shows a range.")

    if not result.size.cell_count_available:
        st.info("The simulator needs a Cell Count column -- not available in this export.")
        return
    if not result.size_opportunities:
        st.success("No size-affecting opportunities to simulate at the current thresholds.")
        return

    labels = {f"{o.priority}. {o.issue} -- {o.module}": o for o in result.size_opportunities if o.cell_impact}
    if not labels:
        st.info("None of the current size opportunities have a measurable cell impact to simulate.")
        return

    selected_labels = st.multiselect("Select optimizations to apply", options=list(labels.keys()),
                                      default=list(labels.keys())[:min(3, len(labels))])
    selected = [labels[l] for l in selected_labels]

    if not selected:
        st.info("Select at least one optimization above to see the projection.")
        return

    sim = simulate(selected, result.size.total_cells)

    c1, c2, c3 = st.columns(3)
    c1.metric("Starting size", f"{sim.starting_gb:,.2f} GB", f"{sim.starting_cells:,.0f} cells")
    c2.metric("Projected ending size", f"{cells_to_gb(sim.ending_cells_high):,.2f}-{cells_to_gb(sim.ending_cells_low):,.2f} GB")
    c3.metric("Potential reduction", f"{sim.total_reduction_pct_low:.0f}-{sim.total_reduction_pct_high:.0f}%")

    st.subheader("Step-by-step waterfall (conservative end of each range)")
    waterfall = pd.DataFrame([{
        "Step": "Starting size", "Cells after step": sim.starting_cells, "GB after step": cells_to_gb(sim.starting_cells),
    }] + [{
        "Step": s.label, "Cells after step": s.cells_after, "GB after step": cells_to_gb(s.cells_after),
    } for s in sim.steps])
    st.bar_chart(waterfall.set_index("Step")["GB after step"])
    st.dataframe(waterfall, width="stretch", hide_index=True)

    st.caption(
        "Reduction ranges by mechanism: full-grain re-dimensioning 25-40%, Time Range scoping 20-35%, "
        "TEXT/subsidiary-view fixes 10-20%, other size fixes 5-15%. These are structural assumptions about "
        "how each fix typically behaves, not measurements of this specific model -- confirm in a sandbox "
        "before committing to a number in a client deliverable."
    )
