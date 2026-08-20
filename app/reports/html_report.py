# app/reports/html_report.py -- master spec section 20 (interactive HTML report).
# ============================================================
# A single, self-contained, downloadable HTML file covering
# every major section of the platform -- Executive Summary,
# Module Sizing, Findings, Optimization Backlog, Action Plan,
# Rules Reference -- built with the same Tridant tokens as the
# in-app Executive Dashboard (app/branding.py), using plain
# <details>/<summary> for drill-down so it needs no JavaScript
# and still works as a plain static file.
# ============================================================
from __future__ import annotations

import html as html_lib

from app.branding import (
    TRIDANT_LOGO_B64, ACCENT, ACCENT_DEEP, ON_ACCENT, BODY_TEXT, HEADER_BG, TEXT_STRONG, TEXT_FAINT,
    SURFACE, SURFACE_ALT, BORDER, BORDER_STRONG, RADIUS, SHADOW, GOOGLE_FONT_URL, STATUS_COLORS,
    SEVERITY_COLORS,
)
from app.analysis.pipeline import AnalysisResult
from app.analysis.size_analysis import cells_to_gb

_LOGO_HTML = f'<img alt="Tridant" src="data:image/png;base64,{TRIDANT_LOGO_B64}" style="height:26px;width:auto;display:block;">'


def _css() -> str:
    return f"""
<style>
:root{{--bg:#FFFFFF;--surface:{SURFACE};--surface-alt:{SURFACE_ALT};--border:{BORDER};--border-strong:{BORDER_STRONG};
--text:{BODY_TEXT};--text-strong:{TEXT_STRONG};--text-faint:{TEXT_FAINT};--accent:{ACCENT};--accent-deep:{ACCENT_DEEP};
--on-accent:{ON_ACCENT};--radius:{RADIUS};--shadow:{SHADOW};}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:'Source Sans Pro',-apple-system,sans-serif;line-height:1.55;}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 26px;}}
.topbar{{background:{HEADER_BG};padding:18px 0;}}
.topbar .wrap{{display:flex;align-items:center;gap:12px;}}
.topbar .name{{font-weight:600;font-size:14px;color:#FFF;}}
.topbar .sub{{color:rgba(255,255,255,.75);font-size:12px;}}
h1{{font-size:26px;color:var(--text-strong);margin:28px 0 6px;}}
h2{{font-size:19px;color:var(--text-strong);border-top:1px solid var(--border);padding-top:26px;margin-top:30px;}}
.kpi-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--border);border:1px solid var(--border-strong);border-radius:var(--radius);overflow:hidden;margin:16px 0;}}
.kpi{{background:#FFF;padding:14px;}}
.kpi .val{{font-weight:700;font-size:18px;color:var(--text-strong);}}
.kpi .lbl{{font-size:11px;color:var(--text-faint);margin-top:3px;}}
table{{width:100%;border-collapse:collapse;font-size:12.5px;margin:10px 0;}}
th{{background:var(--accent);color:#FFF;text-align:left;padding:8px 10px;font-size:11.5px;}}
td{{padding:7px 10px;border-bottom:1px solid var(--border);}}
tr:nth-child(even) td{{background:var(--surface);}}
.badge{{display:inline-block;padding:2px 8px;border-radius:5px;font-size:10.5px;font-weight:700;text-transform:uppercase;}}
details{{border:1px solid var(--border-strong);border-radius:var(--radius);margin:8px 0;padding:10px 14px;}}
summary{{cursor:pointer;font-weight:600;color:var(--text-strong);}}
.status-chip{{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.08em;padding:5px 12px;border-radius:100px;}}
footer{{border-top:1px solid var(--border);margin-top:36px;padding:20px 0 40px;font-size:11.5px;color:var(--text-faint);}}
</style>"""


def _badge(text: str, color: str) -> str:
    return f'<span class="badge" style="color:{color};background:{color}1A;border:1px solid {color}55;">{html_lib.escape(text)}</span>'


def _kpi(val, lbl) -> str:
    return f'<div class="kpi"><div class="val">{html_lib.escape(str(val))}</div><div class="lbl">{html_lib.escape(lbl)}</div></div>'


def build_html_report(result: AnalysisResult, client_name: str = "", model_label: str = "") -> str:
    size = result.size
    health = result.health
    status_color, status_bg, _ = STATUS_COLORS.get(health.band, STATUS_COLORS["Fair"])
    client_name = client_name.strip() or "Your Organization"

    kpis = "".join([
        _kpi(f"{size.total_cells:,.0f}" if size.cell_count_available else "N/A", "Total cells"),
        _kpi(f"{cells_to_gb(size.total_cells):,.2f} GB" if size.cell_count_available else "N/A", "Estimated size"),
        _kpi(f"{health.overall:.0f}/100 ({health.band})", "Model health"),
        _kpi(f"{result.data_quality.score:.0f}/100", "Data quality"),
    ])

    health_rows = "".join(
        f"<tr><td>{html_lib.escape(d.label)}</td><td>{d.score:.0f}</td><td>{html_lib.escape(d.detail)}</td></tr>"
        for d in health.dimensions
    )

    size_rows = "".join(
        f"<tr><td>{r.rank}</td><td>{html_lib.escape(r.module)}</td><td>{r.cell_count:,.0f}</td>"
        f"<td>{r.pct_of_model*100:.1f}%</td><td>{r.cumulative_pct*100:.1f}%</td><td>{r.line_items}</td>"
        f"<td>{html_lib.escape(r.status)}</td><td>{html_lib.escape(r.primary_lever)}</td></tr>"
        for r in size.module_rows[:40]
    ) if size.cell_count_available else '<tr><td colspan="8">No Cell Count column in this export.</td></tr>'

    finding_names = {}
    for f in result.findings:
        finding_names.setdefault(f.name, {"severity": f.severity, "confidence": f.confidence, "count": 0,
                                           "recommendation": f.recommendation})
        finding_names[f.name]["count"] += 1
    findings_rows = "".join(
        f"<tr><td>{html_lib.escape(name)}</td>{_badge(d['severity'], SEVERITY_COLORS.get(d['severity'], SEVERITY_COLORS['medium']))}"
        f"<td>{d['count']}</td><td>{html_lib.escape(d['confidence'])}</td><td>{html_lib.escape(d['recommendation'])}</td></tr>"
        for name, d in sorted(finding_names.items(), key=lambda kv: -kv[1]["count"])
    ) if finding_names else '<tr><td colspan="5">No rule violations detected.</td></tr>'

    opp_rows = "".join(
        f"<tr><td>{o.priority}</td><td>{html_lib.escape(o.module)}</td><td>{html_lib.escape(o.issue)}</td>"
        f"<td>{html_lib.escape(o.recommended_action)}</td><td>{html_lib.escape(o.expected_benefit)}</td>"
        f"<td>{html_lib.escape(o.confidence)}</td><td>{html_lib.escape(o.effort)}</td></tr>"
        for o in result.top_opportunities
    ) if result.top_opportunities else '<tr><td colspan="7">No opportunities identified.</td></tr>'

    plan_sections = ""
    for horizon, label in [("0-30", "0-30 Days -- Quick wins"), ("31-60", "31-60 Days -- Structural improvements"),
                            ("61-90", "61-90 Days -- Architecture improvements")]:
        items = [i for i in result.action_plan if i.horizon == horizon]
        body = "".join(f"<li><b>{html_lib.escape(i.title)}</b> -- {html_lib.escape(i.detail)}</li>" for i in items) \
            or "<li>Nothing queued for this horizon.</li>"
        plan_sections += f"<details><summary>{html_lib.escape(label)}</summary><ul>{body}</ul></details>"

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Anaplan Model Health Report -- {html_lib.escape(client_name)}</title>
<link href="{GOOGLE_FONT_URL}" rel="stylesheet">
{_css()}
</head><body>
<div class="topbar"><div class="wrap">{_LOGO_HTML}
<div><div class="name">{html_lib.escape(client_name.upper())}</div>
<div class="sub">Anaplan Model Health &amp; Optimization Report</div></div></div></div>
<div class="wrap">
<h1>{html_lib.escape(model_label or 'Model Health Report')}</h1>
<span class="status-chip" style="color:{status_color};background:{status_bg};">{health.band.upper()} &middot; {health.overall:.0f}/100</span>
<div class="kpi-strip">{kpis}</div>

<h2>Health Score Breakdown</h2>
<table><tr><th>Dimension</th><th>Score</th><th>Detail</th></tr>{health_rows}</table>

<h2>Module Sizing</h2>
<table><tr><th>Rank</th><th>Module</th><th>Cell Count</th><th>% of Model</th><th>Cumulative %</th>
<th>Line Items</th><th>Status</th><th>Primary Lever</th></tr>{size_rows}</table>

<h2>Findings</h2>
<table><tr><th>Finding</th><th>Severity</th><th>Items</th><th>Confidence</th><th>Recommendation</th></tr>{findings_rows}</table>

<h2>Top Optimization Opportunities</h2>
<table><tr><th>#</th><th>Module</th><th>Issue</th><th>Recommended Action</th><th>Expected Benefit</th>
<th>Confidence</th><th>Effort</th></tr>{opp_rows}</table>

<h2>Consultant Action Plan</h2>
{plan_sections}

<footer>Generated by the Anaplan Model Health &amp; Optimization Platform. Figures are computed live from the
uploaded export against {len(result.active_rule_ids)} active rules. Confidence labels distinguish Measured,
Estimated, Potential, and Requires-validation findings -- see the Rules Reference for methodology.</footer>
</div>
</body></html>"""
