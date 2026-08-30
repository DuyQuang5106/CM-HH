# CM-HH Data Artifacts

This directory contains task-specific datasets and reference values for CM-HH
experiments.

Each task has the same split layout:

```text
instances/{task_id}/
  train/
  validation/
  test/
  smoke/
references/{task_id}/
  reference.json
```

`reference.json` stores the per-instance baseline used by the evaluator when
computing relative gaps. If no solver-provided optimum is available yet, mark
the reference file as `pending` in `cmhh/configs/tasks/task_registry.yaml`.

