# tests/conftest.py
# ============================================================
# Synthetic fixtures shaped like a real Anaplan "Module List
# Export" (confirmed against a live client export: Line Item /
# Format / Formula / Summary / Applies To / Time Scale / Time
# Range / Versions / Cell Count / Notes / Module Name), but with
# entirely fabricated module/line-item names and values -- no
# real client data anywhere in the test suite.
# ============================================================
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def raw_export_df() -> pd.DataFrame:
    rows = [
        # Full-grain cluster: 4 items in CALC01 sharing an identical cell count.
        dict(name="Revenue A", format="NUMBER", formula="Sales[SUM: Region.Map, LOOKUP: Version.Cur]",
             summary="SUM", applies_to="Product, Region, Time", time_scale="Month", time_range="Model Calendar",
             versions="All Versions", cell_count=1000000, calc_effort=1.0, notes="", module="CALC01 Var P&L"),
        dict(name="Revenue B", format="NUMBER", formula="Cost[SUM: Region.Map, LOOKUP: Version.Cur]",
             summary="SUM", applies_to="Product, Region, Time", time_scale="Month", time_range="Model Calendar",
             versions="All Versions", cell_count=1000000, calc_effort=1.0, notes="", module="CALC01 Var P&L"),
        dict(name="Revenue C", format="NUMBER", formula="Margin[SUM: Region.Map, LOOKUP: Version.Cur]",
             summary="SUM", applies_to="Product, Region, Time", time_scale="Month", time_range="Model Calendar",
             versions="All Versions", cell_count=1000000, calc_effort=1.0, notes="Rate driver, see SYS01", module="CALC01 Var P&L"),
        dict(name="Revenue D", format="NUMBER",
             formula="IF A THEN X ELSE IF B THEN Y ELSE IF C THEN Z ELSE IF D THEN W ELSE IF E THEN V ELSE U",
             summary="SUM", applies_to="Product, Region, Time", time_scale="Month", time_range="Model Calendar",
             versions="All Versions", cell_count=1000000, calc_effort=1.0, notes="", module="CALC01 Var P&L"),
        # Subsidiary view: Applies To differs from the module's modal value above.
        dict(name="Filter Flag", format="BOOLEAN", formula="1",
             summary="NONE", applies_to="Users, SKU", time_scale="Month", time_range="Actuals History",
             versions="All Versions", cell_count=500, calc_effort=0.1, notes="Flag for UI filter", module="CALC01 Var P&L"),
        # SELECT hardcoded vs TIME.All Periods acceptable.
        dict(name="Hardcoded Select", format="NUMBER", formula="Amount[SELECT: FY24]",
             summary="NONE", applies_to="Product, Region, Time", time_scale="Month", time_range="Model Calendar",
             versions="All Versions", cell_count=2000, calc_effort=0.2, notes="", module="SYS01 Mapping"),
        dict(name="Time Scoped Select", format="NUMBER", formula="Revenue[SELECT: TIME.All Periods]",
             summary="NONE", applies_to="Product", time_scale="Month", time_range="Actuals History",
             versions="All Versions", cell_count=300, calc_effort=0.1, notes="", module="SYS01 Mapping"),
        # TEXT in a Calc module.
        dict(name="Account Code", format="TEXT", formula="'#Export'.Account Code",
             summary="NONE", applies_to="Product", time_scale="Month", time_range="Actuals History",
             versions="All Versions", cell_count=800, calc_effort=0.1, notes="", module="CALC02 Export"),
        # Clean, unflagged line item.
        dict(name="Simple Constant", format="NUMBER", formula="1",
             summary="NONE", applies_to="Product", time_scale="Month", time_range="Actuals History",
             versions="All Versions", cell_count=100, calc_effort=0.05, notes="Static flag", module="DAT01 Inputs"),
        # POST + LOOKUP nested, high risk formula.
        dict(name="Transfer Post", format="NUMBER", formula="POST(Inv.Delta, Map.Tgt[LOOKUP: Map.Rule])",
             summary="NONE", applies_to="Product", time_scale="Month", time_range="Actuals History",
             versions="All Versions", cell_count=1500, calc_effort=0.3, notes="", module="DAT02 Transfers"),
    ]
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "name": "Line Item Name", "format": "Format", "formula": "Formula", "summary": "Summary",
        "applies_to": "Applies To", "time_scale": "Time Scale", "time_range": "Time Range",
        "versions": "Versions", "cell_count": "Cell Count", "calc_effort": "Calculation Effort",
        "notes": "Notes", "module": "Module Name",
    })
    cols = ["Line Item Name", "Format", "Formula", "Summary", "Applies To", "Time Scale", "Time Range",
            "Versions", "Cell Count", "Calculation Effort", "Notes", "Module Name"]
    return df[cols]
