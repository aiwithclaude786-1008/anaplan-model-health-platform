from app.data.normalization import normalize
from app.analysis.size_analysis import analyze_size


def test_analyze_size_basic(raw_export_df):
    nd = normalize(raw_export_df)
    size = analyze_size(nd, agg_method="max", top_n=3)

    assert size.cell_count_available is True
    assert size.modules_count == 5  # CALC01, SYS01, CALC02, DAT01, DAT02
    assert size.line_items_count == len(raw_export_df)
    assert size.largest_module == "CALC01 Var P&L"
    assert size.largest_module_cells == 1_000_000
    assert size.total_cells > 0
    assert size.top_n_actual == 3

    pct_sum = sum(r.pct_of_model for r in size.module_rows)
    assert abs(pct_sum - 1.0) < 1e-6


def test_status_bands_are_monotonic_by_cumulative_pct(raw_export_df):
    nd = normalize(raw_export_df)
    size = analyze_size(nd)
    cumulative = [r.cumulative_pct for r in size.module_rows]
    assert cumulative == sorted(cumulative)
    assert size.module_rows[0].status in ("CRITICAL", "HIGH", "WATCH", "OK")
