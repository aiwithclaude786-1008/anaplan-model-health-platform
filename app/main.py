# app/main.py
# ============================================================
# Anaplan Model Health & Optimization Platform -- entrypoint.
# Wires the shared sidebar, runs analysis/pipeline.run_pipeline
# exactly once per upload (master spec section 22), and routes
# to whichever page the user selects. Every page below reads
# from the same cached AnalysisResult -- no page recomputes
# findings, size, or scores independently.
# ============================================================
import re
import sys
import time
from pathlib import Path

# `streamlit run app/main.py` puts this file's own directory (app/) on
# sys.path, not its parent -- so `import app.branding` etc. would fail
# with "No module named 'app'" unless the project root (one level up)
# is added explicitly here, before any `app.*` import below.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.branding import inject_streamlit_theme_css
from app.data.loaders import load_file, build_demo_df
from app.data.normalization import SchemaError
from app.rules.thresholds import RuleThresholds
from app.analysis.pipeline import run_pipeline

from app.ui.executive_dashboard import render_executive_dashboard
from app.ui.consultant_dashboard import render_consultant_dashboard
from app.ui.size_dashboard import render_size_dashboard
from app.ui.dimensionality_dashboard import render_dimensionality_dashboard
from app.ui.formula_optimization_center import render_formula_optimization_center
from app.ui.hotspot_matrix import render_hotspot_matrix
from app.ui.optimization_opportunities import render_optimization_opportunities
from app.ui.action_plan import render_action_plan
from app.ui.simulator import render_simulator
from app.ui.data_quality import render_data_quality
from app.ui.dependency_view import render_dependency_view
from app.ui.rules_reference import render_rules_reference

from app.reports.excel_report import build_excel_report
from app.reports.csv_report import build_optimization_backlog_csv, build_findings_csv
from app.reports.json_report import build_json_report
from app.reports.html_report import build_html_report
from app.reports.pdf_report import build_pdf_report

st.set_page_config(page_title="Anaplan Model Health & Optimization Platform", layout="wide")
st.markdown(inject_streamlit_theme_css(), unsafe_allow_html=True)
st.title("Anaplan Model Health & Optimization Platform")

# ---- Sidebar: upload + report details ----
st.sidebar.header("Data")
uploaded = st.sidebar.file_uploader("Upload Anaplan Export (CSV or XLSX)", type=["csv", "xlsx"])
demo_mode = st.sidebar.checkbox("Preview (Demo Data)", value=False,
                                 help="Show the platform with realistic sample data when no file is uploaded.")

with st.sidebar.expander("Report Details", expanded=True):
    default_model_label = ""
    if uploaded is not None:
        default_model_label = re.sub(r"\.(csv|xlsx)$", "", uploaded.name, flags=re.I)
    elif demo_mode:
        default_model_label = "Demo Blueprint"

    client_name_input = st.text_input("Client name", value="" if uploaded is not None or not demo_mode else "Demo Company",
                                       placeholder="e.g. Acme Beverages")
    model_label_input = st.text_input("Model name", value=default_model_label, placeholder="e.g. Var P&L Model")
    scenario_label_input = st.text_input("Scenario / version label (optional)", value="")
    top_n_modules = st.number_input("Modules to highlight in concentration KPIs", min_value=1, max_value=10, value=5, step=1)
    workspace_capacity_input = st.number_input("Workspace cell capacity (optional -- 0 to skip)", min_value=0, value=0, step=1_000_000)

with st.sidebar.expander("Rule Thresholds", expanded=False):
    nested_if_high = st.slider("IF count for HIGH severity", 4, 20, 6, 1)
    nested_if_med = st.slider("IF count for MEDIUM severity", 2, nested_if_high - 1, min(4, nested_if_high - 1), 1)
    daisy_chain_threshold = st.slider("Function count for High Function Density", 2, 12, 4, 1)

with st.sidebar.expander("Module Size Aggregation", expanded=False):
    agg_choice = st.radio("Method for Cell Count roll-up per module",
                           ["MAX (recommended)", "SUM (raw total across rows)"], index=0)
    agg_method = "max" if agg_choice.startswith("MAX") else "sum"

THRESHOLDS = RuleThresholds(nested_if_high=nested_if_high, nested_if_med=nested_if_med,
                             daisy_chain_threshold=daisy_chain_threshold)
LARGE_FILE_ROW_LIMIT = 20000

# ---- Load data ----
df = None
_t_load_start = time.perf_counter()
if uploaded:
    df, err = load_file(uploaded, uploaded.name)
    if err is not None or df is None:
        st.error(f"Failed to read file: {err}")
        st.stop()
elif demo_mode:
    df = build_demo_df(n_rows=80)
_file_load_seconds = time.perf_counter() - _t_load_start

if df is None:
    st.info("Upload an Anaplan export or turn on **Preview (Demo Data)** in the sidebar to get started.")
    st.stop()

if len(df) > LARGE_FILE_ROW_LIMIT:
    st.warning(f"This file has {len(df):,} rows, above the {LARGE_FILE_ROW_LIMIT:,}-row comfort threshold. "
               "The platform will still run, but consider pre-filtering by module if it feels slow.")

try:
    _t_pipeline_start = time.perf_counter()
    result = run_pipeline(df, THRESHOLDS, agg_method=agg_method, top_n_modules=int(top_n_modules))
    _pipeline_call_seconds = time.perf_counter() - _t_pipeline_start
except SchemaError as e:
    st.error(str(e))
    st.stop()

is_preview = uploaded is None and demo_mode

# ---- Performance diagnostics -- always visible so a slow run can be
# pinpointed (file read vs. cache-key hashing vs. a specific analysis
# stage) instead of guessed at. See app/analysis/pipeline.py's
# _Stopwatch for the per-stage breakdown.
with st.sidebar.expander(
    f"Performance ({_file_load_seconds + _pipeline_call_seconds:.1f}s)", expanded=False,
):
    stage_total = sum(result.timings.values())
    st.caption(f"File read: **{_file_load_seconds:.2f}s** ({len(df):,} rows)")
    st.caption(f"Pipeline call: **{_pipeline_call_seconds:.2f}s** (stage compute: {stage_total:.2f}s)")
    if _pipeline_call_seconds > stage_total + 0.5:
        st.caption(f"↳ {_pipeline_call_seconds - stage_total:.2f}s of that was cache bookkeeping "
                    "(hashing the upload to check the cache), not analysis.")
    for stage, seconds in result.timings.items():
        st.caption(f"&nbsp;&nbsp;- {stage}: {seconds:.2f}s", unsafe_allow_html=True)
    st.caption("Note: these numbers reflect the run that actually computed the result -- if this upload was "
               "already cached (e.g. you just switched pages), the pipeline call above will be near-zero.")

# ---- Navigation ----
PAGES = [
    "Executive Dashboard", "Consultant Dashboard", "Model Size", "Dimensionality",
    "Formula Optimization Center", "Calculation Hotspot Matrix", "Optimization Opportunities",
    "Before / After Simulator", "Consultant Action Plan", "Dependency Analysis", "Data Quality",
    "Rules Reference", "Export Reports",
]
page = st.sidebar.radio("Navigate", PAGES)

if page == "Executive Dashboard":
    render_executive_dashboard(result, client_name_input, model_label_input, scenario_label_input,
                                is_preview, workspace_capacity_input)
elif page == "Consultant Dashboard":
    render_consultant_dashboard(result)
elif page == "Model Size":
    render_size_dashboard(result)
elif page == "Dimensionality":
    render_dimensionality_dashboard(result)
elif page == "Formula Optimization Center":
    render_formula_optimization_center(result)
elif page == "Calculation Hotspot Matrix":
    render_hotspot_matrix(result)
elif page == "Optimization Opportunities":
    render_optimization_opportunities(result)
elif page == "Before / After Simulator":
    render_simulator(result)
elif page == "Consultant Action Plan":
    render_action_plan(result)
elif page == "Dependency Analysis":
    render_dependency_view(result)
elif page == "Data Quality":
    render_data_quality(result)
elif page == "Rules Reference":
    render_rules_reference(THRESHOLDS, set(result.active_rule_ids))
elif page == "Export Reports":
    st.header("Export Reports")
    st.caption("Every export is generated from the same analysis result shown on the other pages.")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Excel workbook", data=build_excel_report(result, client_name_input, model_label_input),
                        file_name="anaplan_model_health_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c2.download_button("Interactive HTML report", data=build_html_report(result, client_name_input, model_label_input),
                        file_name="anaplan_model_health_report.html", mime="text/html")
    c3.download_button("Executive PDF report", data=build_pdf_report(result, client_name_input, model_label_input),
                        file_name="anaplan_model_health_report.pdf", mime="application/pdf")

    c4, c5 = st.columns(2)
    c4.download_button("Optimization backlog (CSV)", data=build_optimization_backlog_csv(result),
                        file_name="optimization_backlog.csv", mime="text/csv")
    c5.download_button("Findings (CSV)", data=build_findings_csv(result),
                        file_name="findings.csv", mime="text/csv")
    st.download_button("Findings (JSON, machine-readable)", data=build_json_report(result, client_name_input, model_label_input),
                        file_name="analysis.json", mime="application/json")
