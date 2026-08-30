# CM-HH handoff smoke checklist

Use this checklist before launching full 500-call or 1000-call experiments on a
GPU/server machine. The goal is to catch integration errors, not to produce
report-quality results.

## 1. Check dependencies

From the `HeurAgenix` directory:

```powershell
$env:PYTHONPATH="src"
python scripts/check_reference_solvers.py
python -m cmhh.cli --repo-root . validate-config --experiment cmhh/configs/experiments/h1_isolated.yaml --stream cmhh/configs/streams/tsp_size_ascending.yaml
```

Expected:

- Python imports work.
- Concorde/PyVRP/OR-Tools are found.
- `validate-config` exits with code 0.

## 2. Prepare data and references

For a data/reference-only check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 `
  -HandoffSmoke `
  -PrepareOnly
```

This validates representative TSP/CVRP/JSSP/cross-problem/stationary streams,
generates deterministic data, and verifies references.

## 3. Run a true LLM smoke

This uses real LLM calls but overrides the experiment configs only for this run.
The full experiment YAML files remain unchanged.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 `
  -HandoffSmoke `
  -Seeds 1 `
  -LlmConfig cmhh/configs/llm/llm_config.local.json
```

Default handoff-smoke budget:

```yaml
search:
  generations: 20
  candidates_per_generation: 3
  max_llm_calls: 30
```

A successful smoke should produce:

- `metrics.json`
- `performance_matrix.csv`
- `pre_learning_scores.json`
- passing `audit-run` for stream conditions
- no uncaught Python tracebacks in the driver log

## 4. Monitor progress

The runner prints a `RunPrefix`. Use it with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1 -RunPrefix <RUN_PREFIX>
```

Or follow the transcript directly:

```powershell
Get-Content cmhh/results/<RUN_PREFIX>_driver.log -Wait
```

## 5. Launch full budget only after smoke passes

For the current report budget:

```yaml
search:
  generations: 100
  candidates_per_generation: 5
  max_llm_calls: 500
```

Use the same budget for every compared condition. Do not mix smoke, 500-call,
and 1000-call results in one headline comparison.
