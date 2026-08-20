from app.analysis.simulator import simulate
from app.models.schemas import OptimizationOpportunity


def _opp(issue, cell_impact, module="M1"):
    return OptimizationOpportunity(
        priority=1, module=module, line_item="n item(s)", issue=issue,
        current_impact=f"{cell_impact:,.0f} cells", recommended_action="Fix it",
        expected_benefit="...", confidence="Measured", effort="Medium",
        validation_required=True, cell_impact=cell_impact,
    )


def test_reduction_low_bound_never_exceeds_high_bound():
    opp = _opp("Full-grain calc cluster (RULE-SIZE-001)", 1_000_000)
    sim = simulate([opp], starting_cells=4_000_000)
    assert sim.total_reduction_pct_low <= sim.total_reduction_pct_high
    assert sim.ending_cells_low <= sim.ending_cells_high


def test_no_selection_yields_zero_reduction():
    sim = simulate([], starting_cells=1_000_000)
    assert sim.total_reduction_pct_low == 0.0
    assert sim.total_reduction_pct_high == 0.0
    assert sim.ending_cells_low == sim.ending_cells_high == 1_000_000


def test_cannot_remove_more_cells_than_exist():
    opp = _opp("Full Model Calendar (RULE-DIM-002)", 10_000_000)  # bigger than the model itself
    sim = simulate([opp], starting_cells=1_000_000)
    assert sim.ending_cells_high >= 0
    assert sim.ending_cells_low >= 0


def test_unknown_rule_id_falls_back_to_default_range():
    opp = _opp("Some future rule (RULE-NEW-999)", 100_000)
    sim = simulate([opp], starting_cells=1_000_000)
    assert sim.steps[0].reduction_low_pct == 5.0
    assert sim.steps[0].reduction_high_pct == 15.0


def test_multiple_steps_reduce_cumulatively():
    opps = [
        _opp("Full-grain calc cluster (RULE-SIZE-001)", 1_000_000, module="M1"),
        _opp("Full Model Calendar (RULE-DIM-002)", 500_000, module="M2"),
    ]
    sim = simulate(opps, starting_cells=4_000_000)
    assert len(sim.steps) == 2
    assert sim.steps[1].cells_before == sim.steps[0].cells_after
