# app.py
# ============================================================
# Anaplan Model Health Tool
# v2 CORRECTED logic is unchanged. v3 adds:
#   - A dynamic, per-client Executive Summary tab (now FIRST tab),
#     rendered as an interactive HTML dashboard, computed entirely
#     from the uploaded file + the same detection rules used in the
#     Audit Dashboard tab. Nothing about it is hardcoded to any one
#     client — client name, model name, and scenario label are all
#     inputs, and every number on it is derived live from the data.
#   - Shared data pipeline moved out of any single tab so all three
#     tabs read from the same computed result.
# ============================================================

import re
import json
import html as html_lib
import random
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np

# ============================================================
# Page config
# ============================================================
st.set_page_config(page_title="Anaplan Model Health Tool", layout="wide")

# ------------------------------------------------------------
# Tridant brand pass for the native Streamlit chrome (sidebar,
# buttons, tabs). Same measured values as the Executive Summary
# HTML tab: accent #00ADEF, text #5A5A5A, Source Sans Pro, 4px
# radius. Paired with .streamlit/config.toml for base theme colors
# — this block covers what config.toml can't reach (font import,
# fine button/tab styling).
# ------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Source Sans Pro', -apple-system, sans-serif; }
.stButton>button, .stDownloadButton>button {
    background-color:#00ADEF; color:#FFFFFF; border:none; border-radius:4px; font-weight:600;
}
.stButton>button:hover, .stDownloadButton>button:hover { background-color:#0090C9; color:#FFFFFF; }
.stTabs [aria-selected="true"] { color:#00ADEF; border-bottom-color:#00ADEF; }
[data-testid="stMetricValue"] { color:#2B2E31; }
[data-testid="stHeader"] { background-color:#9C66A0; }
</style>
""", unsafe_allow_html=True)

st.title("Anaplan Model Health Tool")

tab_exec, tab_dashboard, tab_reference = st.tabs(
    ["🧾 Executive Summary", "📊 Audit Dashboard", "📋 Rules, Bugs & Fix Reference"]
)

# ============================================================
# Refactor suggestions mapping
# ============================================================
REFACTOR = {
    "multi_lookup": "Split LOOKUP into helper line item before aggregation",
    "nested_if": "Replace IF chains with mapping module",
    "timesum": "Replace TIMESUM with cumulative module using PREVIOUS",
    "calc_chain": "Stage calculations into multiple line items",
    "post_lookup": "Separate POST and LOOKUP into different staged line items / modules",
    "post_sum": "Separate POST and SUM into different staged line items / modules",
    "post_if": "Move POST outside IF; calculate POST in dedicated output line item/module",
    "daisy_chain": "Break daisy chain into staged calculations",
    "timesum_range": "Add START/END or replace with cumulative logic",
    "lookup_sum": "Stage calculations into multiple line items",
    "lookup_select": "Stage calculations into multiple line items",
    "select_sum": "Stage calculations into multiple line items",
}

# Short, general Anaplan/PLANUAL-style rule statements used only in the
# Executive Summary tab — these describe the RULE, not client-specific data.
RULE_DESCRIPTIONS = {
    "multi_lookup": "Avoid chaining multiple LOOKUPs in a single formula.",
    "nested_if": "Keep IF logic shallow — long chains should become a mapping module.",
    "lookup_sum": "Don't combine LOOKUP and SUM inside the same dimension mapping.",
    "lookup_select": "Don't combine LOOKUP and SELECT inside the same dimension mapping.",
    "select_sum": "Don't combine SELECT and SUM inside the same dimension mapping.",
    "calc_chain": "Keep formulas short and single-purpose rather than function-dense.",
    "post_lookup": "Keep the POST target mapping outside the POST statement itself.",
    "post_sum": "Keep the POST source aggregation outside the POST statement itself.",
    "post_if": "Move POST outside conditional branches into a dedicated output line item.",
    "timesum": "Prefer a cumulative module using PREVIOUS over TIMESUM.",
    "timesum_range": "Always scope TIMESUM with a START/END range.",
}

# ============================================================
# Column detection helper (expanded synonyms)
# ============================================================
def find_col(cols, keys):
    cl = [str(c).lower() for c in cols]
    for k in keys:
        if k in cl:
            return cols[cl.index(k)]
    for k in keys:
        for i, low in enumerate(cl):
            if k in low:
                return cols[i]
    return None

FORMULA_KEYS = ["formula", "expression", "formula text", "line item formula",
                 "item formula", "calc formula", "formula string"]
CELLCOUNT_KEYS = ["cell count", "cell_count", "cell", "cells", "total cells"]
CALCEFFORT_KEYS = ["calculation effort", "calc effort", "calculation",
                    "calc time", "calculation time", "compute effort"]

# ============================================================
# load_file — preserves both XLSX engine error messages
# ============================================================
@st.cache_data(show_spinner=False)
def load_file(_bytes, filename):
    if filename.lower().endswith(".csv"):
        try:
            df = pd.read_csv(_bytes)
        except Exception as e:
            return None, f"CSV read failed: {e}"
        return df, None

    first_err = None
    try:
        df = pd.read_excel(_bytes, engine="openpyxl")
        return df, None
    except Exception as e1:
        first_err = str(e1)
    try:
        df = pd.read_excel(_bytes)
        return df, None
    except Exception as e2:
        return None, f"XLSX read failed with openpyxl engine ({first_err}); fallback also failed: {e2}"

# ============================================================
# Demo dataset
# ============================================================
def build_demo_df(n_rows=80, seed=42):
    random.seed(seed)
    np.random.seed(seed)

    samples = [
        ("REV_Planning", "Revenue Alloc",
         "Sales[SUM: Region.Map, LOOKUP: Version.Cur] + Adj[LOOKUP: Scenario.Live]"),
        ("REV_Planning", "Baseline", "Baseline"),
        ("COST_Allocations", "Cost Switch",
         "IF A THEN X ELSE IF B THEN Y ELSE IF C THEN Z ELSE IF D THEN W ELSE IF E THEN V ELSE U"),
        ("INV_Transfers", "Transfer Post Lookup",
         "POST(Inv.Delta, Map.Tgt[LOOKUP: Map.Rule])"),
        ("INV_Transfers", "Transfer Post Lookup 2",
         "POST(Inv.Delta[LOOKUP: Map.Rule], Map.Tgt)"),
        ("INV_Transfers", "Transfer Post Sum",
         "POST(Inv.Delta[SUM: Dept.Map], Map.Tgt)"),
        ("INV_Transfers", "Post Inside If",
         "IF Flag THEN POST(Inv.Delta, Map.Tgt[LOOKUP: Map.Rule]) ELSE 0"),
        ("INV_Transfers", "Post Nested Extra Paren",
         "IF Flag THEN POST(Inv.Delta, Map.Tgt[LOOKUP: Map.Rule(Region.Code)]) ELSE 0"),
        ("HR_Salary", "Salary Sum", "TIMESUM(Salary)"),
        ("HR_Salary", "Salary Window", "TIMESUM(Salary, START(), END())"),
        ("FX_Rates", "FX Dense",
         "IF Flag THEN CUMULATE(Amount) ELSE MOVINGSUM(Amount, -3, 0) + SELECT: #FY24"),
        ("REV_Planning", "Price LK", "Price[LOOKUP: PMap.Cur]"),
        ("COST_Allocations", "Simple Sum", "X[SUM: Dept.Map] + Y"),
        ("INV_Transfers", "Find In List", "FINDITEM(Product, Code)"),
        ("FX_Rates", "Constant", "1"),
        ("FX_Rates", "FX", "TAX[LOOKUP: SUFFIX.Map] + FX.Rate"),
    ]

    rows = []
    for i in range(n_rows):
        mod, li, f = random.choice(samples)
        if random.random() < 0.25: f = f.replace("LOOKUP", "Lookup")
        if random.random() < 0.25: f = f.replace("SUM", "sum")
        if random.random() < 0.20: f = f.replace("POST", "Post")

        cell_count = float(np.random.lognormal(mean=16.0, sigma=0.8))
        calc_effort = float(np.random.lognormal(mean=5.1, sigma=0.7))

        rows.append({
            "Line Item Name": f"{li} {i+1}",
            "Format": "Number",
            "Formula": f,
            "Cell Count": cell_count,
            "Calculation Effort": calc_effort,
            "Module": mod,
        })

    df = pd.DataFrame(rows)
    c = list(df.columns)
    if c[-1] != "Module":
        df = df[c[:-1] + ["Module"]]
    return df

# ============================================================
# Pretty formula formatter (display-only)
# ============================================================
def _format_anaplan_formula(formula: str) -> str:
    f = str(formula or "").strip()
    if not f:
        return f
    f = re.sub(r"[ \t]+", " ", f)
    pattern = r"(\bIF\b|\bTHEN\b|\bELSE\b|,|\(|\)|\[|\])"
    parts = re.split(pattern, f, flags=re.IGNORECASE)
    lines = []
    indent = 0
    IND = "    "

    def emit(s):
        s = s.strip()
        if s:
            lines.append((IND * indent) + s)

    i = 0
    while i < len(parts):
        tok = parts[i]
        if tok is None:
            i += 1
            continue
        t = tok.strip()
        up = t.upper()
        if t in ["[", "("]:
            emit(t); indent += 1; i += 1; continue
        if t in ["]", ")"]:
            indent = max(0, indent - 1); emit(t); i += 1; continue
        if t == ",":
            emit(","); i += 1; continue
        if up == "IF":
            emit("IF"); indent += 1; i += 1; continue
        if up == "THEN":
            indent = max(0, indent - 1); emit("THEN"); indent += 1; i += 1; continue
        if up == "ELSE":
            indent = max(0, indent - 1); emit("ELSE"); indent += 1; i += 1; continue
        emit(t); i += 1

    out = "\n".join(lines).strip()
    out = re.sub(r"\n\s*,\s*\n", "\n,\n", out)
    return out

# ============================================================
# Regex rules
# ============================================================
RE_IF       = re.compile(r"\bIF\b", re.I)
RE_LOOKUP   = re.compile(r"\bLOOKUP\b", re.I)
RE_SUM      = re.compile(r"\bSUM\b", re.I)
RE_POST     = re.compile(r"\bPOST\b", re.I)
RE_TIMESUM  = re.compile(r"\bTIMESUM\b", re.I)
RE_FINDITEM = re.compile(r"\bFINDITEM\b", re.I)
RE_RANK     = re.compile(r"\bRANK\b", re.I)
RE_SELECT   = re.compile(r"\bSELECT\b", re.I)
RE_CUM      = re.compile(r"\bCUMULATE\b", re.I)
RE_OFFSET   = re.compile(r"\bOFFSET\b|\bLAG\b|\bLEAD\b|\bMOVINGSUM\b", re.I)

RE_START_OR_END = re.compile(r"\bSTART\s*\(|\bEND\s*\(|\bSTART\s*:|\bEND\s*:", re.I)

RE_MAP_SUM_LOOKUP = re.compile(r"\[[^\]]*\bSUM\s*:[^\]]*,[^\]]*\bLOOKUP\s*:", re.I)
RE_MAP_LOOKUP_SUM = re.compile(r"\[[^\]]*\bLOOKUP\s*:[^\]]*,[^\]]*\bSUM\s*:", re.I)
RE_MAP_SELECT_LOOKUP = re.compile(r"\[[^\]]*\bSELECT\s*:[^\]]*,[^\]]*\bLOOKUP\s*:", re.I)
RE_MAP_LOOKUP_SELECT = re.compile(r"\[[^\]]*\bLOOKUP\s*:[^\]]*,[^\]]*\bSELECT\s*:", re.I)
RE_MAP_SUM_SELECT = re.compile(r"\[[^\]]*\bSUM\s*:[^\]]*,[^\]]*\bSELECT\s*:", re.I)
RE_MAP_SELECT_SUM = re.compile(r"\[[^\]]*\bSELECT\s*:[^\]]*,[^\]]*\bSUM\s*:", re.I)

RE_POST_INSIDE_IF = re.compile(
    r"\b(?:THEN|ELSE)\b(?:(?!\bIF\b).)*?\bPOST\s*\(", re.I
)
RE_POST_CALL = re.compile(r"POST\s*\(", re.I)

def post_nested_flags(formula_upper: str):
    has_lookup_nested = False
    has_sum_nested = False
    for m in RE_POST_CALL.finditer(formula_upper):
        start = m.end() - 1
        depth = 0
        j = start
        n = len(formula_upper)
        while j < n:
            ch = formula_upper[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        inner = formula_upper[start + 1:j]
        if re.search(r"\[[^\]]*\bLOOKUP\s*:", inner):
            has_lookup_nested = True
        if re.search(r"\[[^\]]*\bSUM\s*:", inner):
            has_sum_nested = True
        if has_lookup_nested and has_sum_nested:
            break
    return has_lookup_nested, has_sum_nested

def build_entity_pattern(names):
    cleaned = sorted({n for n in names if len(n) >= 2}, key=len, reverse=True)
    if not cleaned:
        return None
    escaped = [re.escape(n) for n in cleaned]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.I)

@st.cache_data(show_spinner=False)
def build_features(formula_series):
    s = formula_series.astype(str).fillna("")
    su = s.str.upper()

    feats = pd.DataFrame(index=formula_series.index)
    feats["formula"] = s
    feats["upper"]   = su

    feats["count_if"] = su.str.count(RE_IF)
    feats["count_lookup"] = su.str.count(RE_LOOKUP)
    feats["count_sum"] = su.str.count(RE_SUM)
    feats["count_select"] = su.str.count(RE_SELECT)

    feats["has_post"] = su.str.contains(RE_POST)
    feats["has_timesum"] = su.str.contains(RE_TIMESUM)

    feats["count_finditem"] = su.str.count(RE_FINDITEM)
    feats["count_rank"] = su.str.count(RE_RANK)
    feats["count_cumulate"] = su.str.count(RE_CUM)
    feats["count_offsetlike"] = su.str.count(RE_OFFSET)

    feats["has_start_or_end"] = su.str.contains(RE_START_OR_END)

    feats["map_has_lookup_sum"] = su.str.contains(RE_MAP_SUM_LOOKUP) | su.str.contains(RE_MAP_LOOKUP_SUM)
    feats["map_has_lookup_select"] = su.str.contains(RE_MAP_SELECT_LOOKUP) | su.str.contains(RE_MAP_LOOKUP_SELECT)
    feats["map_has_select_sum"] = su.str.contains(RE_MAP_SUM_SELECT) | su.str.contains(RE_MAP_SELECT_SUM)

    nested = su.apply(post_nested_flags)
    feats["has_post_lookup_nested"] = nested.apply(lambda t: t[0])
    feats["has_post_sum_nested"] = nested.apply(lambda t: t[1])

    # NOTE: RE_POST_INSIDE_IF uses a negative lookahead, which pandas' PyArrow
    # string backend cannot execute (its regex engine is RE2, which has no
    # lookahead/lookbehind support) even though Python's own `re` module
    # handles it fine. Route this one through a plain Python .apply() so it
    # always uses the `re` module directly, regardless of string backend.
    feats["has_post_inside_if"] = su.apply(lambda x: bool(RE_POST_INSIDE_IF.search(x)))

    feats["func_density_count"] = (
        feats["count_sum"]
        + feats["count_lookup"]
        + feats["count_if"]
        + feats["count_finditem"]
        + feats["count_rank"]
        + feats["count_select"]
        + feats["count_cumulate"]
        + feats["count_offsetlike"]
        + feats["has_timesum"].astype(int)
        + feats["has_post"].astype(int)
    )
    return feats

def detect_row(row, thresholds, func_density_label="High Function Density"):
    issues = []
    nested_if_high = thresholds["nested_if_high"]
    nested_if_med = thresholds["nested_if_med"]
    daisy_chain_threshold = thresholds["daisy_chain_threshold"]

    if row.count_lookup > 1:
        issues.append(("Multiple LOOKUP", "high", "multi_lookup"))

    if row.count_if >= nested_if_high:
        issues.append(("Deep Nested IF", "high", "nested_if"))
    elif row.count_if >= nested_if_med:
        issues.append(("Nested IF", "medium", "nested_if"))

    if row.map_has_lookup_sum:
        issues.append(("LOOKUP & SUM", "high", "lookup_sum"))
    if row.map_has_lookup_select:
        issues.append(("LOOKUP & SELECT", "high", "lookup_select"))
    if row.map_has_select_sum:
        issues.append(("SELECT & SUM", "high", "select_sum"))

    if row.func_density_count >= daisy_chain_threshold:
        issues.append((func_density_label, "high", "calc_chain"))

    if row.has_post_lookup_nested:
        issues.append(("POST + LOOKUP (nested)", "high", "post_lookup"))
    if row.has_post_sum_nested:
        issues.append(("POST + SUM (nested)", "high", "post_sum"))
    if row.has_post_inside_if:
        issues.append(("POST inside IF", "high", "post_if"))

    if row.has_timesum:
        if not row.has_start_or_end:
            issues.append(("TIMESUM without range", "high", "timesum_range"))
        else:
            issues.append(("TIMESUM", "medium", "timesum"))

    seen, deduped = set(), []
    for label, sev, key in issues:
        if key not in seen:
            deduped.append((label, sev, key))
            seen.add(key)
    return deduped

def risk(issues, weights, cap=None):
    total = sum(weights.get(sev, 0) for _, sev, _ in issues)
    if cap is not None:
        total = min(total, cap)
    return total

def extract_issue_metadata(issue_lists):
    labels = set(); severities = set(); keys = set()
    for issues in issue_lists:
        for label, sev, key in issues:
            labels.add(label); severities.add(sev); keys.add(key)
    return sorted(labels), sorted(severities), sorted(keys)

# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.header("Settings")

uploaded = st.sidebar.file_uploader("Upload Anaplan Export (CSV or XLSX)", type=["csv", "xlsx"])

demo_mode = st.sidebar.checkbox(
    "🔍 Preview (Demo Data)", value=False,
    help="Show the dashboard with realistic sample data when no file is uploaded."
)

# ------------------------------------------------------------
# Report Details — makes the Executive Summary tab dynamic per
# client instead of hardcoded to any one organization or model.
# ------------------------------------------------------------
with st.sidebar.expander("Report Details (Executive Summary)", expanded=True):
    default_model_label = ""
    if uploaded is not None:
        default_model_label = re.sub(r"\.(csv|xlsx)$", "", uploaded.name, flags=re.I)
    elif demo_mode:
        default_model_label = "Demo Blueprint"

    client_name_input = st.text_input(
        "Client name", value="" if uploaded is not None or not demo_mode else "Demo Company",
        placeholder="e.g. Acme Beverages"
    )
    model_label_input = st.text_input("Model name", value=default_model_label, placeholder="e.g. Var P&L Model")
    scenario_label_input = st.text_input("Scenario / version label (optional)", value="", placeholder="e.g. FY26 Budget")
    top_n_modules = st.number_input("Modules to highlight in concentration gauge", min_value=1, max_value=10, value=2, step=1)
    workspace_capacity_input = st.number_input(
        "Workspace cell capacity (optional — leave 0 if unknown)",
        min_value=0, value=0, step=1000000,
        help="If you know this client's actual workspace cell entitlement, entering it adds a capacity-used metric. Leave at 0 to skip."
    )

with st.sidebar.expander("Severity Weights", expanded=True):
    w_high = st.slider("High severity weight", 5, 30, 15, 1)
    w_med = st.slider("Medium severity weight", 3, 15, 7, 1)
    w_low = st.slider("Low severity weight", 1, 10, 3, 1)
SEVERITY_WEIGHT = {"high": w_high, "medium": w_med, "low": w_low}

with st.sidebar.expander("Rule Thresholds", expanded=True):
    nested_if_high = st.slider("IF count for HIGH severity", 4, 20, 6, 1)
    _med_default = min(4, nested_if_high - 1)
    nested_if_med = st.slider(
        "IF count for MEDIUM severity", 2, nested_if_high - 1, _med_default, 1
    )
    daisy_chain_threshold = st.slider("Function count for High Function Density", 2, 12, 4, 1)

THRESHOLDS = {
    "nested_if_high": nested_if_high,
    "nested_if_med": nested_if_med,
    "daisy_chain_threshold": daisy_chain_threshold,
}

with st.sidebar.expander("Risk Scoring Options", expanded=False):
    use_risk_cap = st.checkbox(
        "Cap Risk per line item (reduce double-counting inflation)", value=False
    )
    risk_cap_value = st.number_input(
        "Risk cap value", min_value=10, max_value=200, value=40, step=5,
        disabled=not use_risk_cap
    )
RISK_CAP = risk_cap_value if use_risk_cap else None

with st.sidebar.expander("Daisy Chain Score Weights (module-level)", expanded=False):
    w_cross_line = st.slider("Cross-line reference weight", 1, 20, 5, 1)
    w_inter_module = st.slider("Inter-module reference weight", 1, 20, 10, 1)
    w_calc_tokens = st.slider("Calc-token density weight", 1, 10, 2, 1)

with st.sidebar.expander("Module Size Aggregation", expanded=False):
    agg_choice = st.radio(
        "Method for 'Cell Count' roll-up per module",
        ["MAX (recommended — assumes repeated header total per row)",
         "SUM (raw total across all rows — inflates if header repeats)"],
        index=0,
    )
    agg_method = "max" if agg_choice.startswith("MAX") else "sum"

LARGE_FILE_ROW_LIMIT = 20000

# ============================================================
# SHARED DATA PIPELINE — runs once, feeds all three tabs
# ============================================================
df = None
data_ready = False

if uploaded:
    df, err = load_file(uploaded, uploaded.name)
    if err is not None or df is None:
        st.error(f"Failed to read file: {err}")
        st.stop()
elif demo_mode:
    df = build_demo_df(n_rows=80)
else:
    df = None

if df is not None:
    df = df.dropna(how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]
    cols = list(df.columns)

    if len(cols) < 2:
        st.error("Your file must have at least 2 columns.")
        st.stop()

    line_col_df = cols[0]
    module_col_df = cols[-1]

    formula_col = "Formula" if "Formula" in df.columns else (find_col(cols, FORMULA_KEYS) or None)
    if not formula_col or formula_col not in df.columns:
        st.error("Formula column not found. Your export must include a Formula/Expression column.")
        st.write("Detected columns:", cols)
        st.stop()

    size_col_exact = "Cell Count" if "Cell Count" in df.columns else (find_col(cols, CELLCOUNT_KEYS) or None)
    calc_time_col_exact = "Calculation Effort" if "Calculation Effort" in df.columns else (find_col(cols, CALCEFFORT_KEYS) or None)
    cell_count_available = size_col_exact is not None and size_col_exact in df.columns

    feats = build_features(df[formula_col])
    issues_list = [detect_row(r, THRESHOLDS) for r in feats.itertuples(index=False)]

    result = pd.DataFrame({
        "Module": df[module_col_df].astype(str).fillna("Unknown"),
        "Line Item": df[line_col_df].astype(str).fillna("Unknown"),
        "Risk": [risk(iss, SEVERITY_WEIGHT, RISK_CAP) for iss in issues_list],
        "Issues": issues_list,
        "Refactor": [[REFACTOR.get(k, k) for (_, _, k) in iss] for iss in issues_list],
        "Formula": feats["formula"],
    })
    flagged = result[result["Risk"] > 0].copy()

    overall_avg = float(flagged["Risk"].mean()) if len(flagged) else 0.0
    health = max(0.0, 100.0 - overall_avg)
    band = "Excellent" if health > 85 else "Good" if health > 70 else "Fair" if health > 50 else "Critical"

    # ---- Module resolution + Cell Count aggregation (shared) ----
    mod_series = df[module_col_df].astype(str).str.strip().replace(
        {"": np.nan, "None": np.nan, "none": np.nan, "NaN": np.nan, "nan": np.nan, "-": np.nan}
    ).ffill()
    df["_ModuleResolved_"] = mod_series.fillna("Unknown")

    cell_num_all = None
    neg_cell_count = 0
    mod_sum = pd.DataFrame(columns=["Module", "Cell Count (raw)", "Size (GB)"])
    total_cells = 0.0

    if cell_count_available:
        cell_num_all = pd.to_numeric(df[size_col_exact], errors="coerce")
        neg_cell_count = int((cell_num_all < 0).sum())
        result["CellCount"] = cell_num_all.values

        work = pd.DataFrame({"Module": df["_ModuleResolved_"], "Cell Count (raw)": cell_num_all}).dropna(subset=["Cell Count (raw)"])
        if not work.empty:
            mod_sum = (
                work.groupby("Module", as_index=False)["Cell Count (raw)"]
                .agg(agg_method)
                .sort_values("Cell Count (raw)", ascending=False)
            )
            mod_sum["Size (GB)"] = mod_sum["Cell Count (raw)"] / 132000000.0
            total_cells = float(mod_sum["Cell Count (raw)"].sum())
    else:
        result["CellCount"] = np.nan

    modules_count = df["_ModuleResolved_"].nunique()
    line_items_count = len(result)

    top_n_actual = min(int(top_n_modules), len(mod_sum)) if len(mod_sum) else 0
    top_n_cells = float(mod_sum.head(top_n_actual)["Cell Count (raw)"].sum()) if top_n_actual else 0.0
    top_n_pct = (top_n_cells / total_cells * 100.0) if total_cells > 0 else None

    largest_module_name = mod_sum.iloc[0]["Module"] if len(mod_sum) else None
    largest_module_cells = float(mod_sum.iloc[0]["Cell Count (raw)"]) if len(mod_sum) else None

    data_ready = True

# ============================================================
# Findings summarizer for the Executive Summary (uses the SAME
# detections as the Audit Dashboard — no separate/duplicate logic)
# ============================================================
def summarize_findings(result_df, cell_count_available, total_cells):
    from collections import OrderedDict
    agg = OrderedDict()
    for idx, issues in zip(result_df.index, result_df["Issues"]):
        cell_val = result_df.at[idx, "CellCount"] if cell_count_available else np.nan
        for label, sev, key in issues:
            if label not in agg:
                agg[label] = {"severity": sev, "key": key, "items": 0, "cell_impact": 0.0, "has_any_cell": False}
            a = agg[label]
            a["items"] += 1
            if cell_count_available and pd.notna(cell_val):
                a["cell_impact"] += float(cell_val)
                a["has_any_cell"] = True

    findings = []
    for label, a in agg.items():
        pct = None
        cell_impact = None
        if cell_count_available and a["has_any_cell"] and total_cells > 0:
            cell_impact = a["cell_impact"]
            pct = cell_impact / total_cells * 100.0
        findings.append({
            "name": label,
            "rule": RULE_DESCRIPTIONS.get(a["key"], "Review against Anaplan best practice."),
            "refactor": REFACTOR.get(a["key"], ""),
            "severity": a["severity"],
            "items": a["items"],
            "cellImpact": cell_impact,
            "pctModel": pct,
        })

    findings.sort(key=lambda f: (f["pctModel"] is None, -(f["pctModel"] or 0), -f["items"]))
    return findings

# ------------------------------------------------------------
# Tridant logo (left side of the Executive Summary header).
# Empty until an actual logo file is provided — once you upload
# it, this gets set to a base64-embedded <img> tag so the report
# stays a single self-contained file (no external image dependency
# that could break when the HTML renders in Streamlit's sandboxed
# iframe).
# ------------------------------------------------------------
# ------------------------------------------------------------
# Tridant logo (left side of the Executive Summary header).
# Empty until an actual logo file is provided — once you upload
# it, this gets set to a base64-embedded <img> tag so the report
# stays a single self-contained file (no external image dependency
# that could break when the HTML renders in Streamlit's sandboxed
# iframe).
# ------------------------------------------------------------
TRIDANT_LOGO_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAeMAAABVCAYAAAB6k4zkAAASWklEQVR4nO3deZyV5XXA8R8DA7KIKKMRJagsSrRqARckmgJpVargFiqSiKhBFFE0irjGNNaWBJKCSaymEjCJSlAMJiTWpY0iWuuSghIXgklcA0FZFCU6A9M/zkwYpndm7nKe7X3P9/N5Pwpz7/M8l5m5577Pck474ApMrLY0/Hcr8DGwoeHaBLzT8PcxOAXor9je3cAf23jMnsBjin1qqAc+aPj/LcBGYB3yvXobWAWsZsf3NY/2BR4E2pfx3GeAc3WHU7GrgbOV2noSmIz8HMXgZuDU0IPIk3q7kr1+DywBrgeOobw3OA1LCoytkmtoEX32Uu7T17UdCcjfB8YCNUW81iyZS2X/foP9D7lVc9D9+bje6+hbt4Dwvy95uoIPwC69azNwH3Aa0Al/lii+hnqyHYybX9uBZcgdUc8iXnfKaoAPqezfa5H3UbduDro/D9uA432+gFYsIPzvR26uquK+JyYR3YEzgPuBtcB3gb5BR2Ta0g44DrgN+Z7d3/DnLLoE6FJhG19Ad0kkNlXAPUCf0AMxflkwzq4ewMXIlOhdwEFBR2OK0QGZ1VgGPAeMQ4J1FnQDpiq00w6YrtBOzPYAFuN3dssEZsE4+9oD44EXgZlUfmdi/BiC3CE9TzzTlpWYhAQZDecgyxRZdgTwvdCDMP5YMM6PamAG8AowMvBYTPEGAQ81XKkuOXQEvqLYXidgmmJ7sTofOC/0IIwfFozz59PAo8ANZGcKNA+OR45GXYFMZ6fki0Bv5TYvQpZisu5W4ttBbhywYJxP7YCvI2vJHQOPxRSvMzAbeIJ0NvhUAVc5aLc7cKGDdmPTCdnUpzXFbyJlwTjfzkKOQllATstQYAUwKvA4inEKMNBR29OAXRy1HZP9kEQ49n6dYfbNNaOBH2JT1qnZHViKHBeK2dUO294b2cyVBycAXws9COOOBWMDcCZwY+hBmJJVAbcgu+RjNBI4ynEf08nP+9gNwEmhB2HcyMsPsWnbjcDnQw/ClGUGstEnttmNGR766IckAsmLHyOv2WSMBWPT1AJg19CDMGW5iLjukAfj73y0y6nw2PRANnR1DjwOo8yCsWmqN/DV0IMwZbsK3fO8lfBxV9xoENlIjFKsw5D0qSZDLBib5qaS/exGWTaL8OuK/ZGKVD75DP4xmABMCT0Io8eCsWluF/L3xpYlVcgxmJDritPxv349EjjSc5+hzQGODj0Io8OCsSnkfCSxv0lTdySvdXWAvnsBEwP0C/n7EFmN5AnYK/RATOUsGJtCupGvHapZdCRhjqtdRrgkMqcDBwbqO5TewEKkIIxJWAdghId+lgJdFdu7HMlA5NpC4FOK7d0ALC/zuR2AAcAwpMye5r9nIROQ3dV5sRL46wrbaI/sRu8KHICUrTwKGE6YIDED+Rle5am/Hsiu7lAayytOCjiGEEYANxP/rvK5yIc11+agW0jE17i92ATUK17DPY37D8rjPlVpXN2Am4CPlcfX9PqE4sstLlHue2gRffZS7nNFka+1XIcgR4/WK4+7rWs5/tZvr/H0mtr6ufW5AXGOg9dQ7nW68mtboDy+Ocrja8mcFMdt09Rp2oLcZX8OWOuoj2rkLtzo+A1y59IHOX70nqd+P4v+m3QhnYnj7qGaeI53+baA/E3TZ4YF47T9D1Is4ANH7R/nqN082wr8K3L8Z76nPr+B+7KLE4lnI9GF5KO8YnO7IglBbPNlgiwYp28F7u4EDnbUrpGlm/OQ9f/3HffVD7fnfjsga7Wx6EZ+z+AeAtwRehCmdBaMs2Eebjbp9HfQptnZEmST11uO+7kad2vHY5ENazGZRn5TRp6J7gYm44EF42yox016PEtI78erwDHAaw77OAzZY6CtHXHu4t2LcOedYzAbW2ZKigXj7HjEQZtWNMKft4ATkd3WrnzZQZsnIoE+Rlfifq08Vh2ARUjNZ5MAC8bZsRrZHKRtNwdtmsLWIFO+2x21Pxb97+c1im3VI0suWvqS7+Q1ewP3EiYTmymRBeNs2eCgTdfJRczOHge+5qjtTsAYxfaGoTsV+iuk0IUml2vlKTgW+GboQZi2WTDOljoHbbq42zatmwm85Kjt0xTb0l4rvhtZP39esc3DyVd5xUIuQzZ1mYhZMM6O9sA+Dtr90EGbpnW1uDuu9nforKMeAoxWaKfRB8iUKuhOVUOcG8x8m4d8z0ykLBhnx+Horw3VIekFjX8PAcsctNuN4tKNtkW7QtLt7DhvvQB4V7Ht4Vipwa5IQhDblBkpC8bZ8Q8O2vyjgzZN8W5x1G6lR5z6AOM1BtKglp3z/25F/7XnrbxiIQcCd5LvNfRoWTDOhj2QFIDa3nDQpinez4B1Dto9osLnX4luyb4fA283+7tb0V0iORUYqNheqk4jrmxppoEF42z4Dm6OIL3soE1TvFokIGsbUsFza9A/rzy7wN+9B/xAsY/G8ooG/gU/pXNNCSwYp+96dKcMm3rOUbumeL9w0GYfii+P2dyl6KaZXErLO8dnA9sU+zob6K3YXqqqgJ9g/xZRsWCcri7A95G6xq642EBkSvO0o3YHlPGcbsBU5XG0dgb2DSRoaKkGLldsT5vPD797AvcBHT32aVphwTg9+yDHXlYDkxz28zo2TR2DdbgpIrF/Gc+5ANhdcQxPA0+08RjthBWT0X0Nmi4AnvLY39FIOU8TgbzmbQ3lnyi/AHs7pIqSi7PEhdznqR/TtjXoTymWWnu4I/pnn4vJtrUSeBi9xB1dgYuR38XY7AL8PZKJbJCnPqcgddF/6Kk/0wILxn6ldOj+ztADMH+xBjkrq6mmxMd/CdhXsf/VSPnIYnwT3Sxa04BvEV92uZ7AZuAE4FlgP0/93oZ86FnpqT9TgE1Tm0KWAy+GHoT5i+bHfjR0KuGxVcBVyv3PpviCGP+JborMGuA8xfa0NN4crUeKevhKuNMZSQgS6/R9LlgwNoXMDD0As5OPHLTZvYTHngocpNj3WkqfFtUuIBF7ecVnkZ3rvvRFvieWECQQC8amuSdxc5zGlM/FHVIpv/vauZ2/A3xc4nMWA79XHMP+xF884XbgRx77Oxm4wWN/pgkLxqap7cR99MPo+XORjxsJHKnY74dIdq1S1SHrvJpmEP+d4IXAKo/93YhVuQrCgrFpai4yPWbi4iK5/wzkXOu1tJ4mUvuu+HZgU5nP/QGSmUvLocAoxfZc+Ag4A9jiqb8q4B5kt72LkqymBRaMTaPngWtCD8IU5Oo42xDgZuQ8+cvIcZ/BTb4+GCm5qKV5QYhSuSggkUJ5xdXARI/97YFMV2t+8DFtsGBsQKoznU7p63jGjwM89DEQuA75UPY6kgziG8p9LATerLCNW9Hd0HYccIxie64sxm+Cjsm4yXdvWmDB2LwPnIRVaIqZ7/PpfZDkNH+r3K5GNq130S0gAWncHYMsLTzpqa9q5Gy58cSCcb5tQDZr/G/ogZgW7UM2Evr/Er2NSNoFJMYAByu250otUrf8T5766+qpH4MF4zz7HTAMSYVn4pWVUnea54RfBxYptgdy15mCd4BxFJ8wxSTCgnE+PYAUmH819EBMm8aEHoCCZ4HHlNvULiBxFjI9n4JfIaVTTYZYMM6XTcC5SEaljUFHYorRBVnPT532RjCAFcAjiu3FXl6xuZnAz0MPwuixYJwPtcgu1AOBBWGHYkowkWys230Xqb19ElKZSIt2isxJlF5AI5R64Bx0s5KZgCwYZ982YChSNm594LGY4nVAqgtlwd5IoFuKnF39KfJBo9LA9wi6mw8byyumYiPwBexIYiZYMM6+9kg5RDszmJbzkZmMrOmCLJPMB9YBy5CiDeW+Vu2740uQMabi18DU0IMwlbNgnA9/hRRoT+lNJs96AjeFHoQHVUjSjVnIZsKXkfXlYRT/3nQv8AfFMfUEvqzYng93YMtPybNgnB9HIdOEmmt2xo07gD1DDyKAgUjd5CeRrHDzgFOQerstcVFAIvbyioVMAV4IPQhTPgvGfk1GSrcVusbgvpj4COR8ZkfH/ZjyXYJM4+bdXsB5wBIkOc0DDX/eq8BjtQtIfBoYr9ieD1uRghLvhx6IKY8FY7/+hCQsKHT9HBiL7Hx2aTSyXtfecT+mdGdQWSGFrNoF+bA6D1gLPIUk6fhMw9c/QnZsa0qhvGJza/BbUMIosmAcl58h6e5cZ9cZD3yP9N5ssmwiUrrOfidb1w4p7DATeAmpaDQLmaLVnFk6GDhZsT1ffoqkCzWJsV/8+CwBJuA+IE9GP4uRKV0VUsZwPpJ4wpRmALLGuxj95ZdUCkg0dw3wROhBmNJYMI7TXfjZ0XklllYvpAOQ1IbXhh6IKWgYcGzoQZShDplhWxd6IKZ4FozjNR/ZIenaTcClHvoxO3RDPgS9CHwu8FhM61K9O14LnIludSvjkAXjuP0bcIWHfuZiGz982Ae5C34N+RDkK9XlYuBNT31lzUnAoaEHUabHsVmXZFgwjt+3kTUg1+Yhu3mNnipkI9ClSD3fN5D14ULHc1x5FEmZ2AcYBHwVqaJkipdKecVCZiHHwkzkUjvYnlczgV1x+ym3CtnNOxp4yGE/seqDThajzkims/2QzUUhk6xsA77S5M8rGq6bgH8ERiE/VwdiH8xbMw753Xsj9EDKUI/Mej0P9A07FNMaC8bpuA45G+zyU3o1cjTiRCRncJ7sjlTByZJ/Rtalm+uCFETo2fDnj5F0lHVIYO7mZXTpaA9MRxKypGgTMuv131gGvmjZp+G0XA3c5riPzkgCkiGO+zFuPQd8vYWvTWJHIAboBBwGDEYC8WvAM0hKSiPOJ53yioWswM+GUFMmC8bpmYLUhnWpO/AfSIEJk54NyNGWugJfq6btTYH9kFzmvYB3kTXmV3B/9j1mnUn/1MF8JHWoiZAF4/TUIwH5bsf91CABub/jfoyuOmRKsqWi8+OR3MvFqgGORIo41AIrkbJ9WyoYY6qmkv4U/sXIXbKJjAXjNG1DsnQtctzPvkhA7u24H6NjO7JZ57EWvl5FZXsOOgGHs/N09mLgdxW0mZLdgQtCD6JCf0Z2128KPA7TjAXjdG0DzkbWd13qh+yuzmNJv9RchGRva8kYdhRX0LA/slu7H3AIEuiXk+3p7MtJv+rZa1hegehYME7bJ8in3Icd93Mw8CCwm+N+THnqgHNpey+Bdjaphew47vMSkuv8OOQc9QTgXrJX0q838MXQg1DwAJabPioWjNP3CXAakuPYpSHAUuRYjInHh8gd74I2HjccOFq571kt/P17wI+QTWQ1wOeR0pBrlPsPZTrZeO+8lpaXNIxnWfiBMlLP9WTgacf9HAvcT/rTdFnxWyTAPljEY7Xvih9FNnO1pRb4L2R6dwAyTX4Vco491enszyDJcVK3DTgLO8IWBQvG2fERkqzjGcf9nIBk6mrvuB/TukXAEcBvinjsIOT7pqncKc5XkDvqv0H2IXwJ+AmwWWlcvqRaQKI5KygRCQvG2bIZCcirHPdzOpLLup3jfsz/twE5nnQmxa/HamdtewF4RKGdDciGs3FIYB5JOtPZQ8lOxa0nSDv/diZYMM6ejcibmuuAfA5wi+M+zM7uRDbT3VPCc/oDY5XH0dJacSVqkX0PjdPZA5F6248T712bjwIuvnwbSYVrArHc1Nm0HpmWXIYcO3FlKulNL6boKSRrVjl7ArQ3G72JTCu79mrD9S3kfO8oZF/EKKCHh/6LcSLZyfVcj+zIPxRL9BOE3Rln1zvIDlrXCRmuA0Y47iOvnkbe8D9LeYG4F/rnSecid7E+bUQyzo1HprNHIHdyv/U8jkKGhx6Aos1I9ratoQeSRxaMs+0t5A75bcf9dHfcfp7UIXeexzRclZSzvAzdne+bcZ8XvS11yHGcK5AKUwcR/3R2Sl5AkscYzywYZ98a5NP72sDjMK17Fgme+yIbmio9ptYD/TfV24EPlNus1GpkKns4cqb5LOQuemPAMaXuTuDfQw8ib2zNOB/WAMcj5z1TLgOXJVuQu7lfIslUtAvXTwF2VWyvFpmijtkmJCvYQuTo3bHIOvNo5A7aFO9SJNHP4NADyQsLxvnxIrLLejk2rezbeuDlhmslsiFrFe6mVTsD05TbvAvZh5CKbciHnceRTWwDgFOAC3G7qTErGgtK/Jp4Nsxlmq9zohPQXbv6BX6yxoxDt2Taw+jfAZWqL3JGMmYPI3V0W9MBKVQQk1pkV2otsra5teHyvZa5G5IiVdMSslPppwvwKeJLXPMOkrwnJj2R3ewaNtH277WGGnQ/QGzCw7j/D1qhK2npURYwAAAAAElFTkSuQmCC"
)
TRIDANT_LOGO_HTML = f'<img class="logo" alt="Tridant" src="data:image/png;base64,{TRIDANT_LOGO_B64}">'

# ============================================================
# Executive Summary HTML template (token-based — no brace escaping)
# ============================================================
EXEC_TEMPLATE = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  /* ===========================================================
     Tridant brand tokens — sourced from live inspection of
     tridant.com (Aug 2026):
       --accent   : rgb(0,173,239) measured directly off their CTA
                    button background-color.
       --on-accent: rgb(255,255,255) measured off the same button's
                    text color.
       --text     : #5a5a5a measured off body/computed text color.
       font-family: "Source Sans Pro" measured off the same button
                    (font-family + Rendered Fonts: SourceSansPro-SemiBold).
       --radius   : 4px measured off the button's border-radius.
     Everything else below (surfaces, borders, status colors) is a
     reasonable extension of those measured values, not a second
     measurement — call it out if any of it should be adjusted.
     =========================================================== */
  :root{
    --bg:#FFFFFF; --surface:#F6F8F9; --surface-alt:#EEF2F4;
    --border:rgba(20,24,27,0.08); --border-strong:rgba(20,24,27,0.14);
    --text:#5A5A5A; --text-strong:#2B2E31; --text-faint:#8B9096;
    --accent:#00ADEF; --accent-deep:#0090C9; --on-accent:#FFFFFF;
    --critical:#C0392B; --critical-bright:#D64545; --high:#C97A1E; --medium:#3E7C90; --low:#6B7268;
    --excellent:#2F8F57; --good:#5C8A3A; --fair:#C97A1E;
    --radius:4px; --shadow:0 12px 30px -16px rgba(20,24,27,0.16);
  }
  *{box-sizing:border-box;}
  body{margin:0;background:radial-gradient(1200px 640px at 12% -10%, rgba(0,173,239,0.05), transparent 60%),var(--bg);color:var(--text);font-family:'Source Sans Pro',-apple-system,sans-serif;-webkit-font-smoothing:antialiased;line-height:1.5;}
  .wrap{max-width:1120px;margin:0 auto;padding:0 28px;}
  .topbar{background:#9C66A0;border-bottom:1px solid rgba(20,24,27,0.14);padding:20px 0;}
  .topbar .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;}
  .brand{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}
  .brand .logo{height:28px;width:auto;display:block;}
  .brand .mark{font-family:'Source Sans Pro',sans-serif;font-size:11px;letter-spacing:.1em;font-weight:700;color:#9C66A0;background:#FFFFFF;padding:4px 9px;border-radius:var(--radius);}
  .brand .name{font-weight:600;letter-spacing:.02em;font-size:14px;color:#FFFFFF;}
  .brand .sub{color:rgba(255,255,255,0.75);font-size:12px;letter-spacing:.02em;}
  .badge-preview{font-family:'Source Sans Pro',sans-serif;font-size:10px;font-weight:600;letter-spacing:.08em;color:#FFFFFF;border:1px solid rgba(255,255,255,0.6);border-radius:100px;padding:2px 8px;}
  .prepared{font-size:12px;color:rgba(255,255,255,0.75);text-align:right;}
  .prepared b{color:#FFFFFF;font-weight:600;}
  .hero{padding:56px 0 40px;}
  .eyebrow{font-family:'Source Sans Pro',sans-serif;font-size:12px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--accent-deep);margin:0 0 18px;display:flex;align-items:center;gap:10px;}
  .eyebrow::before{content:'';width:22px;height:1px;background:var(--accent-deep);display:inline-block;}
  h1.headline{font-family:'Source Sans Pro',sans-serif;font-weight:700;font-size:clamp(24px,3.6vw,40px);line-height:1.2;margin:0 0 20px;color:var(--text-strong);max-width:34ch;}
  .verdict-panel{display:grid;grid-template-columns:1.15fr 0.85fr;gap:0;border:1px solid var(--border-strong);border-radius:var(--radius);overflow:hidden;background:var(--bg);box-shadow:var(--shadow);}
  @media (max-width:840px){.verdict-panel{grid-template-columns:1fr;}}
  .verdict-text{padding:32px 34px;border-right:1px solid var(--border);}
  @media (max-width:840px){.verdict-text{border-right:none;border-bottom:1px solid var(--border);}}
  .status-chip{display:inline-flex;align-items:center;gap:8px;font-family:'Source Sans Pro',sans-serif;font-size:11px;letter-spacing:.1em;font-weight:700;padding:6px 12px;border-radius:100px;margin-bottom:16px;}
  .status-chip .dot{width:7px;height:7px;border-radius:50%;}
  .verdict-text p{font-size:15.5px;color:var(--text);max-width:56ch;margin:0;}
  .verdict-text p b{color:var(--text-strong);font-weight:700;}
  .gauge-col{padding:28px 30px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;background:linear-gradient(180deg, rgba(0,173,239,0.05), transparent 40%),var(--surface);}
  .gauge-label{font-family:'Source Sans Pro',sans-serif;font-size:10.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--text-faint);text-align:center;}
  .gauge-readout{font-family:'Source Sans Pro',sans-serif;font-weight:700;font-size:15px;color:var(--text-strong);text-align:center;margin-top:4px;}
  .gauge-readout .pct{font-size:30px;}
  .gauge-caption{font-size:11.5px;color:var(--text-faint);text-align:center;max-width:24ch;line-height:1.4;}
  .kpi-strip{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--border);border:1px solid var(--border-strong);border-radius:var(--radius);overflow:hidden;margin-top:22px;}
  @media (max-width:900px){.kpi-strip{grid-template-columns:repeat(3,1fr);}}
  @media (max-width:520px){.kpi-strip{grid-template-columns:repeat(2,1fr);}}
  .kpi{background:var(--bg);padding:18px 16px;position:relative;}
  .kpi .val{font-family:'Source Sans Pro',sans-serif;font-weight:700;font-size:clamp(15px,2vw,20px);color:var(--text-strong);letter-spacing:-0.01em;font-variant-numeric:tabular-nums;}
  .kpi.flag .val{color:var(--critical-bright);}
  .kpi .lbl{margin-top:5px;font-size:11px;color:var(--text-faint);letter-spacing:.02em;}
  .kpi .tip{display:none;position:absolute;left:14px;right:14px;top:100%;margin-top:8px;background:var(--text-strong);border:1px solid var(--border-strong);border-radius:8px;padding:10px 12px;font-size:11.5px;color:#FFFFFF;z-index:5;line-height:1.4;box-shadow:var(--shadow);}
  .kpi:hover .tip{display:block;}
  section.block{padding:48px 0;border-top:1px solid var(--border);}
  .block-title{font-family:'Source Sans Pro',sans-serif;font-weight:700;font-size:24px;margin:0 0 6px;color:var(--text-strong);}
  .block-desc{color:var(--text);font-size:14px;max-width:64ch;margin:0 0 24px;}
  .dist-chart{display:flex;flex-direction:column;gap:10px;margin-bottom:8px;}
  .dist-row{display:grid;grid-template-columns:200px 1fr 74px;align-items:center;gap:14px;}
  @media (max-width:640px){.dist-row{grid-template-columns:120px 1fr 56px;}}
  .dist-name{font-size:13px;color:var(--text);}
  .dist-track{height:9px;background:var(--surface);border:1px solid var(--border);border-radius:100px;overflow:hidden;}
  .dist-fill{height:100%;border-radius:100px;width:0%;transition:width 1.1s cubic-bezier(.16,.84,.44,1);}
  .dist-val{font-family:'Source Sans Pro',sans-serif;font-size:12.5px;color:var(--text);text-align:right;font-variant-numeric:tabular-nums;}
  .filter-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:22px 0 20px;}
  .chip{font-family:'Source Sans Pro',sans-serif;font-size:11.5px;font-weight:600;letter-spacing:.02em;padding:7px 14px;border-radius:100px;border:1px solid var(--border-strong);background:transparent;color:var(--text);cursor:pointer;transition:all .15s ease;}
  .chip:hover{border-color:var(--accent);color:var(--accent-deep);}
  .chip.active{background:var(--accent);color:var(--on-accent);border-color:var(--accent);font-weight:700;}
  .filter-meta{margin-left:auto;font-size:12px;color:var(--text-faint);font-family:'Source Sans Pro',sans-serif;}
  .filter-meta b{color:var(--accent-deep);}
  .findings{border:1px solid var(--border-strong);border-radius:var(--radius);overflow:hidden;}
  .frow{border-bottom:1px solid var(--border);background:var(--bg);}
  .frow:last-child{border-bottom:none;}
  .frow.hidden{display:none;}
  .frow-head{display:grid;grid-template-columns:28px 1.5fr 1fr 90px;align-items:center;gap:16px;padding:16px 20px;cursor:pointer;-webkit-tap-highlight-color:transparent;}
  @media (max-width:760px){.frow-head{grid-template-columns:20px 1fr 80px;}.fh-rule{display:none;}}
  .fh-chevron{color:var(--text-faint);transition:transform .2s ease;font-size:12px;}
  .frow.open .fh-chevron{transform:rotate(90deg);color:var(--accent-deep);}
  .fh-title{display:flex;flex-direction:column;gap:3px;min-width:0;}
  .fh-name{font-weight:600;font-size:14.5px;color:var(--text-strong);}
  .fh-rule{font-size:12px;color:var(--text-faint);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .fh-impact{display:flex;flex-direction:column;gap:5px;}
  .fh-impact-track{height:5px;background:var(--surface-alt);border-radius:100px;overflow:hidden;}
  .fh-impact-fill{height:100%;border-radius:100px;}
  .fh-impact-label{font-family:'Source Sans Pro',sans-serif;font-size:11px;color:var(--text-faint);font-variant-numeric:tabular-nums;}
  .sev-badge{font-family:'Source Sans Pro',sans-serif;font-size:10.5px;letter-spacing:.06em;font-weight:700;padding:4px 9px;border-radius:5px;text-transform:uppercase;white-space:nowrap;justify-self:end;}
  .sev-high{background:rgba(201,122,30,.10);color:var(--high);border:1px solid rgba(201,122,30,.32);}
  .sev-medium{background:rgba(62,124,144,.10);color:var(--medium);border:1px solid rgba(62,124,144,.32);}
  .sev-low{background:rgba(107,114,104,.10);color:var(--low);border:1px solid rgba(107,114,104,.32);}
  .frow-body{max-height:0;overflow:hidden;transition:max-height .28s ease;}
  .frow.open .frow-body{max-height:420px;}
  .frow-body-inner{padding:0 20px 22px 64px;display:grid;grid-template-columns:1fr 220px;gap:26px;}
  @media (max-width:760px){.frow-body-inner{grid-template-columns:1fr;padding-left:20px;}}
  .frow-note{font-size:13.5px;color:var(--text);line-height:1.6;margin:0 0 10px;}
  .frow-refactor{font-size:12.5px;color:var(--accent-deep);font-weight:600;margin:0;}
  .frow-facts{display:flex;flex-direction:column;gap:10px;padding-left:20px;border-left:1px solid var(--border);}
  @media (max-width:760px){.frow-facts{border-left:none;padding-left:0;padding-top:10px;border-top:1px solid var(--border);}}
  .fact{display:flex;justify-content:space-between;gap:10px;font-size:12px;}
  .fact span:first-child{color:var(--text-faint);}
  .fact span:last-child{font-family:'Source Sans Pro',sans-serif;color:var(--text-strong);font-weight:600;text-align:right;font-variant-numeric:tabular-nums;}
  .na{color:var(--text-faint);font-style:italic;}
  .empty-state{padding:40px;text-align:center;color:var(--text);font-size:14px;border:1px dashed var(--border-strong);border-radius:var(--radius);background:var(--surface);}
  .banner{border:1px solid var(--border-strong);background:var(--surface);border-radius:var(--radius);padding:14px 18px;font-size:12.5px;color:var(--text);margin-bottom:24px;}
  footer{border-top:1px solid var(--border);padding:30px 0 46px;}
  footer .wrap{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;align-items:flex-start;}
  footer p{font-size:12px;color:var(--text-faint);max-width:60ch;margin:0;line-height:1.6;}
  footer .fmark{font-family:'Source Sans Pro',sans-serif;font-size:11px;font-weight:600;color:var(--text-faint);letter-spacing:.06em;}
</style></head>
<body>
<div class="topbar"><div class="wrap">
  <div class="brand">
    __TRIDANT_LOGO__
    <span class="mark">__CLIENT_INITIALS__</span>
    <span class="name">__CLIENT_NAME__</span>
    <span class="sub">· Anaplan Model Health Check</span>
    __PREVIEW_BADGE__
  </div>
  <div class="prepared">Prepared by <b>Tridant</b><br>Scored live against the Audit Dashboard's rule set</div>
</div></div>

<div class="hero"><div class="wrap">
  <p class="eyebrow">__MODEL_LABEL__</p>
  <h1 class="headline">__HEADLINE__</h1>

  <div class="verdict-panel">
    <div class="verdict-text">
      <span class="status-chip" style="color:__STATUS_COLOR__;background:__STATUS_BG__;border:1px solid __STATUS_BORDER__;"><span class="dot" style="background:__STATUS_COLOR__;box-shadow:0 0 10px __STATUS_COLOR__;"></span>__STATUS_LABEL__</span>
      <p>__VERDICT_TEXT__</p>
    </div>
    <div class="gauge-col">
      <div class="gauge-label">Concentration Gauge</div>
      <div class="gauge-svg-wrap">
        <svg width="108" height="190" viewBox="0 0 108 190" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="30" y="10" width="48" height="150" rx="24" fill="rgba(0,173,239,0.04)" stroke="rgba(20,24,27,0.22)" stroke-width="1.5"/>
          <g stroke="rgba(20,24,27,0.22)" stroke-width="1">
            <line x1="24" y1="160" x2="30" y2="160"/><line x1="24" y1="122.5" x2="30" y2="122.5"/>
            <line x1="24" y1="85" x2="30" y2="85"/><line x1="24" y1="47.5" x2="30" y2="47.5"/><line x1="24" y1="10" x2="30" y2="10"/>
          </g>
          <g font-family="Source Sans Pro, sans-serif" font-size="8" fill="rgba(20,24,27,0.4)">
            <text x="10" y="163">0</text><text x="4" y="125.5">25</text><text x="4" y="88">50</text><text x="4" y="50.5">75</text><text x="1" y="13">100</text>
          </g>
          <clipPath id="tubeClip"><rect x="31" y="11" width="46" height="148" rx="23"/></clipPath>
          <g clip-path="url(#tubeClip)"><rect id="gaugeFill" x="31" y="159" width="46" height="0" fill="url(#fillGrad)"/></g>
          <defs><linearGradient id="fillGrad" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stop-color="#00ADEF"/><stop offset="55%" stop-color="#C97A1E"/><stop offset="100%" stop-color="#D64545"/>
          </linearGradient></defs>
          <rect x="30" y="10" width="48" height="150" rx="24" fill="none" stroke="rgba(20,24,27,0.22)" stroke-width="1.5"/>
        </svg>
      </div>
      <div class="gauge-readout"><span class="pct" style="color:__GAUGE_COLOR__;">__GAUGE_PCT_LABEL__</span></div>
      <div class="gauge-caption">__GAUGE_CAPTION__</div>
    </div>
  </div>

  <div class="kpi-strip">__KPI_TILES__</div>
</div></div>

<section class="block"><div class="wrap">
  __DATA_QUALITY_BANNER__
  <h2 class="block-title">Where the space is going</h2>
  <p class="block-desc">Share of total model cells implicated by each rule violation found in this upload. These can overlap — a line item may be flagged by more than one rule — so bars don't sum to 100%.</p>
  <div class="dist-chart" id="distChart"></div>

  <h2 class="block-title" style="margin-top:36px;">Findings, ranked by space impact</h2>
  <p class="block-desc">Generated live from the same detection rules as the Audit Dashboard tab. Select a row for a plain-English read on what's happening and why it matters.</p>

  <div class="filter-row" id="filterRow">
    <button class="chip active" data-sev="all">All findings</button>
    <button class="chip" data-sev="high">High</button>
    <button class="chip" data-sev="medium">Medium</button>
    <button class="chip" data-sev="low">Low</button>
    <span class="filter-meta" id="filterMeta"></span>
  </div>

  <div class="findings" id="findings"></div>
</div></section>

<footer><div class="wrap">
  <p>__FOOTER_NOTE__</p>
  <div class="fmark">TRIDANT · ANAPLAN PARTNER</div>
</div></footer>

<script>
(function(){
  "use strict";
  var FINDINGS = __FINDINGS_JSON__;
  var GAUGE_PCT = __GAUGE_PCT_JS__;

  var SEV_COLOR = { high: "#C97A1E", medium: "#3E7C90", low: "#6B7268" };

  function fmtNum(n){ if (n === null || n === undefined) return null; return Math.round(n).toLocaleString("en-US"); }

  var distEl = document.getElementById("distChart");
  var findingsEl = document.getElementById("findings");

  if (FINDINGS.length === 0){
    distEl.innerHTML = '<div class="empty-state">No PLANUAL-style rule violations were detected at the current thresholds. Nice and clean.</div>';
    findingsEl.innerHTML = '<div class="empty-state">Nothing flagged — adjust thresholds in the Audit Dashboard sidebar if you expected findings here.</div>';
  } else {
    var sizedPcts = FINDINGS.filter(function(f){return f.pctModel !== null;}).map(function(f){return f.pctModel;});
    var maxPct = sizedPcts.length ? Math.max.apply(null, sizedPcts) : 1;

    FINDINGS.forEach(function(f){
      var row = document.createElement("div");
      row.className = "dist-row";
      var name = document.createElement("div"); name.className = "dist-name"; name.textContent = f.name;
      var track = document.createElement("div"); track.className = "dist-track";
      var fill = document.createElement("div"); fill.className = "dist-fill"; fill.style.background = SEV_COLOR[f.severity] || SEV_COLOR.medium;
      track.appendChild(fill);
      var val = document.createElement("div"); val.className = "dist-val";
      val.textContent = (f.pctModel !== null) ? f.pctModel.toFixed(1) + "%" : "—";
      row.appendChild(name); row.appendChild(track); row.appendChild(val);
      distEl.appendChild(row);
      requestAnimationFrame(function(){ requestAnimationFrame(function(){
        var w = (f.pctModel !== null) ? (f.pctModel / maxPct) * 100 : 0;
        fill.style.width = w + "%";
      });});
    });

    function buildRow(f){
      var row = document.createElement("div");
      row.className = "frow"; row.dataset.severity = f.severity;

      var head = document.createElement("div"); head.className = "frow-head";
      var chevron = document.createElement("div"); chevron.className = "fh-chevron"; chevron.textContent = "▸"; head.appendChild(chevron);

      var titleWrap = document.createElement("div"); titleWrap.className = "fh-title";
      var nameEl = document.createElement("div"); nameEl.className = "fh-name"; nameEl.textContent = f.name;
      var ruleEl = document.createElement("div"); ruleEl.className = "fh-rule"; ruleEl.textContent = f.rule;
      titleWrap.appendChild(nameEl); titleWrap.appendChild(ruleEl); head.appendChild(titleWrap);

      var impactWrap = document.createElement("div"); impactWrap.className = "fh-impact";
      var impactTrack = document.createElement("div"); impactTrack.className = "fh-impact-track";
      var impactFill = document.createElement("div"); impactFill.className = "fh-impact-fill";
      impactFill.style.background = SEV_COLOR[f.severity] || SEV_COLOR.medium;
      impactFill.style.width = (f.pctModel !== null ? Math.min(f.pctModel, 100) : 0) + "%";
      impactTrack.appendChild(impactFill);
      var impactLabel = document.createElement("div"); impactLabel.className = "fh-impact-label";
      impactLabel.textContent = (f.pctModel !== null) ? f.pctModel.toFixed(1) + "% of model" : "not sized";
      impactWrap.appendChild(impactTrack); impactWrap.appendChild(impactLabel); head.appendChild(impactWrap);

      var sevBadge = document.createElement("span");
      sevBadge.className = "sev-badge sev-" + f.severity; sevBadge.textContent = f.severity;
      head.appendChild(sevBadge);

      head.addEventListener("click", function(){ row.classList.toggle("open"); });

      var body = document.createElement("div"); body.className = "frow-body";
      var bodyInner = document.createElement("div"); bodyInner.className = "frow-body-inner";
      var noteEl = document.createElement("p"); noteEl.className = "frow-note"; noteEl.textContent = f.rule; bodyInner.appendChild(noteEl);
      if (f.refactor){
        var refEl = document.createElement("p"); refEl.className = "frow-refactor"; refEl.textContent = "Suggested fix: " + f.refactor;
        bodyInner.appendChild(refEl);
      }
      var facts = document.createElement("div"); facts.className = "frow-facts";
      var fact1 = document.createElement("div"); fact1.className = "fact"; fact1.innerHTML = "<span>Items flagged</span><span>" + f.items + "</span>"; facts.appendChild(fact1);
      var cellText = (f.cellImpact !== null) ? fmtNum(f.cellImpact) : '<span class="na">not sized</span>';
      var fact2 = document.createElement("div"); fact2.className = "fact"; fact2.innerHTML = "<span>Cell impact</span><span>" + cellText + "</span>"; facts.appendChild(fact2);
      var pctText = (f.pctModel !== null) ? f.pctModel.toFixed(1) + "%" : '<span class="na">not sized</span>';
      var fact3 = document.createElement("div"); fact3.className = "fact"; fact3.innerHTML = "<span>% of model</span><span>" + pctText + "</span>"; facts.appendChild(fact3);
      bodyInner.appendChild(facts);
      body.appendChild(bodyInner); row.appendChild(head); row.appendChild(body);
      return row;
    }

    FINDINGS.forEach(function(f){ findingsEl.appendChild(buildRow(f)); });
    var firstRow = findingsEl.querySelector(".frow");
    if (firstRow) firstRow.classList.add("open");

    var chips = document.querySelectorAll(".chip");
    var filterMeta = document.getElementById("filterMeta");
    function applyFilter(sev){
      var rows = document.querySelectorAll(".frow");
      var visibleCount = 0;
      rows.forEach(function(r){
        var match = (sev === "all") || (r.dataset.severity === sev);
        r.classList.toggle("hidden", !match);
        if (match) visibleCount++;
      });
      filterMeta.innerHTML = "Showing <b>" + visibleCount + "</b> of " + FINDINGS.length + " findings";
    }
    chips.forEach(function(chip){
      chip.addEventListener("click", function(){
        chips.forEach(function(c){ c.classList.remove("active"); });
        chip.classList.add("active");
        applyFilter(chip.dataset.sev);
      });
    });
    applyFilter("all");
  }

  window.addEventListener("load", function(){
    var fillEl = document.getElementById("gaugeFill");
    var tubeTop = 11, tubeBottom = 159, tubeHeight = tubeBottom - tubeTop;
    var pct = Math.max(0, Math.min(100, GAUGE_PCT));
    var fillHeight = (pct / 100) * tubeHeight;
    var fillY = tubeBottom - fillHeight;
    setTimeout(function(){
      fillEl.setAttribute("y", fillY);
      fillEl.setAttribute("height", fillHeight);
    }, 150);
  });
})();
</script>
</body></html>
"""

def build_exec_html(client_name, model_label, scenario_label, is_preview,
                     modules_count, line_items_count, cell_count_available,
                     total_cells, top_n_actual, top_n_pct, top_n_cells,
                     largest_module_name, largest_module_cells,
                     health, band, capacity_cells, neg_cell_count,
                     findings):
    client_name = client_name.strip() or "Your Organization"
    initials = "".join([w[0] for w in client_name.split()[:2]]).upper() or "CO"

    model_bits = [b for b in [model_label.strip(), scenario_label.strip()] if b]
    model_line = " — ".join(model_bits) if model_bits else "Uploaded Blueprint"

    status_colors = {
        "Excellent": ("#2F8F57", "rgba(47,143,87,0.08)", "rgba(47,143,87,0.35)"),
        "Good": ("#5C8A3A", "rgba(92,138,58,0.08)", "rgba(92,138,58,0.35)"),
        "Fair": ("#C97A1E", "rgba(201,122,30,0.08)", "rgba(201,122,30,0.35)"),
        "Critical": ("#D64545", "rgba(214,69,69,0.08)", "rgba(214,69,69,0.35)"),
    }
    status_color, status_bg, status_border = status_colors.get(band, status_colors["Fair"])

    # ---- Verdict copy, templated by health band (not copied text) ----
    total_cells_fmt = f"{total_cells:,.0f}" if cell_count_available and total_cells > 0 else None
    top_n_pct_fmt = f"{top_n_pct:.0f}%" if top_n_pct is not None else None
    top_n_label = f"top {top_n_actual} module{'s' if top_n_actual != 1 else ''}"

    if not cell_count_available:
        verdict_text = (
            f"No Cell Count column was found in this export, so capacity metrics aren't available. "
            f"The rule-based findings below are still fully computed from <b>{line_items_count:,} line items</b> "
            f"across <b>{modules_count:,} modules</b>."
        )
        headline = f"Structural findings for {html_lib.escape(client_name)}, sized by rule violations only."
        gauge_pct_js = 0
        gauge_pct_label = "N/A"
        gauge_caption = "Cell Count column not found in this export"
        gauge_color = "var(--text-faint)"
    elif band == "Critical":
        verdict_text = (
            f"<b>{client_name}</b>'s model is carrying <b>{total_cells_fmt} allocated cells</b> across "
            f"<b>{modules_count:,} modules</b>. The {top_n_label} alone account for <b>{top_n_pct_fmt}</b> of that "
            f"footprint. That concentration is actually useful news: the risk is structural and localized, "
            f"not spread evenly across the model — which means it's fixable without a full rebuild."
        )
        headline = "Space is concentrated, not diffuse — which means it's fixable."
        gauge_pct_js = round(top_n_pct or 0, 1)
        gauge_pct_label = top_n_pct_fmt or "—"
        gauge_caption = f"of all model cells sit in just {top_n_actual} of {modules_count} modules"
        gauge_color = status_color
    elif band == "Fair":
        verdict_text = (
            f"<b>{client_name}</b>'s model holds <b>{total_cells_fmt} allocated cells</b> across "
            f"<b>{modules_count:,} modules</b>, with a moderate amount of structural risk. The {top_n_label} "
            f"account for <b>{top_n_pct_fmt}</b> of the footprint — worth monitoring, though nothing here looks urgent yet."
        )
        headline = "A moderate amount of structural risk, worth a scheduled clean-up."
        gauge_pct_js = round(top_n_pct or 0, 1)
        gauge_pct_label = top_n_pct_fmt or "—"
        gauge_caption = f"of all model cells sit in just {top_n_actual} of {modules_count} modules"
        gauge_color = status_color
    else:
        verdict_text = (
            f"<b>{client_name}</b>'s model holds <b>{total_cells_fmt} allocated cells</b> across "
            f"<b>{modules_count:,} modules</b>, with a generally healthy, well-distributed structure. The "
            f"{top_n_label} account for <b>{top_n_pct_fmt}</b> of the footprint — a reasonable concentration "
            f"for a model this size."
        )
        headline = "Generally healthy structure — a few pockets worth a look."
        gauge_pct_js = round(top_n_pct or 0, 1)
        gauge_pct_label = top_n_pct_fmt or "—"
        gauge_caption = f"of all model cells sit in just {top_n_actual} of {modules_count} modules"
        gauge_color = status_color

    # ---- KPI tiles (built in Python, inserted as one HTML block) ----
    def kpi_tile(val, lbl, tip, flag=False):
        cls = "kpi flag" if flag else "kpi"
        return f'<div class="{cls}"><div class="val">{html_lib.escape(str(val))}</div><div class="lbl">{html_lib.escape(lbl)}</div><div class="tip">{html_lib.escape(tip)}</div></div>'

    tiles = []
    tiles.append(kpi_tile(total_cells_fmt if total_cells_fmt else "N/A", "Allocated cells",
                           "Total cells the model is currently allocating across all modules and line items.",
                           flag=(band == "Critical")))
    tiles.append(kpi_tile(f"{modules_count:,}", "Modules", "Total module count detected in this export."))
    tiles.append(kpi_tile(f"{line_items_count:,}", "Line items", "Total line items across all modules in the model."))
    tiles.append(kpi_tile(top_n_pct_fmt if top_n_pct_fmt else "N/A", top_n_label.capitalize(),
                           f"Share of the model's total cell count held by the {top_n_label}.",
                           flag=(top_n_pct is not None and top_n_pct >= 50)))
    largest_fmt = f"{largest_module_cells:,.0f}" if largest_module_cells is not None else "N/A"
    tiles.append(kpi_tile(largest_fmt, "Largest module",
                           f"Cell count of the single largest module ({html_lib.escape(str(largest_module_name)) if largest_module_name else 'n/a'})."))
    tiles.append(kpi_tile(band.upper(), "Overall status", "Combined severity across every rule-based finding below.", flag=(band == "Critical")))

    if capacity_cells and capacity_cells > 0 and cell_count_available and total_cells > 0:
        used_pct = total_cells / capacity_cells * 100.0
        tiles.append(kpi_tile(f"{used_pct:.0f}%", "Of stated capacity",
                               f"Based on the workspace capacity you entered ({capacity_cells:,.0f} cells).",
                               flag=(used_pct >= 80)))

    kpi_html = "".join(tiles)

    # ---- Data quality banner ----
    banner_html = ""
    if cell_count_available and neg_cell_count > 0:
        banner_html = (
            f'<div class="banner">⚠️ {neg_cell_count} row(s) in this export have a negative Cell Count value '
            f'and were excluded from the totals above — worth checking the source export.</div>'
        )

    preview_badge = '<span class="badge-preview">PREVIEW DATA</span>' if is_preview else ""

    footer_note = (
        "Figures are computed live from the uploaded export against the same detection rules used in the "
        "Audit Dashboard tab. Cell-impact percentages are not mutually exclusive — several findings can be "
        "triggered by the same underlying line items."
    )
    if is_preview:
        footer_note = "This view is showing demo/preview data, not a real client export. " + footer_note

    out = EXEC_TEMPLATE
    out = out.replace("__CLIENT_INITIALS__", html_lib.escape(initials))
    out = out.replace("__TRIDANT_LOGO__", TRIDANT_LOGO_HTML)
    out = out.replace("__CLIENT_NAME__", html_lib.escape(client_name.upper()))
    out = out.replace("__PREVIEW_BADGE__", preview_badge)
    out = out.replace("__MODEL_LABEL__", html_lib.escape(model_line))
    out = out.replace("__HEADLINE__", html_lib.escape(headline))
    out = out.replace("__STATUS_COLOR__", status_color)
    out = out.replace("__STATUS_BG__", status_bg)
    out = out.replace("__STATUS_BORDER__", status_border)
    out = out.replace("__STATUS_LABEL__", band)
    out = out.replace("__VERDICT_TEXT__", verdict_text)
    out = out.replace("__GAUGE_COLOR__", gauge_color)
    out = out.replace("__GAUGE_PCT_LABEL__", gauge_pct_label)
    out = out.replace("__GAUGE_CAPTION__", gauge_caption)
    out = out.replace("__GAUGE_PCT_JS__", json.dumps(gauge_pct_js))
    out = out.replace("__KPI_TILES__", kpi_html)
    out = out.replace("__DATA_QUALITY_BANNER__", banner_html)
    out = out.replace("__FOOTER_NOTE__", html_lib.escape(footer_note))
    out = out.replace("__FINDINGS_JSON__", json.dumps(findings))
    return out

# ============================================================
# TAB 1 — Executive Summary (dynamic, per client, per upload)
# ============================================================
with tab_exec:
    if not data_ready:
        st.info("Upload an Anaplan export or turn on **🔍 Preview (Demo Data)** in the sidebar to generate the Executive Summary.")
    else:
        is_preview = (uploaded is None and demo_mode)
        findings = summarize_findings(result, cell_count_available, total_cells)

        exec_html = build_exec_html(
            client_name=client_name_input,
            model_label=model_label_input,
            scenario_label=scenario_label_input,
            is_preview=is_preview,
            modules_count=modules_count,
            line_items_count=line_items_count,
            cell_count_available=cell_count_available,
            total_cells=total_cells,
            top_n_actual=top_n_actual,
            top_n_pct=top_n_pct,
            top_n_cells=top_n_cells,
            largest_module_name=largest_module_name,
            largest_module_cells=largest_module_cells,
            health=health,
            band=band,
            capacity_cells=workspace_capacity_input,
            neg_cell_count=neg_cell_count,
            findings=findings,
        )

        n_findings = len(findings)
        approx_height = 1000 + n_findings * 120 + 200
        approx_height = max(1500, min(approx_height, 3600))

        components.html(exec_html, height=approx_height, scrolling=True)

# ============================================================
# TAB 2 — Audit Dashboard
# ============================================================
with tab_dashboard:
    if not data_ready:
        st.info("Upload Anaplan export or turn on **Preview (Demo Data)** in the sidebar.")
        st.stop()

    if len(df) > LARGE_FILE_ROW_LIMIT:
        st.warning(
            f"This file has {len(df):,} rows, above the {LARGE_FILE_ROW_LIMIT:,}-row "
            "comfort threshold for the daisy-chain and formula-parsing passes. "
            "The app will still run, but consider pre-filtering the export by module if it feels slow."
        )

    with st.expander("✅ Column Mapping (fixed by your rule)", expanded=False):
        st.write(f"Line Item (FIRST column): **{line_col_df}**")
        st.write(f"Module (LAST column): **{module_col_df}**")
        st.write(f"Formula (detected): **{formula_col}**")

    issue_labels, issue_severities, _ = extract_issue_metadata(flagged["Issues"])

    st.sidebar.header("Filters")
    selected_issues = st.sidebar.multiselect(
        "Show only rows containing these issue types",
        options=issue_labels,
        default=issue_labels if issue_labels else []
    )
    selected_severities = st.sidebar.multiselect(
        "Filter by severity",
        options=issue_severities,
        default=issue_severities if issue_severities else []
    )

    max_risk_all = int(result["Risk"].max() if len(result) else 0)
    c1, c2 = st.sidebar.columns(2)
    min_risk = c1.number_input("Minimum Risk score", min_value=0, value=0, step=1)
    max_risk = c2.number_input("Maximum Risk score", min_value=0, value=max_risk_all, step=1)

    def row_matches_filters(issues):
        if not issues:
            return False if selected_issues else True
        labels = [label for label, _, _ in issues]
        severities = [sev for _, sev, _ in issues]
        if selected_issues and not any(lbl in labels for lbl in selected_issues):
            return False
        if selected_severities and not any(s in severities for s in selected_severities):
            return False
        return True

    filtered_flagged = flagged[
        flagged["Issues"].apply(row_matches_filters)
        & (flagged["Risk"] >= min_risk)
        & (flagged["Risk"] <= max_risk)
    ].copy()

    st.metric("Model Health", f"{health:.1f} {band}")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Line Items", len(result))
    m2.metric("Flagged (total)", len(flagged))
    m3.metric("Flagged (shown)", len(filtered_flagged))

    st.subheader("Top Risk Line Items (filtered view)")
    top_risk_view = filtered_flagged.sort_values("Risk", ascending=False).head(200).copy()
    st.dataframe(top_risk_view, use_container_width=True)

    with st.expander("🔍 Drill Down (Top Risk Line Items)", expanded=False):
        if not top_risk_view.empty:
            top_risk_view["_SelectKey_"] = (
                top_risk_view["Module"].astype(str)
                + " | "
                + top_risk_view["Line Item"].astype(str)
                + " | Risk="
                + top_risk_view["Risk"].astype(int).astype(str)
                + " | #"
                + top_risk_view.index.astype(str)
            )

            selected_key = st.selectbox(
                "Select a line item to view details",
                options=top_risk_view["_SelectKey_"].tolist()
            )

            selected_row = top_risk_view[top_risk_view["_SelectKey_"] == selected_key].head(1)

            if not selected_row.empty:
                r = selected_row.iloc[0]
                st.markdown(f"**Module:** {r['Module']}")
                st.markdown(f"**Line Item:** {r['Line Item']}")
                st.markdown(f"**Risk:** {int(r['Risk'])}")
                st.markdown("**Issues:**")
                st.write(r["Issues"])
                st.markdown("**Refactor Suggestions:**")
                st.write(r["Refactor"])
                with st.expander("📌 Formula (click to expand)", expanded=False):
                    st.code(_format_anaplan_formula(str(r["Formula"])), language="text")
        else:
            st.info("No rows available in Top Risk table to drill down.")

    st.subheader("Issue Type Counts (filtered view)")
    issue_rows = []
    for issues in filtered_flagged["Issues"]:
        for label, sev, key in issues:
            issue_rows.append((label, key, sev))
    if issue_rows:
        issue_df = pd.DataFrame(issue_rows, columns=["Issue", "Key", "Severity"])
        counts = issue_df["Issue"].value_counts().reset_index()
        counts.columns = ["Issue", "Count"]
        st.table(counts)
    else:
        st.info("No issues match the current filters.")

    st.subheader("Module Risk Summary (filtered view)")
    if not filtered_flagged.empty:
        mod_risk_summary = (
            filtered_flagged.groupby("Module", as_index=False)
            .agg(Total_Risk=("Risk", "sum"), Flagged_Items=("Risk", "count"))
            .sort_values(["Total_Risk", "Flagged_Items"], ascending=[False, False])
        )
        st.dataframe(mod_risk_summary.head(100), use_container_width=True)
        st.bar_chart(mod_risk_summary.set_index("Module")["Total_Risk"].head(25))
    else:
        st.info("No flagged items to summarize by module.")

    st.divider()
    st.subheader("Capacity & Performance Hotspots")

    if cell_count_available:
        if neg_cell_count > 0:
            st.warning(f"⚠️ {neg_cell_count} row(s) have a negative **Cell Count** — check the source export.")
        if cell_num_all is not None and cell_num_all.notna().sum() > 0:
            p999 = cell_num_all.quantile(0.999)
            outlier_count = int((cell_num_all > p999).sum()) if pd.notna(p999) else 0
            if outlier_count > 0:
                st.caption(f"ℹ️ {outlier_count} row(s) exceed the 99.9th percentile of Cell Count (> {p999:,.0f}) — worth a manual sanity check.")

        if not mod_sum.empty:
            top_modules = mod_sum.head(10)[["Module", "Cell Count (raw)", "Size (GB)"]]
            col_left, col_right = st.columns([2, 1])
            with col_left:
                st.markdown(f"**Top 10 Biggest Modules by `Cell Count`** ({agg_method.upper()} per module)  \n(Unit: Cells + GB)")
                st.dataframe(top_modules, use_container_width=True)
            with col_right:
                st.bar_chart(top_modules.set_index("Module")["Size (GB)"], use_container_width=True)
        else:
            st.info("No numeric values found in **Cell Count** to compute top modules.")
    else:
        st.info("Expected a **Cell Count** column (e.g., `Cell Count`).")

    if calc_time_col_exact and calc_time_col_exact in df.columns:
        eff_raw = df[calc_time_col_exact].astype(str).str.strip()
        eff_num = (
            eff_raw.str.replace("%", "", regex=False)
            .str.replace(",", "", regex=False)
            .replace({"": np.nan, "nan": np.nan, "None": np.nan})
        )
        eff_num = pd.to_numeric(eff_num, errors="coerce")
        neg_count_eff = int((eff_num < 0).sum())
        if neg_count_eff > 0:
            st.warning(f"⚠️ {neg_count_eff} row(s) have a negative **Calculation Effort** — check the source export.")

        tmp = pd.DataFrame({
            "Module": df["_ModuleResolved_"],
            "Line Item": df[line_col_df].astype(str),
            "Calculation Effort": eff_num
        }).dropna(subset=["Calculation Effort"])

        if tmp.empty:
            st.info("No numeric values found in **Calculation Effort**.")
        else:
            top_calc = tmp.sort_values("Calculation Effort", ascending=False).head(10)
            st.markdown("**Top 10 Highest Calculation Effort Line Items**")
            st.dataframe(top_calc, use_container_width=True)
    else:
        st.info("Expected a **Calculation Effort** column (e.g., `Calculation Effort`).")

    st.divider()
    st.download_button(
        "Download Full Audit (all rows)",
        data=result.to_csv(index=False).encode("utf-8"),
        file_name="anaplan_full_audit.csv",
        mime="text/csv"
    )
    st.download_button(
        "Download Filtered Audit (shown rows)",
        data=filtered_flagged.to_csv(index=False).encode("utf-8"),
        file_name="anaplan_filtered_audit.csv",
        mime="text/csv"
    )

    with st.expander("Legend and Key (click to expand)"):
        st.markdown(
            "### Columns\n"
            "- **Module**: LAST column from your export.\n"
            "- **Line Item**: FIRST column from your export.\n"
            "- **Formula**: Formula/Expression column.\n"
            "- **Risk**: Sum of severity weights for detected issues"
            + (f" (capped at {RISK_CAP})." if RISK_CAP else " (uncapped).") + "\n"
            "- **Issues**: (label, severity, key).\n"
            "- **Refactor**: Suggested refactor per rule."
        )
        st.markdown(
            "### POST Rules (corrected)\n"
            "- **POST + LOOKUP (nested)**: flags if `[...LOOKUP: ...]` appears inside the true, "
            "paren-depth-matched `POST(...)` call.\n"
            "- **POST + SUM (nested)**: same, for `[...SUM: ...]`.\n"
            "- **POST inside IF**: flags `THEN/ELSE ... POST(...)` within the same branch."
        )
        st.markdown(f"### Module Size Aggregation\nCurrently using **{agg_method.upper()}** per module (configurable in the sidebar).")

    st.divider()
    st.subheader("Top 5 Daisy Chain Modules (Advanced Dependency Analysis)")

    all_line_items_upper = result["Line Item"].astype(str).str.upper().dropna().unique().tolist()[:300]
    all_modules_upper = result["Module"].astype(str).str.upper().dropna().unique().tolist()[:200]
    line_item_pattern = build_entity_pattern(all_line_items_upper)
    module_pattern = build_entity_pattern(all_modules_upper)

    def count_cross_line_refs(formula_upper, own_name_upper):
        if line_item_pattern is None:
            return 0
        matches = set(line_item_pattern.findall(formula_upper))
        matches.discard(own_name_upper)
        return len(matches)

    def count_inter_module_refs(formula_upper, current_module_upper):
        if module_pattern is None:
            return 0
        matches = set(module_pattern.findall(formula_upper))
        matches.discard(current_module_upper)
        return len(matches)

    with st.spinner("Scanning cross-references for daisy-chain analysis…"):
        daisy_rows = []
        for i, row in result.iterrows():
            formula = str(row["Formula"])
            formula_up = formula.upper()
            module = str(row["Module"])
            line_item = str(row["Line Item"])
            cross_refs = count_cross_line_refs(formula_up, line_item.upper())
            inter_refs = count_inter_module_refs(formula_up, module.upper())
            calc_tokens = int(feats.loc[i, "func_density_count"]) if i in feats.index else 0
            daisy_score = (cross_refs * w_cross_line) + (inter_refs * w_inter_module) + (calc_tokens * w_calc_tokens)
            daisy_rows.append({
                "Module": module, "Line Item": line_item, "Daisy_Score": daisy_score,
                "Cross-Line Refs": cross_refs, "Inter-Module Refs": inter_refs,
                "Calc Tokens": calc_tokens, "Formula": formula
            })

    daisy_df = pd.DataFrame(daisy_rows)
    module_daisy = (
        daisy_df.groupby("Module", as_index=False)
        .agg(Daisy_Score=("Daisy_Score", "sum"), Max_Cross_Line=("Cross-Line Refs", "max"),
             Max_Inter_Module=("Inter-Module Refs", "max"), Avg_Calc_Tokens=("Calc Tokens", "mean"),
             Line_Items=("Line Item", "count"))
        .sort_values("Daisy_Score", ascending=False)
    )
    top5 = module_daisy.head(5)
    st.markdown("### 🔥 Top 5 Modules by Daisy Chain Risk")
    st.dataframe(top5, use_container_width=True)

    st.markdown("### 🔍 Drill Down into a Module")
    if not top5.empty:
        selected_mod = st.selectbox("Select a module", options=top5["Module"].tolist())
        mod_view = daisy_df[daisy_df["Module"] == selected_mod].sort_values("Daisy_Score", ascending=False)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Daisy Score", int(mod_view["Daisy_Score"].sum()))
        c2.metric("Max Cross-Line Depth", int(mod_view["Cross-Line Refs"].max()))
        c3.metric("Max Inter-Module Hops", int(mod_view["Inter-Module Refs"].max()))
        st.markdown("#### High Daisy-Chain Line Items")
        st.dataframe(mod_view.head(30), use_container_width=True)
    else:
        st.info("No modules found for daisy chain ranking.")

    st.divider()
    st.subheader("Top 10 Worst Performance / Heavy Anaplan Functions")

    FUNC_COST = {
        "POST + LOOKUP (nested)": 15, "POST + SUM (nested)": 13, "POST inside IF": 14,
        "TIMESUM": 12, "POST": 11, "LOOKUP": 9, "SUM": 8, "OFFSET / MOVINGSUM": 8,
        "CUMULATE": 7, "SELECT": 6, "FINDITEM": 6, "RANK": 5, "IF": 4,
    }
    func_usage = {
        "POST + LOOKUP (nested)": feats["has_post_lookup_nested"].sum(),
        "POST + SUM (nested)": feats["has_post_sum_nested"].sum(),
        "POST inside IF": feats["has_post_inside_if"].sum(),
        "TIMESUM": feats["has_timesum"].sum(),
        "POST": feats["has_post"].sum(),
        "LOOKUP": feats["count_lookup"].sum(),
        "SUM": feats["count_sum"].sum(),
        "OFFSET / MOVINGSUM": feats["count_offsetlike"].sum(),
        "CUMULATE": feats["count_cumulate"].sum(),
        "SELECT": feats["count_select"].sum(),
        "FINDITEM": feats["count_finditem"].sum(),
        "RANK": feats["count_rank"].sum(),
        "IF": feats["count_if"].sum(),
    }
    func_rows = []
    for fn, count in func_usage.items():
        impact = float(count) * float(FUNC_COST.get(fn, 1))
        func_rows.append({
            "Function / Pattern": fn, "Usage Count": int(count), "Cost Weight": int(FUNC_COST.get(fn, 1)),
            "Total Impact Score": int(impact),
            "Recommended Refactor": {
                "POST + LOOKUP (nested)": REFACTOR["post_lookup"], "POST + SUM (nested)": REFACTOR["post_sum"],
                "POST inside IF": REFACTOR["post_if"], "TIMESUM": REFACTOR["timesum"],
                "POST": "Move POST to dedicated output module/line item", "LOOKUP": "Stage LOOKUP into helper line item",
                "SUM": "Aggregate once and reuse result", "OFFSET / MOVINGSUM": "Pre-calculate rolling values",
                "CUMULATE": "Use running total module", "SELECT": "Replace with mapping module",
                "FINDITEM": "Pre-map text to list item", "RANK": "Pre-rank in separate module",
                "IF": "Replace IF chains with mapping",
            }.get(fn, "Stage logic into helper module"),
        })
    func_df = pd.DataFrame(func_rows).sort_values("Total Impact Score", ascending=False).head(10)
    st.dataframe(func_df, use_container_width=True)
    st.bar_chart(func_df.set_index("Function / Pattern")["Total Impact Score"], use_container_width=True)

    with st.expander("Diagnostics — Module & Cell Count (click to expand)", expanded=False):
        st.markdown(
            "- Module is taken from **LAST column**, and forward-filled if blank.\n"
            f"- Cell Count uses **{agg_method.upper()} per module** (consistent with the roll-up above)."
        )
        if cell_count_available and cell_num_all is not None:
            mod_frame = pd.DataFrame({"Module": df["_ModuleResolved_"], "CellNum": cell_num_all}).dropna(subset=["CellNum"])
            if not mod_frame.empty:
                per_mod = (
                    mod_frame.groupby("Module", as_index=False)
                    .agg(Max_Cell=("CellNum", "max"), Sum_Cell=("CellNum", "sum"), Rows=("CellNum", "count"))
                    .sort_values("Max_Cell", ascending=False)
                )
                st.dataframe(per_mod.head(50), use_container_width=True)
            else:
                st.info("No numeric rows available to compute per-module aggregates.")
        else:
            st.info("No Cell Count column detected for diagnostics.")

# ============================================================
# TAB 3 — Rules, Bugs & Fix Reference
# ============================================================
with tab_reference:
    st.header("📋 Rules, Bugs & Fix Reference")
    st.caption(
        "Everything the original script did, everything that was found to be broken or "
        "improvable, and exactly what changed — in the order it should be prioritized."
    )

    st.subheader("Prioritized fix log")
    priority_data = [
        {"Priority": 1, "Category": "Bug", "Issue": "Cross-line / inter-module substring false positives",
         "Fix Applied": "Single compiled word-boundary alternation regex per candidate set", "Status": "✅ Implemented"},
        {"Priority": 2, "Category": "Bug", "Issue": "Cell Count SUM vs MAX inconsistency",
         "Fix Applied": "User-selectable aggregation method (MAX default), applied consistently everywhere", "Status": "✅ Implemented"},
        {"Priority": 3, "Category": "Bug", "Issue": "POST+LOOKUP / POST+SUM nested-paren false negatives",
         "Fix Applied": "Depth-aware character scan finds the true matching close-paren of POST(...)", "Status": "✅ Implemented"},
        {"Priority": 4, "Category": "Bug", "Issue": "'POST inside IF' regex was greedy and unanchored",
         "Fix Applied": "Tightened to THEN/ELSE-local match that stops at the next IF token", "Status": "✅ Implemented"},
        {"Priority": 5, "Category": "Bug", "Issue": "nested_if_med slider could crash if nested_if_high was lowered",
         "Fix Applied": "Clamp preserved from prior patch; boundary explicitly documented", "Status": "✅ Implemented"},
        {"Priority": 6, "Category": "Design", "Issue": "func_token_count conflated function density with true daisy-chain dependency",
         "Fix Applied": "Split into row-level 'High Function Density' vs module-level Daisy Chain", "Status": "✅ Implemented"},
        {"Priority": 7, "Category": "Design", "Issue": "Multiple LOOKUP always 'high' regardless of context",
         "Fix Applied": "Documented as a future enhancement, not auto-applied", "Status": "🟡 Documented only"},
        {"Priority": 8, "Category": "Design", "Issue": "Overlapping flags can inflate Risk score",
         "Fix Applied": "Optional per-line-item Risk cap, opt-in via sidebar toggle", "Status": "✅ Implemented (opt-in)"},
        {"Priority": 9, "Category": "Design", "Issue": "find_col() had a narrow synonym list",
         "Fix Applied": "Expanded keys list for Formula / Cell Count / Calc Effort", "Status": "✅ Implemented"},
        {"Priority": 10, "Category": "Design", "Issue": "detect_row/risk relied on module-level globals",
         "Fix Applied": "Refactored to accept thresholds/weights as explicit parameters", "Status": "✅ Implemented"},
        {"Priority": 11, "Category": "UX", "Issue": "Daisy score weights were hidden magic numbers",
         "Fix Applied": "Exposed as sidebar sliders", "Status": "✅ Implemented"},
        {"Priority": 12, "Category": "UX", "Issue": "Drilldown _SelectKey_ could collide on duplicate rows",
         "Fix Applied": "Row index appended to guarantee a unique key", "Status": "✅ Implemented"},
        {"Priority": 13, "Category": "UX", "Issue": "No progress indication on large files",
         "Fix Applied": "st.spinner around feature extraction and the daisy-chain scan", "Status": "✅ Implemented"},
        {"Priority": 14, "Category": "UX", "Issue": "No warning on very large uploads",
         "Fix Applied": "Row-count warning banner above a configurable threshold", "Status": "✅ Implemented"},
        {"Priority": 15, "Category": "Robustness", "Issue": "load_file() silently discarded the first XLSX engine error",
         "Fix Applied": "Both exception messages captured and surfaced together", "Status": "✅ Implemented"},
        {"Priority": 16, "Category": "Robustness", "Issue": "No sanity check on negative/outlier Cell Count values",
         "Fix Applied": "Warning banners for negative and 99.9th-percentile outlier values", "Status": "✅ Implemented"},
        {"Priority": 17, "Category": "Robustness", "Issue": "Regex boundary assumptions untested against real exports",
         "Fix Applied": "Documented; recommend a regression test suite against real anonymized formulas", "Status": "🟡 Documented, needs real-data validation"},
        {"Priority": 18, "Category": "Feature", "Issue": "No client-facing executive view; a one-off static report was hardcoded to a single client",
         "Fix Applied": "Added a dynamic Executive Summary tab: client name / model / scenario are inputs, "
                         "every number is computed live from the uploaded file via the same rules as the Audit Dashboard",
         "Status": "✅ Implemented"},
    ]
    priority_df = pd.DataFrame(priority_data)
    st.dataframe(priority_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("How the Executive Summary tab stays dynamic")
    st.markdown(
        "- **Client name, model name, scenario label** are sidebar text inputs (Report Details), never "
        "hardcoded — the model name defaults to the uploaded filename but can be overridden.\n"
        "- **Every KPI, gauge value, and finding** is computed from `result`, `feats`, and `mod_sum` — the "
        "exact same DataFrames the Audit Dashboard tab uses — so the two tabs can never disagree.\n"
        "- **The verdict paragraph** is templated by the computed Model Health band (Excellent / Good / Fair / "
        "Critical), not a fixed sentence — it reads differently for a healthy model than a critical one.\n"
        "- **Findings only appear if actually detected** — a clean model shows an empty-state message instead "
        "of a fabricated table.\n"
        "- **Cell-impact numbers are omitted, not guessed**, whenever the export has no Cell Count column."
    )