from __future__ import annotations

from pathlib import Path

from plan_cli.dag import analyse_dependency_graph, build_graph, find_cycles, topological_order
from plan_cli.planning import load_json

# DAG tests verify ordering, cycles, and critical paths.
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_dependency_analysis_reports_critical_path() -> None:
    plan = load_json(FIXTURES / "valid_plan.json")
    graph, tasks, external_edges = build_graph(plan)

    assert len(tasks) == 3
    assert external_edges == []
    assert find_cycles(graph) == []
    assert topological_order(graph) == ["P1-T1", "P1-T2", "P2-T1"]

    report = analyse_dependency_graph(plan)
    assert report["task_count"] == 3
    assert report["critical_path"] == ["P1-T1", "P1-T2", "P2-T1"]
    assert report["execution_waves"][0] == ["P1-T1"]
    assert "graph TD" in report["mermaid"]


def test_cycle_fixture_has_cycles() -> None:
    plan = load_json(FIXTURES / "cycle_plan.json")
    graph, _, _ = build_graph(plan)

    assert find_cycles(graph)
    assert analyse_dependency_graph(plan)["critical_path"] == []
