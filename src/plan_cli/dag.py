from __future__ import annotations

from collections import deque
from typing import Any

import networkx as nx

from .planning import flatten_tasks, task_dependencies, task_duration_hours

# Dependency graph analysis helpers for the /plan runtime.


def build_graph(plan: dict[str, Any]) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
    graph = nx.DiGraph()
    tasks = flatten_tasks(plan)
    task_ids = {task["id"] for task in tasks if task.get("id")}
    external_edges: list[dict[str, Any]] = []

    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            continue
        graph.add_node(task_id, task=task, duration_hours=task_duration_hours(task))

    for task in tasks:
        task_id = task.get("id")
        if not task_id:
            continue
        for dep in task_dependencies(task):
            if dep in task_ids:
                graph.add_edge(dep, task_id, type="hard")
            else:
                external_edges.append({"from": dep, "to": task_id, "type": "external"})

    return graph, tasks, external_edges


def find_cycles(graph: Any) -> list[list[str]]:
    try:
        return [list(cycle) for cycle in nx.simple_cycles(graph)]
    except nx.NetworkXError:
        return []


def topological_order(graph: Any) -> list[str]:
    try:
        return list(nx.topological_sort(graph))
    except nx.NetworkXUnfeasible:
        return []


def critical_path(graph: Any) -> dict[str, Any]:
    nodes = list(graph.nodes)
    if not nodes:
        return {"path": [], "total_hours": 0.0, "tasks": []}

    order = topological_order(graph)
    if not order:
        return {"path": [], "total_hours": 0.0, "tasks": []}

    duration = {node: float(graph.nodes[node].get("duration_hours", 0.0)) for node in nodes}
    dist = {node: duration[node] for node in nodes}
    parent: dict[str, str | None] = {node: None for node in nodes}

    for node in order:
        for succ in graph.successors(node):
            candidate = dist[node] + duration[succ]
            if candidate > dist[succ]:
                dist[succ] = candidate
                parent[succ] = node

    end_node = max(nodes, key=lambda node: dist[node])
    path: list[str] = []
    current = end_node
    while current is not None:
        path.append(current)
        current = parent[current]
    path.reverse()

    return {
        "path": path,
        "total_hours": dist[end_node],
        "tasks": [graph.nodes[node]["task"] for node in path],
    }


def execution_waves(graph: Any) -> list[list[str]]:
    indegree = {node: graph.in_degree(node) for node in graph.nodes}
    remaining = set(graph.nodes)
    waves: list[list[str]] = []

    while remaining:
        wave = sorted(node for node in remaining if indegree[node] == 0)
        if not wave:
            break
        waves.append(wave)
        for node in wave:
            remaining.remove(node)
            for succ in graph.successors(node):
                indegree[succ] -= 1

    return waves


def blockers(graph: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for node in graph.nodes:
        successors = list(graph.successors(node))
        if len(successors) >= 2:
            items.append({"task": node, "blocks": successors, "block_count": len(successors)})
    return sorted(items, key=lambda item: item["block_count"], reverse=True)


def single_points_of_failure(graph: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for node in graph.nodes:
        task = graph.nodes[node].get("task", {})
        priority = task.get("priority") or task.get("phase_priority") or "medium"
        if priority != "critical":
            continue

        downstream: set[str] = set()
        queue = deque([node])
        visited = {node}
        while queue:
            current = queue.popleft()
            for succ in graph.successors(current):
                if succ not in visited:
                    visited.add(succ)
                    downstream.add(succ)
                    queue.append(succ)

        if downstream:
            items.append(
                {
                    "task": node,
                    "description": task.get("description", ""),
                    "downstream_count": len(downstream),
                    "downstream": sorted(downstream),
                }
            )

    return sorted(items, key=lambda item: item["downstream_count"], reverse=True)


def generate_mermaid(graph: Any, critical: dict[str, Any]) -> str:
    lines = ["graph TD"]
    critical_nodes = set(critical.get("path", []))

    for node in graph.nodes:
        task = graph.nodes[node].get("task", {})
        phase = task.get("phase_name") or task.get("phase_id") or ""
        duration = graph.nodes[node].get("duration_hours", 0.0)
        label = f"{node}<br/>{phase}<br/>{duration:g}h".replace('"', "'")
        symbol = node.replace("-", "_")
        if node in critical_nodes:
            lines.append(f'  {symbol}["{label}"]:::critical')
        else:
            lines.append(f'  {symbol}["{label}"]')

    lines.append("")
    for source, target in graph.edges:
        lines.append(f"  {source.replace('-', '_')} --> {target.replace('-', '_')}")

    lines.append("")
    lines.append("  classDef critical fill:#ff6b6b,stroke:#c92a2a,color:#fff")
    return "\n".join(lines)


def analyse_dependency_graph(plan: dict[str, Any]) -> dict[str, Any]:
    graph, tasks, external_edges = build_graph(plan)
    cycles = find_cycles(graph)
    critical = critical_path(graph)
    waves = execution_waves(graph)
    blocking = blockers(graph)
    spofs = single_points_of_failure(graph)

    edges = [
        {"from": source, "to": target, "type": data.get("type", "hard")}
        for source, target, data in graph.edges(data=True)
    ]
    edges.extend(external_edges)

    return {
        "task_count": len(tasks),
        "edge_count": len(edges),
        "nodes": list(graph.nodes),
        "edges": edges,
        "external_edges": external_edges,
        "cycles": cycles,
        "critical_path": critical.get("path", []),
        "critical_path_hours": critical.get("total_hours", 0.0),
        "execution_waves": waves,
        "blockers": blocking,
        "single_points_of_failure": spofs,
        "mermaid": generate_mermaid(graph, critical),
        "tasks": tasks,
        "topological_order": topological_order(graph),
    }
