# app/branding.py
# ============================================================
# Single source of Tridant brand tokens (see
# tridant_brand_reference.md for provenance -- values marked
# Measured were pulled directly from tridant.com's computed
# styles; Derived values are a consistent extension where the
# marketing site had no equivalent element). Every UI page and
# every report imports from here so the brand never drifts
# between pages, instead of living only in one HTML template
# the way it did in the original app.py.
# ============================================================
from __future__ import annotations

# ---- Core brand (Measured) ----
ACCENT = "#00ADEF"
ACCENT_DEEP = "#0090C9"
ON_ACCENT = "#FFFFFF"
BODY_TEXT = "#5A5A5A"
HEADER_BG = "#9C66A0"
FONT_FAMILY = "'Source Sans Pro', -apple-system, sans-serif"
GOOGLE_FONT_URL = "https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap"
RADIUS = "4px"

# ---- Derived / supporting palette ----
SURFACE = "#F6F8F9"
SURFACE_ALT = "#EEF2F4"
BORDER = "rgba(20,24,27,0.08)"
BORDER_STRONG = "rgba(20,24,27,0.14)"
TEXT_STRONG = "#2B2E31"
TEXT_FAINT = "#8B9096"
SHADOW = "0 12px 30px -16px rgba(20,24,27,0.16)"

# ---- Severity / status colors (Derived, consistent tonal family) ----
SEVERITY_COLORS = {
    "critical": "#C0392B",
    "high": "#C97A1E",
    "medium": "#3E7C90",
    "low": "#6B7268",
}
STATUS_COLORS = {
    "Excellent": ("#2F8F57", "rgba(47,143,87,0.08)", "rgba(47,143,87,0.35)"),
    "Good": ("#5C8A3A", "rgba(92,138,58,0.08)", "rgba(92,138,58,0.35)"),
    "Fair": ("#C97A1E", "rgba(201,122,30,0.08)", "rgba(201,122,30,0.35)"),
    "Critical": ("#D64545", "rgba(214,69,69,0.08)", "rgba(214,69,69,0.35)"),
}

CONFIDENCE_COLORS = {
    "Measured": "#2F8F57",
    "Estimated": "#3E7C90",
    "Potential": "#C97A1E",
    "Requires validation": "#8B9096",
}

TRIDANT_LOGO_B64 = (
    "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"
)


def inject_streamlit_theme_css() -> str:
    """Global CSS applied once at app startup so every native
    Streamlit page (not just the HTML report tabs) picks up the
    Tridant tokens: font, accent buttons/tabs, header bar."""
    return f"""
<style>
@import url('{GOOGLE_FONT_URL}');
html, body, [class*="css"] {{ font-family: {FONT_FAMILY}; }}
.stButton>button, .stDownloadButton>button {{
    background-color:{ACCENT}; color:{ON_ACCENT}; border:none; border-radius:{RADIUS}; font-weight:600;
}}
.stButton>button:hover, .stDownloadButton>button:hover {{ background-color:{ACCENT_DEEP}; color:{ON_ACCENT}; }}
.stTabs [aria-selected="true"] {{ color:{ACCENT}; border-bottom-color:{ACCENT}; }}
[data-testid="stMetricValue"] {{ color:{TEXT_STRONG}; }}
[data-testid="stHeader"] {{ background-color:{HEADER_BG}; }}
</style>
"""
