import json

import pandas as pd
import pytest

from app.analysis.pipeline import run_pipeline
from app.rules.thresholds import RuleThresholds
from app.reports.excel_report import build_excel_report
from app.reports.csv_report import build_optimization_backlog_csv, build_findings_csv
from app.reports.json_report import build_json_report
from app.reports.html_report import build_html_report
from app.reports.pdf_report import build_pdf_report


@pytest.fixture
def result(raw_export_df):
    return run_pipeline(raw_export_df, RuleThresholds())


def test_excel_report_has_all_ten_sheets(result):
    xlsx_bytes = build_excel_report(result, "Acme", "Model")
    import io
    xls = pd.ExcelFile(io.BytesIO(xlsx_bytes))
    assert len(xls.sheet_names) == 10


def test_json_report_round_trips(result):
    payload = json.loads(build_json_report(result, "Acme", "Model"))
    assert payload["client"] == "Acme"
    assert "health" in payload and "findings" in payload
    assert isinstance(payload["findings"], list)


def test_html_report_is_self_contained_html(result):
    html = build_html_report(result, "Acme", "Model")
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "Acme" in html


def test_pdf_report_produces_valid_pdf_bytes(result):
    pdf_bytes = build_pdf_report(result, "Acme", "Model")
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500


def test_csv_reports_are_nonempty(result):
    assert len(build_optimization_backlog_csv(result)) > 0
    assert len(build_findings_csv(result)) > 0
