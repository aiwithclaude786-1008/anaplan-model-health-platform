# app/reports/pdf_report.py -- master spec section 20 (PDF executive report).
# ============================================================
# A consulting-style PDF summary using reportlab (pure Python,
# no system dependency). Deliberately shorter than the Excel/HTML
# reports -- an executive leave-behind, not the full data dump.
# ============================================================
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

from app.branding import ACCENT, TEXT_STRONG
from app.analysis.pipeline import AnalysisResult
from app.analysis.size_analysis import cells_to_gb


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("TridantTitle", parent=ss["Title"], textColor=colors.HexColor(TEXT_STRONG), spaceAfter=4))
    ss.add(ParagraphStyle("TridantHeading", parent=ss["Heading2"], textColor=colors.HexColor(TEXT_STRONG),
                           spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle("TridantBody", parent=ss["BodyText"], leading=14))
    return ss


def _table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ACCENT)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8F9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build_pdf_report(result: AnalysisResult, client_name: str = "", model_label: str = "") -> bytes:
    ss = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=22 * mm, bottomMargin=18 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    story = []

    size = result.size
    health = result.health
    client_name = client_name.strip() or "Your Organization"

    story.append(Paragraph(client_name, ss["TridantTitle"]))
    story.append(Paragraph(model_label or "Anaplan Model Health & Optimization Report", ss["TridantBody"]))
    story.append(Spacer(1, 10))

    verdict = (
        f"Overall model health scores <b>{health.overall:.0f}/100 ({health.band})</b>. "
        + (f"The model holds <b>{size.total_cells:,.0f} cells</b> "
           f"(~{cells_to_gb(size.total_cells):,.1f} GB-equivalent) across <b>{size.modules_count} modules</b>, "
           f"with the top {size.top_n_actual} modules holding <b>{size.top_n_pct:.0f}%</b> of that footprint."
           if size.cell_count_available else "No Cell Count column was found, so size metrics aren't available.")
    )
    story.append(Paragraph(verdict, ss["TridantBody"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Health Score Breakdown", ss["TridantHeading"]))
    health_data = [["Dimension", "Score"]] + [[d.label, f"{d.score:.0f}"] for d in health.dimensions]
    story.append(_table(health_data, col_widths=[120 * mm, 30 * mm]))

    if size.cell_count_available:
        story.append(Paragraph("Top Modules by Size", ss["TridantHeading"]))
        size_data = [["Rank", "Module", "Cells", "% of Model", "Status"]] + [
            [r.rank, r.module, f"{r.cell_count:,.0f}", f"{r.pct_of_model*100:.1f}%", r.status]
            for r in size.module_rows[:10]
        ]
        story.append(_table(size_data, col_widths=[14 * mm, 70 * mm, 30 * mm, 25 * mm, 20 * mm]))

    story.append(Paragraph("Top Optimization Opportunities", ss["TridantHeading"]))
    if result.top_opportunities:
        opp_data = [["#", "Module", "Issue", "Recommended Action", "Confidence"]] + [
            [o.priority, o.module, o.issue, o.recommended_action, o.confidence]
            for o in result.top_opportunities[:10]
        ]
        story.append(_table(opp_data, col_widths=[8 * mm, 35 * mm, 45 * mm, 55 * mm, 22 * mm]))
    else:
        story.append(Paragraph("No optimization opportunities identified at the current thresholds.", ss["TridantBody"]))

    story.append(PageBreak())
    story.append(Paragraph("Consultant Action Plan", ss["TridantHeading"]))
    for horizon, label in [("0-30", "0-30 Days -- Quick wins"), ("31-60", "31-60 Days -- Structural improvements"),
                            ("61-90", "61-90 Days -- Architecture improvements")]:
        items = [i for i in result.action_plan if i.horizon == horizon]
        story.append(Paragraph(f"<b>{label}</b>", ss["TridantBody"]))
        if items:
            for item in items:
                story.append(Paragraph(f"&bull; <b>{item.title}</b> -- {item.detail}", ss["TridantBody"]))
        else:
            story.append(Paragraph("Nothing queued for this horizon.", ss["TridantBody"]))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Generated by the Anaplan Model Health & Optimization Platform against "
        f"{len(result.active_rule_ids)} active rules. Confidence labels distinguish Measured, Estimated, "
        f"Potential, and Requires-validation findings.",
        ss["TridantBody"],
    ))

    doc.build(story)
    return buffer.getvalue()
