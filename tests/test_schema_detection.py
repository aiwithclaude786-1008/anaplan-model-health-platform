from app.data.schema_detection import find_col, detect_schema
from app.data.normalization import normalize


def test_find_col_exact_match():
    cols = ["Module Name", "Cell Count", "Formula"]
    assert find_col(cols, ["formula"]) == "Formula"


def test_find_col_substring_fallback():
    cols = ["Line Item Formula Text"]
    assert find_col(cols, ["formula"]) == "Line Item Formula Text"


def test_find_col_missing_returns_none():
    assert find_col(["A", "B"], ["formula"]) is None


def test_detect_schema_finds_real_export_columns(raw_export_df):
    schema = detect_schema(list(raw_export_df.columns))
    assert schema["formula"] == "Formula"
    assert schema["cell_count"] == "Cell Count"
    assert schema["applies_to"] == "Applies To"
    assert schema["time_range"] == "Time Range"
    assert schema["notes"] == "Notes"


def test_normalize_picks_first_and_last_column_as_line_item_and_module(raw_export_df):
    nd = normalize(raw_export_df)
    assert nd.line_col == "Line Item Name"
    assert nd.module_col == "Module Name"
    assert nd.cell_count_available is True
    assert "applies_to" in nd.optional_cols
    assert "time_range" in nd.optional_cols
    assert "notes" in nd.optional_cols
