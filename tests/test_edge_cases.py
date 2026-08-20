import pandas as pd
import pytest

from app.analysis.pipeline import run_pipeline
from app.rules.thresholds import RuleThresholds
from app.data.normalization import normalize, SchemaError


def test_minimal_export_with_only_mandatory_columns():
    """A model-list export with just Line Item / Formula / Module -- no
    Cell Count, no optional columns at all -- must still run end to end
    without crashing, and must clearly report size as unavailable
    rather than fabricating a number."""
    df = pd.DataFrame({
        "Line Item": ["A", "B", "C"],
        "Formula": ["X[LOOKUP: Y] + Z[LOOKUP: W]", "1", "IF Flag THEN 1 ELSE 0"],
        "Module": ["Mod1", "Mod1", "Mod2"],
    })
    result = run_pipeline(df, RuleThresholds())
    assert result.size.cell_count_available is False
    assert result.health.overall >= 0
    assert result.dimensionality.waste_score is None


def test_missing_formula_column_raises_schema_error():
    df = pd.DataFrame({"Line Item": ["A"], "Module": ["Mod1"]})
    with pytest.raises(SchemaError):
        normalize(df)


def test_single_column_export_raises_schema_error():
    df = pd.DataFrame({"OnlyColumn": [1, 2, 3]})
    with pytest.raises(SchemaError):
        normalize(df)


def test_all_blank_formulas_produce_no_formula_findings():
    df = pd.DataFrame({
        "Line Item": ["A", "B"],
        "Formula": ["", ""],
        "Cell Count": [100, 200],
        "Module": ["Mod1", "Mod1"],
    })
    result = run_pipeline(df, RuleThresholds())
    formula_findings = [f for f in result.findings if f.category == "Formula"]
    assert formula_findings == []


def test_single_row_export_does_not_crash():
    df = pd.DataFrame({
        "Line Item": ["Only Item"],
        "Formula": ["POST(A, B[LOOKUP: C])"],
        "Cell Count": [500],
        "Module": ["Mod1"],
    })
    result = run_pipeline(df, RuleThresholds())
    assert result.size.modules_count == 1
    assert result.size.line_items_count == 1


def test_forward_fill_of_blank_module_rows():
    df = pd.DataFrame({
        "Line Item": ["Header", "A", "B"],
        "Formula": ["", "1", "2"],
        "Module": ["Mod1", None, None],
    })
    nd = normalize(df)
    assert list(nd.df["_ModuleResolved_"]) == ["Mod1", "Mod1", "Mod1"]
