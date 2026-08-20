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
from app.ui.data_quality import render_data_quality
from app.ui.dependency_view import render_dependency_view
from app.ui.rules_reference import render_rules_reference

from app.reports.excel_report import build_excel_report
from app.reports.csv_report import build_optimization_backlog_csv, build_findings_csv
from app.reports.json_report import build_json_report

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
if uploaded:
    df, err = load_file(uploaded, uploaded.name)
    if err is not None or df is None:
        st.error(f"Failed to read file: {err}")
        st.stop()
elif demo_mode:
    df = build_demo_df(n_rows=80)

if df is None:
    st.info("Upload an Anaplan export or turn on **Preview (Demo Data)** in the sidebar to get started.")
    st.stop()

if len(df) > LARGE_FILE_ROW_LIMIT:
    st.warning(f"This file has {len(df):,} rows, above the {LARGE_FILE_ROW_LIMIT:,}-row comfort threshold. "
               "The platform will still run, but consider pre-filtering by module if it feels slow.")

try:
    result = run_pipeline(df, THRESHOLDS, agg_method=agg_method, top_n_modules=int(top_n_modules))
except SchemaError as e:
    st.error(str(e))
    st.stop()

is_preview = uploaded is None and demo_mode

# ---- Navigation ----
PAGES = [
    "Executive Dashboard", "Consultant Dashboard", "Model Size", "Dimensionality",
    "Formula Optimization Center", "Calculation Hotspot Matrix", "Optimization Opportunities",
    "Consultant Action Plan", "Dependency Analysis", "Data Quality", "Rules Reference", "Export Reports",
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
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("Excel workbook", data=build_excel_report(result, client_name_input, model_label_input),
                        file_name="anaplan_model_health_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c2.download_button("Optimization backlog (CSV)", data=build_optimization_backlog_csv(result),
                        file_name="optimization_backlog.csv", mime="text/csv")
    c3.download_button("Findings (CSV)", data=build_findings_csv(result),
                        file_name="findings.csv", mime="text/csv")
    c4.download_button("Findings (JSON)", data=build_json_report(result, client_name_input, model_label_input),
                        file_name="analysis.json", mime="application/json")
