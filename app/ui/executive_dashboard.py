# app/ui/executive_dashboard.py
# ============================================================
# Master spec section 15 -- redesigned Executive Dashboard for
# senior stakeholders. Rebuilds the original app.py's dynamic,
# brand-consistent HTML exec summary against the new
# AnalysisResult (so client name / model name / scenario stay
# free-text inputs and every number is still computed live from
# the same rule engine as every other page), and adds the
# section-15 KPI set (health score, size risk, performance risk,
# optimization potential, critical/high issue counts).
# ============================================================
from __future__ import annotations

import html as html_lib
from collections import OrderedDict

import streamlit.components.v1 as components

from app.branding import (
    TRIDANT_LOGO_B64, ACCENT, ACCENT_DEEP, ON_ACCENT, BODY_TEXT, HEADER_BG, TEXT_STRONG, TEXT_FAINT,
    SURFACE, SURFACE_ALT, BORDER, BORDER_STRONG, RADIUS, SHADOW, GOOGLE_FONT_URL, STATUS_COLORS,
    SEVERITY_COLORS,
)
from app.analysis.pipeline import AnalysisResult
from app.analysis.size_analysis import cells_to_gb

TRIDANT_LOGO_HTML = f'<img class="logo" alt="Tridant" src="data:image/png;base64,{TRIDANT_LOGO_B64}" style="height:28px;width:auto;display:block;">'


def _summarize_findings_by_area(result: AnalysisResult):
    agg = OrderedDict()
    for f in result.findings:
        key = f.name
        if key not in agg:
            agg[key] = {"severity": f.severity, "rule": f.recommendation, "confidence": f.confidence,
                        "items": 0, "cell_impact": 0.0, "has_any_cell": False, "category": f.category}
        a = agg[key]
        a["items"] += 1
        if f.cell_impact:
            a["cell_impact"] += f.cell_impact
            a["has_any_cell"] = True

    total_cells = result.size.total_cells
    findings = []
    for name, a in agg.items():
        pct = (a["cell_impact"] / total_cells * 100.0) if (a["has_any_cell"] and total_cells > 0) else None
        findings.append({
            "name": name, "rule": a["rule"], "severity": a["severity"], "confidence": a["confidence"],
            "items": a["items"], "cellImpact": a["cell_impact"] if a["has_any_cell"] else None, "pctModel": pct,
            "category": a["category"],
        })
    findings.sort(key=lambda f: (f["pctModel"] is None, -(f["pctModel"] or 0), -f["items"]))
    return findings


def render_executive_dashboard(result: AnalysisResult, client_name: str, model_label: str,
                                scenario_label: str, is_preview: bool, capacity_cells: float):
    client_name = (client_name or "").strip() or "Your Organization"
    initials = "".join([w[0] for w in client_name.split()[:2]]).upper() or "CO"
    model_bits = [b for b in [model_label.strip(), scenario_label.strip()] if b]
    model_line = " -- ".join(model_bits) if model_bits else "Uploaded Blueprint"

    size = result.size
    health = result.health
    status_color, status_bg, status_border = STATUS_COLORS.get(health.band, STATUS_COLORS["Fair"])

    critical_n = sum(1 for f in result.findings if f.severity == "critical")
    high_n = sum(1 for f in result.findings if f.severity == "high")
    opp_dim = health.dimension("optimization_opportunity")

    total_cells_fmt = f"{size.total_cells:,.0f}" if size.cell_count_available and size.total_cells > 0 else None
    top_n_pct_fmt = f"{size.top_n_pct:.0f}%" if size.top_n_pct is not None else None
    top_n_label = f"top {size.top_n_actual} module{'s' if size.top_n_actual != 1 else ''}"

    if not size.cell_count_available:
        verdict = (f"No Cell Count column was found in this export, so size/capacity metrics aren't available. "
                    f"The rule-based findings below are still fully computed from "
                    f"<b>{size.line_items_count:,} line items</b> across <b>{size.modules_count:,} modules</b>.")
        headline = f"Structural findings for {html_lib.escape(client_name)}, sized by rule violations only."
    else:
        verdict = (
            f"<b>{html_lib.escape(client_name)}</b>'s model is carrying <b>{total_cells_fmt} allocated cells</b> "
            f"({cells_to_gb(size.total_cells):.2f} GB-equivalent) across <b>{size.modules_count:,} modules</b>. "
            f"The {top_n_label} account for <b>{top_n_pct_fmt}</b> of that footprint. Overall model health "
            f"scores <b>{health.overall:.0f}/100 ({health.band})</b>, with <b>{critical_n}</b> critical and "
            f"<b>{high_n}</b> high-severity findings."
        )
        headline = {
            "Critical": "Space is concentrated, not diffuse -- which means it's fixable.",
            "Fair": "A moderate amount of structural risk, worth a scheduled clean-up.",
            "Good": "Generally healthy structure -- a few pockets worth a look.",
            "Excellent": "Strong structural health across the model.",
        }.get(health.band, "Structural findings for this model.")

    findings = _summarize_findings_by_area(result)

    def kpi(val, lbl, tip, flag=False):
        cls = "kpi flag" if flag else "kpi"
        return (f'<div class="{cls}"><div class="val">{html_lib.escape(str(val))}</div>'
                f'<div class="lbl">{html_lib.escape(lbl)}</div><div class="tip">{html_lib.escape(tip)}</div></div>')

    tiles = [
        kpi(total_cells_fmt or "N/A", "Allocated cells", "Total cells across all modules and line items.",
            flag=(health.band == "Critical")),
        kpi(f"{size.modules_count:,}", "Modules", "Total module count detected in this export."),
        kpi(f"{size.line_items_count:,}", "Line items", "Total line items across all modules."),
        kpi(f"{health.overall:.0f}", "Health score", f"Overall model health, banded {health.band}.",
            flag=(health.band == "Critical")),
        kpi(f"{critical_n + high_n}", "Critical + high issues", "Count of critical- and high-severity findings.",
            flag=(critical_n > 0)),
        kpi(f"{opp_dim.score:.0f}%" if opp_dim else "N/A", "Optimization potential",
            "Share of model cells touched by at least one size- or performance-affecting finding."),
    ]
    if capacity_cells and capacity_cells > 0 and size.cell_count_available and size.total_cells > 0:
        used_pct = size.total_cells / capacity_cells * 100.0
        tiles.append(kpi(f"{used_pct:.0f}%", "Of stated capacity",
                          f"Based on the workspace capacity entered ({capacity_cells:,.0f} cells).",
                          flag=(used_pct >= 80)))
    kpi_html = "".join(tiles)

    dq = result.data_quality
    banner_html = ""
    if dq.score < 90:
        banner_html = (f'<div class="banner">Data quality score: <b>{dq.score:.0f}/100</b> -- '
                        f'{len(dq.issues)} check(s) flagged. See the Data Quality page for detail.</div>')

    preview_badge = '<span class="badge-preview">PREVIEW DATA</span>' if is_preview else ""

    rows_html = []
    for f in findings:
        sev_color = SEVERITY_COLORS.get(f["severity"], SEVERITY_COLORS["medium"])
        pct_label = f'{f["pctModel"]:.1f}% of model' if f["pctModel"] is not None else "not sized"
        cell_label = f'{f["cellImpact"]:,.0f}' if f["cellImpact"] is not None else "not sized"
        rows_html.append(f"""
        <div class="frow">
          <div class="frow-head">
            <div class="fh-title"><div class="fh-name">{html_lib.escape(f["name"])}</div>
              <div class="fh-rule">{html_lib.escape(f["rule"])}</div></div>
            <div class="fh-impact"><div class="fh-impact-track"><div class="fh-impact-fill" style="width:{min(f['pctModel'] or 0, 100)}%;background:{sev_color};"></div></div>
              <div class="fh-impact-label">{pct_label} &middot; {f["items"]} item(s) &middot; cells: {cell_label} &middot; {html_lib.escape(f["confidence"])}</div></div>
            <span class="sev-badge" style="color:{sev_color};background:{sev_color}1A;border:1px solid {sev_color}55;">{f["severity"]}</span>
          </div>
        </div>""")
    findings_html = "".join(rows_html) if rows_html else '<div class="empty-state">No rule violations detected at the current thresholds.</div>'

    html_doc = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="{GOOGLE_FONT_URL}" rel="stylesheet">
<style>
:root{{--bg:#FFFFFF;--surface:{SURFACE};--surface-alt:{SURFACE_ALT};--border:{BORDER};--border-strong:{BORDER_STRONG};
--text:{BODY_TEXT};--text-strong:{TEXT_STRONG};--text-faint:{TEXT_FAINT};--accent:{ACCENT};--accent-deep:{ACCENT_DEEP};
--on-accent:{ON_ACCENT};--radius:{RADIUS};--shadow:{SHADOW};}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:'Source Sans Pro',-apple-system,sans-serif;line-height:1.5;}}
.wrap{{max-width:1120px;margin:0 auto;padding:0 28px;}}
.topbar{{background:{HEADER_BG};padding:20px 0;}}
.topbar .wrap{{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;}}
.brand{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}}
.brand .mark{{font-size:11px;letter-spacing:.1em;font-weight:700;color:{HEADER_BG};background:#FFF;padding:4px 9px;border-radius:var(--radius);}}
.brand .name{{font-weight:600;font-size:14px;color:#FFF;}}
.brand .sub{{color:rgba(255,255,255,.75);font-size:12px;}}
.badge-preview{{font-size:10px;font-weight:600;letter-spacing:.08em;color:#FFF;border:1px solid rgba(255,255,255,.6);border-radius:100px;padding:2px 8px;}}
.hero{{padding:40px 0 28px;}}
.eyebrow{{font-size:12px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--accent-deep);margin:0 0 14px;}}
h1{{font-weight:700;font-size:clamp(22px,3.2vw,34px);line-height:1.2;margin:0 0 18px;color:var(--text-strong);max-width:38ch;}}
.verdict-panel{{border:1px solid var(--border-strong);border-radius:var(--radius);background:#FFF;box-shadow:var(--shadow);padding:26px 30px;}}
.status-chip{{display:inline-flex;align-items:center;gap:8px;font-size:11px;letter-spacing:.1em;font-weight:700;padding:6px 12px;border-radius:100px;margin-bottom:14px;color:{status_color};background:{status_bg};border:1px solid {status_border};}}
.verdict-panel p{{font-size:15px;max-width:80ch;margin:0;}}
.kpi-strip{{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--border);border:1px solid var(--border-strong);border-radius:var(--radius);overflow:hidden;margin-top:20px;}}
@media (max-width:900px){{.kpi-strip{{grid-template-columns:repeat(3,1fr);}}}}
.kpi{{background:#FFF;padding:16px 14px;position:relative;}}
.kpi .val{{font-weight:700;font-size:19px;color:var(--text-strong);}}
.kpi.flag .val{{color:#D64545;}}
.kpi .lbl{{margin-top:4px;font-size:11px;color:var(--text-faint);}}
.kpi .tip{{display:none;position:absolute;left:12px;right:12px;top:100%;margin-top:6px;background:var(--text-strong);border-radius:8px;padding:8px 10px;font-size:11px;color:#FFF;z-index:5;}}
.kpi:hover .tip{{display:block;}}
.banner{{border:1px solid var(--border-strong);background:var(--surface);border-radius:var(--radius);padding:12px 16px;font-size:12.5px;margin:20px 0 0;}}
section{{padding:34px 0;border-top:1px solid var(--border);}}
.block-title{{font-weight:700;font-size:20px;margin:0 0 16px;color:var(--text-strong);}}
.findings{{border:1px solid var(--border-strong);border-radius:var(--radius);overflow:hidden;}}
.frow{{border-bottom:1px solid var(--border);}}
.frow:last-child{{border-bottom:none;}}
.frow-head{{display:grid;grid-template-columns:1.4fr 1fr 90px;align-items:center;gap:16px;padding:14px 18px;}}
.fh-name{{font-weight:600;font-size:14px;color:var(--text-strong);}}
.fh-rule{{font-size:12px;color:var(--text-faint);}}
.fh-impact-track{{height:5px;background:var(--surface-alt);border-radius:100px;overflow:hidden;}}
.fh-impact-fill{{height:100%;border-radius:100px;}}
.fh-impact-label{{font-size:11px;color:var(--text-faint);margin-top:5px;}}
.sev-badge{{font-size:10.5px;letter-spacing:.06em;font-weight:700;padding:4px 9px;border-radius:5px;text-transform:uppercase;text-align:center;}}
.empty-state{{padding:36px;text-align:center;color:var(--text);font-size:14px;background:var(--surface);}}
footer{{border-top:1px solid var(--border);padding:24px 0 36px;font-size:11.5px;color:var(--text-faint);}}
</style></head>
<body>
<div class="topbar"><div class="wrap"><div class="brand">
  {TRIDANT_LOGO_HTML}<span class="mark">{html_lib.escape(initials)}</span>
  <span class="name">{html_lib.escape(client_name.upper())}</span>
  <span class="sub">&middot; Anaplan Model Health &amp; Optimization Platform</span>{preview_badge}
</div></div></div>
<div class="hero"><div class="wrap">
  <p class="eyebrow">{html_lib.escape(model_line)}</p>
  <h1>{html_lib.escape(headline)}</h1>
  <div class="verdict-panel">
    <span class="status-chip">{health.band.upper()} &middot; {health.overall:.0f}/100</span>
    <p>{verdict}</p>
    <div class="kpi-strip">{kpi_html}</div>
  </div>
  {banner_html}
</div></div>
<section><div class="wrap">
  <h2 class="block-title">Findings, ranked by space impact</h2>
  <div class="findings">{findings_html}</div>
</div></section>
<footer><div class="wrap">Figures are computed live from the uploaded export against the active rule set
({len(result.active_rule_ids)} rules run on this file). Cell-impact percentages are not mutually exclusive.</div></footer>
</body></html>"""

    n_findings = len(findings)
    approx_height = 900 + n_findings * 70 + 200
    approx_height = max(1200, min(approx_height, 3200))
    components.html(html_doc, height=approx_height, scrolling=True)
