import pandas as pd

from app.data.normalization import normalize
from app.data.validation import run_data_quality_checks


def test_clean_export_scores_high(raw_export_df):
    nd = normalize(raw_export_df)
    report = run_data_quality_checks(nd)
    assert report.score > 70
    assert report.total_rows == len(raw_export_df)


def test_negative_cell_count_flagged(raw_export_df):
    df = raw_export_df.copy()
    df.loc[0, "Cell Count"] = -5
    nd = normalize(df)
    report = run_data_quality_checks(nd)
    checks = {i.check for i in report.issues}
    assert "Negative Cell Count values" in checks


def test_duplicate_rows_flagged(raw_export_df):
    df = pd.concat([raw_export_df, raw_export_df.iloc[[0]]], ignore_index=True)
    nd = normalize(df)
    report = run_data_quality_checks(nd)
    checks = {i.check for i in report.issues}
    assert "Duplicate Module + Line Item rows" in checks


def test_missing_cell_count_column_flagged(raw_export_df):
    df = raw_export_df.drop(columns=["Cell Count"])
    nd = normalize(df)
    assert nd.cell_count_available is False
    report = run_data_quality_checks(nd)
    checks = {i.check for i in report.issues}
    assert "No Cell Count column found" in checks
