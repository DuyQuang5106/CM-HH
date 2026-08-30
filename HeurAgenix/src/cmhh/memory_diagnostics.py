from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


def build_memory_diagnostics(
    run_dir: str | Path,
    task_ids: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    events = _load_events(Path(run_dir) / "events.jsonl")
    retrieval_events = [event for event in events if event.get("event") == "memory_retrieved"]
    reuse_events = [event for event in events if event.get("event") == "memory_reuse_outcome"]
    transfer_plan_events = [event for event in events if event.get("event") == "memory_transfer_planned"]
    population_insert_events = [event for event in events if event.get("event") == "memory_inserted_into_population"]
    transfer_feedback_events = [event for event in events if event.get("event") == "memory_transfer_feedback"]
    eviction_events = [event for event in events if event.get("event") == "memory_evicted"]
    written_ids = {
        event["memory_id"]
        for event in events
        if event.get("event") == "memory_written" and event.get("memory_id")
    }
    retrieved_ids = [
        memory_id
        for event in retrieval_events
        for memory_id in event.get("memory_ids", [])
    ]
    retrieved_counts = Counter(retrieved_ids)
    source_tasks = [
        task_id
        for event in retrieval_events
        for task_id in event.get("source_tasks", [])
    ]
    duplicate_rates = [
        float(event["duplicate_key_rate"])
        for event in retrieval_events
        if event.get("duplicate_key_rate") is not None
    ]
    validation_deltas = [
        float(event["post_reuse_validation_delta"])
        for event in reuse_events
        if event.get("post_reuse_validation_delta") is not None
    ]
    planned_actions = Counter(
        plan.get("action")
        for event in transfer_plan_events
        for plan in event.get("plans", [])
        if plan.get("action")
    )
    transfer_records = [
        record
        for event in population_insert_events
        for record in event.get("transfer_records", [])
    ]
    inserted_memory_ids = [
        record.get("memory_id")
        for record in transfer_records
        if record.get("inserted_as_seed") and record.get("memory_id")
    ]
    context_memory_ids = [
        record.get("memory_id")
        for record in transfer_records
        if record.get("included_in_context") and record.get("memory_id")
    ]
    feedback_memory_ids = [
        memory_id
        for event in transfer_feedback_events
        for memory_id in event.get("memory_ids", [])
    ]
    eviction_lineage = [
        {
            "memory_id": event.get("memory_id"),
            "task_id": event.get("task_id"),
            "timestamp": event.get("timestamp"),
        }
        for event in eviction_events
        if event.get("memory_id")
    ]
    task_order = {task_id: index for index, task_id in enumerate(task_ids)}
    memory_ages = _memory_ages(retrieval_events, task_order)
    diagnostics = {
        "schema_version": 1,
        "retrieval_events": len(retrieval_events),
        "retrieval_events_with_results": sum(
            1 for event in retrieval_events if event.get("memory_ids")
        ),
        "memory_units_written": len(written_ids),
        "memory_units_retrieved": len(set(retrieved_ids)),
        "retrieval_coverage": (
            len(set(retrieved_ids)) / len(written_ids) if written_ids else None
        ),
        "total_retrieved_units": len(retrieved_ids),
        "transfer_plan_events": len(transfer_plan_events),
        "transfer_action_distribution": dict(sorted(planned_actions.items())),
        "memory_units_inserted_as_seed": len(set(inserted_memory_ids)),
        "memory_units_included_in_context": len(set(context_memory_ids)),
        "transfer_feedback_events": len(transfer_feedback_events),
        "memory_units_with_transfer_feedback": len(set(feedback_memory_ids)),
        "retrieval_to_seed_rate": (
            len(set(inserted_memory_ids)) / len(set(retrieved_ids)) if retrieved_ids else None
        ),
        "retrieval_to_context_rate": (
            len(set(context_memory_ids)) / len(set(retrieved_ids)) if retrieved_ids else None
        ),
        "top_k_concentration": (
            max(retrieved_counts.values()) / len(retrieved_ids) if retrieved_ids else 0.0
        ),
        "duplicate_key_rate_mean": mean(duplicate_rates) if duplicate_rates else None,
        "source_task_distribution": dict(sorted(Counter(source_tasks).items())),
        "memory_age_distribution": dict(sorted(Counter(memory_ages).items())),
        "post_reuse_validation_delta_mean": (
            mean(validation_deltas) if validation_deltas else None
        ),
        "post_reuse_validation_delta_values": validation_deltas,
        "eviction_lineage": eviction_lineage,
        "failure_mode_labels": [],
        "labels_are_diagnostic_heuristics": True,
    }
    diagnostics["failure_mode_labels"] = _label_failure_modes(diagnostics)
    return diagnostics


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _memory_ages(events: list[dict[str, Any]], task_order: dict[str, int]) -> list[str]:
    ages = []
    for event in events:
        current_task = event.get("task_id")
        current_index = task_order.get(current_task)
        for source_task in event.get("source_tasks", []):
            source_index = task_order.get(source_task)
            if current_index is None or source_index is None:
                ages.append("unknown")
            else:
                ages.append(str(max(0, current_index - source_index)))
    return ages


def _label_failure_modes(diagnostics: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    mean_delta = diagnostics["post_reuse_validation_delta_mean"]
    duplicate_rate = diagnostics["duplicate_key_rate_mean"]
    coverage = diagnostics["retrieval_coverage"]
    concentration = diagnostics["top_k_concentration"]
    retrieval_events = diagnostics["retrieval_events"]
    retrieved_events = diagnostics["retrieval_events_with_results"]
    total_retrieved = diagnostics["total_retrieved_units"]

    if mean_delta is not None and mean_delta < 0:
        labels.append("harmful_reuse")
    if mean_delta is not None and mean_delta <= 0:
        labels.append("ineffective_reuse")
    if duplicate_rate is not None and duplicate_rate >= 0.5:
        labels.append("retrieval_pollution")
    if total_retrieved and concentration >= 0.8:
        labels.append("retrieval_diversity_collapse")
    if coverage is not None and retrieval_events > 1 and coverage < 0.25:
        labels.append("memory_dilution")
    if retrieved_events and mean_delta is not None and mean_delta <= 0 and total_retrieved >= 5:
        labels.append("context_competition")
    return labels
