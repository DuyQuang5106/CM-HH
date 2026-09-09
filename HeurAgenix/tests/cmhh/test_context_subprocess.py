from __future__ import annotations

import os
from cmhh.tracking.context import (
    RunLogContext,
    context_from_env,
    context_to_env,
    get_current_context,
    set_current_context,
    update_current_context,
)


def test_context_set_and_update() -> None:
    ctx = RunLogContext(run_id="run_123", task_id="tsp_20", stage="Stage A", worker_id="worker-0")
    set_current_context(ctx)

    current = get_current_context()
    assert current.run_id == "run_123"
    assert current.task_id == "tsp_20"
    assert current.stage == "Stage A"
    assert current.worker_id == "worker-0"

    update_current_context(stage="Stage B", generation=5)
    updated = get_current_context()
    assert updated.stage == "Stage B"
    assert updated.generation == 5
    assert updated.run_id == "run_123"


def test_context_env_propagation() -> None:
    ctx = RunLogContext(
        run_id="run_abc",
        task_id="cvrp_50",
        stage="evolution",
        worker_id="w-1",
        generation=2,
    )
    env = context_to_env(ctx)
    assert env["CMHH_RUN_ID"] == "run_abc"
    assert env["CMHH_TASK_ID"] == "cvrp_50"
    assert env["CMHH_STAGE"] == "evolution"
    assert env["CMHH_WORKER_ID"] == "w-1"
    assert env["CMHH_GENERATION"] == "2"

    restored = context_from_env(env)
    assert restored.run_id == "run_abc"
    assert restored.task_id == "cvrp_50"
    assert restored.stage == "evolution"
    assert restored.worker_id == "w-1"
    assert restored.generation == 2
