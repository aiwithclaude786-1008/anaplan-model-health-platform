# app/rules/thresholds.py
# ============================================================
# Tunable numbers for the rule engine. Defaults for nested_if_*
# and daisy_chain_threshold match the original app.py sidebar
# defaults (kept for backward compatibility with existing
# behavior); the newer thresholds (formula length, LOOKUP count
# for complexity banding) match the real PLANUAL-based Tridant
# report this platform generalizes ("5+ nested IFs", "3+
# LOOKUPs", "formulas over 400 chars").
# ============================================================
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuleThresholds:
    nested_if_high: int = 6
    nested_if_med: int = 4
    daisy_chain_threshold: int = 4
    lookup_multi_threshold: int = 1        # count_lookup > this => "Multiple LOOKUP"
    formula_length_high: int = 400
    complexity_split_if: int = 5           # IF count that alone marks a formula SPLIT-severity
    complexity_split_lookup: int = 3       # LOOKUP count that alone marks a formula SPLIT-severity
