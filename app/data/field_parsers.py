# app/data/field_parsers.py
# ============================================================
# Real Anaplan "Module List Export" files encode Format and
# Summary as JSON blobs, e.g.
#   Format:  {"minimumSignificantDigits":-1,...,"dataType":"NUMBER"}
#   Summary: {"summaryMethod":"SUM","timeSummaryMethod":"SUM",...}
# These helpers extract the human-relevant field from either the
# JSON form or a plain string fallback (some exports/demo data
# just put "NUMBER" / "SUM" directly). Never raises -- worst case
# returns "Unknown" so a malformed cell degrades gracefully rather
# than crashing the pipeline.
# ============================================================
from __future__ import annotations

import json
import re
from typing import Optional


def extract_format_type(value) -> str:
    if value is None:
        return "Unknown"
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return "Unknown"
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            dt = obj.get("dataType")
            if dt:
                return str(dt).upper()
        except Exception:
            pass
        return "Unknown"
    return s.upper()


def extract_summary_method(value) -> str:
    if value is None:
        return "Unknown"
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return "Unknown"
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            sm = obj.get("summaryMethod")
            if sm:
                return str(sm).upper()
        except Exception:
            pass
        return "Unknown"
    return s.upper()


# Naming-convention based module classification (DISCO: Data / Input /
# System / Calc / Output). This is a Tridant PLANUAL consulting
# convention based on module-name prefixes -- NOT a real Anaplan
# metadata field -- so callers should treat the result as an
# INFERENCE, not a fact, and it degrades to "Other" for any module
# that doesn't follow the convention.
_DISCO_PATTERNS = [
    ("Data", re.compile(r"\bDAT\d|\bDATA\b|^DAT\b", re.I)),
    ("System", re.compile(r"\bSYS\d|^SYS\b|^#", re.I)),
    ("Calc", re.compile(r"\bCALC\d|\bCALC\b|\bPA\d", re.I)),
    ("Output", re.compile(r"\bPNL\d|\bEX\d|\bEXPORT\b|\bREPORT\b", re.I)),
    ("Input", re.compile(r"\bINPUT\b|\bIBT\d|\bPLN\b", re.I)),
]


def classify_module_type(module_name: str) -> str:
    name = str(module_name or "")
    for label, pattern in _DISCO_PATTERNS:
        if pattern.search(name):
            return label
    return "Other"


def is_full_time_calendar(time_range_value) -> bool:
    """True when a line item's Time Range is left on the full/default
    model calendar rather than a scoped range."""
    s = str(time_range_value or "").strip().lower()
    if not s or s in ("nan", "not applicable", "-"):
        return False
    return s in ("model calendar", "all periods", "full calendar")


def is_select_time_scoped(select_target: str) -> bool:
    """PLANUAL: SELECT is only acceptable when it targets TIME.All Periods
    (or an equivalent explicit time scope) rather than a hardcoded member."""
    s = str(select_target or "")
    return bool(re.search(r"\bTIME\s*\.\s*ALL\s*PERIODS\b", s, re.I))
