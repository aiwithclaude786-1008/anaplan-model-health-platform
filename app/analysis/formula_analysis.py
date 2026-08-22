# app/analysis/formula_analysis.py
# ============================================================
# Feature extraction for every line item: formula-text features
# (migrated from the original app.py build_features/detect_row/
# post_nested_flags) plus optional-column features derived from
# whatever a real Anaplan "Module List Export" happens to carry
# (Format/Summary JSON blobs, Applies To, Time Range, Notes).
#
# The output of build_feature_table() is one merged DataFrame --
# one row per line item -- that every Rule.detect() reads from,
# and that size/dimensionality/optimization analysis reuses so
# the whole platform computes numbers exactly once (master spec
# section 22).
# ============================================================
from __future__ import annotations

import re
from typing import List

import numpy as np
import pandas as pd

from app.data.normalization import NormalizedData
from app.data.field_parsers import (
    extract_format_type, extract_summary_method, classify_module_type,
    is_full_time_calendar,
)
from app.models.schemas import Finding

# ---- regexes (migrated as-is from the original app.py) ----
RE_IF       = re.compile(r"\bIF\b", re.I)
RE_LOOKUP   = re.compile(r"\bLOOKUP\b", re.I)
RE_SUM      = re.compile(r"\bSUM\b", re.I)
RE_POST     = re.compile(r"\bPOST\b", re.I)
RE_TIMESUM  = re.compile(r"\bTIMESUM\b", re.I)
RE_FINDITEM = re.compile(r"\bFINDITEM\b", re.I)
RE_RANK     = re.compile(r"\bRANK\b", re.I)
RE_SELECT   = re.compile(r"\bSELECT\b", re.I)
RE_CUM      = re.compile(r"\bCUMULATE\b", re.I)
RE_OFFSET   = re.compile(r"\bOFFSET\b|\bLAG\b|\bLEAD\b|\bMOVINGSUM\b", re.I)

RE_START_OR_END = re.compile(r"\bSTART\s*\(|\bEND\s*\(|\bSTART\s*:|\bEND\s*:", re.I)

RE_MAP_SUM_LOOKUP = re.compile(r"\[[^\]]*\bSUM\s*:[^\]]*,[^\]]*\bLOOKUP\s*:", re.I)
RE_MAP_LOOKUP_SUM = re.compile(r"\[[^\]]*\bLOOKUP\s*:[^\]]*,[^\]]*\bSUM\s*:", re.I)
RE_MAP_SELECT_LOOKUP = re.compile(r"\[[^\]]*\bSELECT\s*:[^\]]*,[^\]]*\bLOOKUP\s*:", re.I)
RE_MAP_LOOKUP_SELECT = re.compile(r"\[[^\]]*\bLOOKUP\s*:[^\]]*,[^\]]*\bSELECT\s*:", re.I)
RE_MAP_SUM_SELECT = re.compile(r"\[[^\]]*\bSUM\s*:[^\]]*,[^\]]*\bSELECT\s*:", re.I)
RE_MAP_SELECT_SUM = re.compile(r"\[[^\]]*\bSELECT\s*:[^\]]*,[^\]]*\bSUM\s*:", re.I)

RE_POST_INSIDE_IF = re.compile(r"\b(?:THEN|ELSE)\b(?:(?!\bIF\b).)*?\bPOST\s*\(", re.I)
RE_POST_CALL = re.compile(r"POST\s*\(", re.I)
RE_SELECT_TARGET = re.compile(r"SELECT\s*:\s*([^\],;\[\]]+)", re.I)


def post_nested_flags(formula_upper: str):
    has_lookup_nested = False
    has_sum_nested = False
    for m in RE_POST_CALL.finditer(formula_upper):
        start = m.end() - 1
        depth = 0
        j = start
        n = len(formula_upper)
        while j < n:
            ch = formula_upper[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        inner = formula_upper[start + 1:j]
        if re.search(r"\[[^\]]*\bLOOKUP\s*:", inner):
            has_lookup_nested = True
        if re.search(r"\[[^\]]*\bSUM\s*:", inner):
            has_sum_nested = True
        if has_lookup_nested and has_sum_nested:
            break
    return has_lookup_nested, has_sum_nested


def select_targets(formula: str):
    return [m.group(1).strip() for m in RE_SELECT_TARGET.finditer(formula)]


def build_entity_pattern(names):
    cleaned = sorted({n for n in names if len(n) >= 2}, key=len, reverse=True)
    if not cleaned:
        return None
    escaped = [re.escape(n) for n in cleaned]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.I)


def build_formula_features(formula_series: pd.Series) -> pd.DataFrame:
    s = formula_series.astype(str).fillna("")
    su = s.str.upper()

    feats = pd.DataFrame(index=formula_series.index)
    feats["formula"] = s
    feats["upper"] = su
    feats["formula_length"] = s.str.len()

    feats["count_if"] = su.str.count(RE_IF)
    feats["count_lookup"] = su.str.count(RE_LOOKUP)
    feats["count_sum"] = su.str.count(RE_SUM)
    feats["count_select"] = su.str.count(RE_SELECT)

    feats["has_post"] = su.str.contains(RE_POST)
    feats["has_timesum"] = su.str.contains(RE_TIMESUM)

    feats["count_finditem"] = su.str.count(RE_FINDITEM)
    feats["count_rank"] = su.str.count(RE_RANK)
    feats["count_cumulate"] = su.str.count(RE_CUM)
    feats["count_offsetlike"] = su.str.count(RE_OFFSET)

    feats["has_start_or_end"] = su.str.contains(RE_START_OR_END)

    feats["map_has_lookup_sum"] = su.str.contains(RE_MAP_SUM_LOOKUP) | su.str.contains(RE_MAP_LOOKUP_SUM)
    feats["map_has_lookup_select"] = su.str.contains(RE_MAP_SELECT_LOOKUP) | su.str.contains(RE_MAP_LOOKUP_SELECT)
    feats["map_has_select_sum"] = su.str.contains(RE_MAP_SUM_SELECT) | su.str.contains(RE_MAP_SELECT_SUM)

    nested = su.apply(post_nested_flags)
    feats["has_post_lookup_nested"] = nested.apply(lambda t: t[0])
    feats["has_post_sum_nested"] = nested.apply(lambda t: t[1])

    # Negative-lookahead regex -- must run through Python's `re` module
    # directly (pandas' PyArrow string backend uses RE2, no lookahead
    # support), so this stays a plain .apply() rather than str.contains().
    feats["has_post_inside_if"] = su.apply(lambda x: bool(RE_POST_INSIDE_IF.search(x)))

    feats["select_targets"] = s.apply(select_targets)
    feats["has_select_hardcoded"] = feats["select_targets"].apply(
        lambda targets: any(not re.search(r"\bTIME\s*\.\s*ALL\s*PERIODS\b", t, re.I) for t in targets)
    )
    feats["has_select_time_scoped"] = feats["select_targets"].apply(
        lambda targets: any(re.search(r"\bTIME\s*\.\s*ALL\s*PERIODS\b", t, re.I) for t in targets)
    )

    feats["func_density_count"] = (
        feats["count_sum"]
        + feats["count_lookup"]
        + feats["count_if"]
        + feats["count_finditem"]
        + feats["count_rank"]
        + feats["count_select"]
        + feats["count_cumulate"]
        + feats["count_offsetlike"]
        + feats["has_timesum"].astype(int)
        + feats["has_post"].astype(int)
    )
    return feats


def build_optional_features(nd: NormalizedData, formula_feats: pd.DataFrame) -> pd.DataFrame:
    """Derives extra per-row features from whichever optional columns
    the export actually has (Format/Summary/Applies To/Time Range/
    Notes/Cell Count). Every column here is None/NaN-safe -- callers
    must check nd.optional_cols / nd.cell_count_available before
    trusting a given feature is meaningful."""
    df = nd.df
    idx = df.index
    out = pd.DataFrame(index=idx)

    out["module"] = df["_ModuleResolved_"]
    out["module_type"] = out["module"].apply(classify_module_type)

    if nd.cell_count_available:
        out["cell_count"] = pd.to_numeric(df[nd.cell_count_col], errors="coerce")
    else:
        out["cell_count"] = np.nan

    fmt_col = nd.optional_cols.get("format")
    out["format_type"] = df[fmt_col].apply(extract_format_type) if fmt_col else "Unknown"

    summary_col = nd.optional_cols.get("summary")
    out["summary_method"] = df[summary_col].apply(extract_summary_method) if summary_col else "Unknown"

    applies_col = nd.optional_cols.get("applies_to")
    out["applies_to"] = df[applies_col].astype(str).str.strip() if applies_col else np.nan
    if applies_col:
        modal_applies = out.groupby(out["module"])["applies_to"].transform(
            lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0]
        )
        out["is_subsidiary_view"] = (out["applies_to"] != modal_applies) & out["applies_to"].notna() & (out["applies_to"] != "")
    else:
        out["is_subsidiary_view"] = False

    time_range_col = nd.optional_cols.get("time_range")
    out["time_range"] = df[time_range_col].astype(str) if time_range_col else np.nan
    out["is_full_calendar"] = out["time_range"].apply(is_full_time_calendar) if time_range_col else False

    notes_col = nd.optional_cols.get("notes")
    if notes_col:
        notes_raw = df[notes_col].astype(str).str.strip()
        out["notes_blank"] = notes_raw.isin(["", "-", "nan", "None", "NaN"])
    else:
        out["notes_blank"] = False

    has_formula = formula_feats["formula"].str.strip() != ""
    out["is_text_in_calc"] = (out["format_type"] == "TEXT") & (out["module_type"] == "Calc") & has_formula

    # Full-grain cluster: 4+ line items in the same module sharing an
    # identical, non-zero Cell Count -- a strong, data-only signal that
    # the whole module was built at one uniform (usually maximal) grain.
    if nd.cell_count_available:
        cluster_key = out["module"].astype(str) + "||" + out["cell_count"].round(0).astype("Int64").astype(str)
        cluster_size = cluster_key.map(cluster_key.value_counts())
        out["in_full_grain_cluster"] = (out["cell_count"] > 0) & (cluster_size >= 4)
    else:
        out["in_full_grain_cluster"] = False

    # "Big" line item for summary-method flagging: top decile of cell
    # count model-wide (data-driven threshold, not a fixed constant).
    if nd.cell_count_available and out["cell_count"].notna().any():
        p90 = out["cell_count"].quantile(0.90)
        out["is_big_item"] = out["cell_count"] >= p90
    else:
        out["is_big_item"] = False
    out["has_summary_on_big_item"] = (
        out["is_big_item"] & (out["module_type"] == "Calc") &
        out["summary_method"].notna() & (out["summary_method"] != "NONE") & (out["summary_method"] != "Unknown")
    )

    is_complex = (
        (formula_feats["count_if"] >= 1) | (formula_feats["formula_length"] >= 200) |
        (formula_feats["func_density_count"] >= 4)
    )
    out["is_documentation_gap"] = is_complex & out["notes_blank"]

    return out


def build_feature_table(nd: NormalizedData) -> pd.DataFrame:
    """The single merged, one-row-per-line-item table every rule and
    every downstream analysis module reads from."""
    formula_feats = build_formula_features(nd.df[nd.formula_col])
    optional_feats = build_optional_features(nd, formula_feats)
    feats = pd.concat([formula_feats, optional_feats], axis=1)
    feats["line_item"] = nd.df[nd.line_col].astype(str)
    return feats


def evaluate_rules(rules, feats: pd.DataFrame):
    """Runs every Rule.detect() against the whole feature table at once
    (each detect() is vectorized -- see rules/base.py) and returns a
    list of Finding, one per (rule, row) hit. Looping over rules
    (typically ~17) with a vectorized pandas mask per rule, instead of
    every row x every rule in a Python-level loop, is what keeps a
    large export's rule pass fast."""
    findings: List[Finding] = []
    for rule in rules:
        try:
            mask = rule.detect(feats)
        except Exception:
            continue
        if mask is None or not mask.any():
            continue
        matched = feats[mask]
        for row in matched.itertuples():
            row_dict = row._asdict()
            cell_impact = row_dict.get("cell_count")
            cell_impact = None if (cell_impact is None or (isinstance(cell_impact, float) and np.isnan(cell_impact))) else float(cell_impact)
            findings.append(Finding(
                rule_id=rule.rule_id,
                category=rule.category,
                module=str(row_dict.get("module", "Unknown")),
                line_item=str(row_dict.get("line_item", "Unknown")),
                formula=str(row_dict.get("formula", "")),
                severity=rule.severity,
                name=rule.name,
                cell_impact=cell_impact,
                size_impact=cell_impact if rule.affects_size else None,
                performance_impact=cell_impact if rule.affects_performance else None,
                recommendation=rule.recommendation,
                confidence=rule.confidence,
                affects_size=rule.affects_size,
                affects_performance=rule.affects_performance,
                row_index=row_dict.get("Index"),
            ))
    return findings


# Weights for the normalized 0-100 Formula Impact Score (master spec
# section 3): Complexity x Cell Exposure x Dependency Impact x
# Performance Risk, each normalized to 0-1 first so no single factor
# dominates just because of its raw scale.
def compute_formula_impact_score(feats: pd.DataFrame) -> pd.Series:
    complexity = (
        feats["func_density_count"].clip(upper=20) / 20.0 * 0.5
        + (feats["formula_length"].clip(upper=800) / 800.0) * 0.5
    )
    if feats["cell_count"].notna().any() and feats["cell_count"].max() > 0:
        cell_exposure = np.log1p(feats["cell_count"].fillna(0)) / np.log1p(feats["cell_count"].max())
    else:
        cell_exposure = pd.Series(0.0, index=feats.index)
    performance_risk = (
        feats["count_lookup"].clip(upper=5) / 5.0 * 0.3
        + feats["count_select"].clip(upper=5) / 5.0 * 0.2
        + feats["has_post"].astype(int) * 0.2
        + feats["has_timesum"].astype(int) * 0.15
        + feats["count_if"].clip(upper=10) / 10.0 * 0.15
    ).clip(upper=1.0)

    score = (0.35 * complexity + 0.35 * cell_exposure + 0.30 * performance_risk) * 100.0
    return score.clip(lower=0.0, upper=100.0).round(1)
