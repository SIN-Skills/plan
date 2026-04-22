from __future__ import annotations

from pathlib import Path

from plan_cli.monte_carlo import (
    extract_task_estimates,
    generate_histogram_data,
    identify_high_risk_tasks,
    run_monte_carlo,
    simulate_plan,
)
from plan_cli.planning import load_json
from plan_cli.schema import ExitCode

# Monte Carlo tests verify duration simulation and risk outputs.
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_monte_carlo_results_are_generated() -> None:
    plan = load_json(FIXTURES / "valid_plan.json")
    tasks = extract_task_estimates(plan)

    assert len(tasks) == 3

    results = run_monte_carlo(tasks, iterations=500, seed=7)
    assert results["task_count"] == 3
    assert results["summary"]["mean"] > 0
    assert results["percentiles"]["p50"] > 0

    high_risk = identify_high_risk_tasks(tasks)
    assert len(high_risk) == 3

    raw_results = run_monte_carlo(tasks, iterations=200, seed=7, capture_samples=True)
    histogram = generate_histogram_data(raw_results, bins=5)
    assert len(histogram) == 5

    response = simulate_plan(FIXTURES / "valid_plan.json", iterations=500, seed=7)
    assert response.exit_code == ExitCode.OK
    assert response.status == "simulated"
    assert response.artifacts["task_count"] == 3
