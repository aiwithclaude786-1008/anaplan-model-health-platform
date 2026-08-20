# app/ui/components.py
# ============================================================
# Small shared UI helpers so every page renders severity/
# confidence consistently with the Tridant palette (branding.py)
# instead of each page inventing its own colors.
# ============================================================
from __future__ import annotations

import re

import streamlit as st

from app.branding import SEVERITY_COLORS, CONFIDENCE_COLORS, TEXT_STRONG


def severity_badge(severity: str) -> str:
    color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["medium"])
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:5px;'
        f'font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;'
        f'color:{color};background:{color}1A;border:1px solid {color}55;">{severity}</span>'
    )


def confidence_badge(confidence: str) -> str:
    color = CONFIDENCE_COLORS.get(confidence, CONFIDENCE_COLORS["Estimated"])
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:5px;'
        f'font-size:11px;font-weight:600;color:{color};background:{color}1A;'
        f'border:1px solid {color}55;">{confidence}</span>'
    )


def kpi_row(items):
    """items: list of (value, label, help_text)."""
    cols = st.columns(len(items))
    for col, (value, label, help_text) in zip(cols, items):
        col.metric(label, value, help=help_text or None)


def render_badges_html(pairs):
    """pairs: list of (label_html) strings already built by severity_badge/confidence_badge."""
    st.markdown(" &nbsp; ".join(pairs), unsafe_allow_html=True)


def format_anaplan_formula(formula: str) -> str:
    """Pretty-printer for the formula detail panel -- migrated as-is
    from the original app.py's _format_anaplan_formula()."""
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


def fmt_num(n) -> str:
    if n is None:
        return "N/A"
    try:
        return f"{float(n):,.0f}"
    except (TypeError, ValueError):
        return str(n)


def fmt_pct(n, digits=1) -> str:
    if n is None:
        return "N/A"
    try:
        return f"{float(n):.{digits}f}%"
    except (TypeError, ValueError):
        return str(n)


def section_header(title: str, description: str = ""):
    st.markdown(f"### {title}")
    if description:
        st.caption(description)
