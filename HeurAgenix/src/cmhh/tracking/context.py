from __future__ import annotations

import contextvars
import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RunLogContext:
    run_id: str | None = None
    task_id: str | None = None
    stage: str | None = None
    problem: str | None = None
    seed: int | None = None
    worker_id: str | None = None
    generation: int | None = None
    llm_call_logger: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and k != "llm_call_logger"}


_CURRENT_CONTEXT: contextvars.ContextVar[RunLogContext] = contextvars.ContextVar(
    "current_run_log_context",
    default=RunLogContext(),
)


def get_current_context() -> RunLogContext:
    return _CURRENT_CONTEXT.get()


def set_current_context(context: RunLogContext) -> contextvars.Token:
    return _CURRENT_CONTEXT.set(context)


def update_current_context(**kwargs: Any) -> contextvars.Token:
    current = get_current_context()
    updated = RunLogContext(
        run_id=kwargs.get("run_id", current.run_id),
        task_id=kwargs.get("task_id", current.task_id),
        stage=kwargs.get("stage", current.stage),
        problem=kwargs.get("problem", current.problem),
        seed=kwargs.get("seed", current.seed),
        worker_id=kwargs.get("worker_id", current.worker_id),
        generation=kwargs.get("generation", current.generation),
        llm_call_logger=kwargs.get("llm_call_logger", current.llm_call_logger),
    )
    return set_current_context(updated)


def context_to_env(context: RunLogContext | None = None) -> dict[str, str]:
    ctx = context or get_current_context()
    env = {}
    if ctx.run_id is not None:
        env["CMHH_RUN_ID"] = str(ctx.run_id)
    if ctx.task_id is not None:
        env["CMHH_TASK_ID"] = str(ctx.task_id)
    if ctx.stage is not None:
        env["CMHH_STAGE"] = str(ctx.stage)
    if ctx.problem is not None:
        env["CMHH_PROBLEM"] = str(ctx.problem)
    if ctx.seed is not None:
        env["CMHH_SEED"] = str(ctx.seed)
    if ctx.worker_id is not None:
        env["CMHH_WORKER_ID"] = str(ctx.worker_id)
    if ctx.generation is not None:
        env["CMHH_GENERATION"] = str(ctx.generation)
    return env


def context_from_env(environ: dict[str, str] | None = None) -> RunLogContext:
    env = environ or os.environ
    seed_val = env.get("CMHH_SEED")
    seed_int = None
    if seed_val is not None:
        try:
            seed_int = int(seed_val)
        except ValueError:
            pass

    gen_val = env.get("CMHH_GENERATION")
    gen_int = None
    if gen_val is not None:
        try:
            gen_int = int(gen_val)
        except ValueError:
            pass

    return RunLogContext(
        run_id=env.get("CMHH_RUN_ID"),
        task_id=env.get("CMHH_TASK_ID"),
        stage=env.get("CMHH_STAGE"),
        problem=env.get("CMHH_PROBLEM"),
        seed=seed_int,
        worker_id=env.get("CMHH_WORKER_ID"),
        generation=gen_int,
    )
