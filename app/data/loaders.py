# app/data/loaders.py
# ============================================================
# File loading + demo dataset, migrated from the original app.py
# load_file()/build_demo_df(). Behavior is unchanged; only the
# location moved so main.py and tests can both import it.
# ============================================================
from __future__ import annotations

import random
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def load_file(_bytes, filename: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
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


DEMO_SAMPLES = [
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


def build_demo_df(n_rows: int = 80, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)

    rows = []
    for i in range(n_rows):
        mod, li, f = random.choice(DEMO_SAMPLES)
        if random.random() < 0.25:
            f = f.replace("LOOKUP", "Lookup")
        if random.random() < 0.25:
            f = f.replace("SUM", "sum")
        if random.random() < 0.20:
            f = f.replace("POST", "Post")

        cell_count = float(np.random.lognormal(mean=16.0, sigma=0.8))
        calc_effort = float(np.random.lognormal(mean=5.1, sigma=0.7))

        rows.append({
            "Line Item Name": f"{li} {i + 1}",
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
