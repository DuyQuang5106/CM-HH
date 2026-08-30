# Phase 1 Experiment Guide

This guide runs the H1/H1b baseline stack:

1. `h1_isolated`: isolated cold-start, no stream memory.
2. `h1_population_carryover`: sequential stream, final population carries to
   the next task, no external memory.
3. `h1_naive_sequential`: the same population carryover plus naive external
   memory retrieval.
4. `h1_naive_unbounded`: the same naive memory policy without capacity pressure.
5. `archivist_managed`: managed-memory prototype with Archivist admission,
   task-anchor protection, and capacity-aware eviction.
6. `eoh_cold_start`: official EOH cold-start baseline where available.

The H1b control is frozen as:

`naive_memory_sequential = population_carryover + naive external memory`.

Naive memory must not replace population carryover.

`archivist_managed` is currently a managed-memory prototype, not yet the final
full CM-HH architecture. Full CM-HH still requires explicit
`CandidateExtractor`, `TransferPolicy`, `PopulationBuilder`, validation-only
transfer feedback, and child-memory lineage. See
`../../../IDEA/source_of_truth/CMHH_Archivist_Retriever_Design_Specification.md`
from the repository root for the full design.

## 1. Environment

Run commands from the `HeurAgenix` repository root.

```powershell
cd C:\Users\LENOVO\Projects\CM_HH\HeurAgenix
$env:PYTHONPATH = "src"
```

If you use the Conda environment:

```powershell
conda env create -f environment.yml
conda activate heuragenix
$env:PYTHONPATH = "src"
```

## 2. Validate Configs

```powershell
python -m cmhh.cli validate-config --experiment cmhh/configs/experiments/h1_isolated.yaml
python -m cmhh.cli validate-config --experiment cmhh/configs/experiments/h1_population_carryover.yaml
python -m cmhh.cli validate-config --experiment cmhh/configs/experiments/h1_naive_sequential.yaml
```

Warnings about missing frozen references or unfinished adapters are expected
until Phase 0 gates are complete. Errors should be fixed before running H1.

## 3. Prepare Data And References

Generate deterministic TSP data:

```powershell
python -m cmhh.cli generate-data --experiment cmhh/configs/experiments/h1_isolated.yaml --seed 42
```

Generate and verify reference values. Start with a small pilot:

```powershell
python -m cmhh.cli generate-references --experiment cmhh/configs/experiments/h1_isolated.yaml --split validation --split test --pilot-count 5
python -m cmhh.cli verify-references --experiment cmhh/configs/experiments/h1_isolated.yaml --split validation --split test
```

For a real H1/H1b run, remove `--pilot-count 5` after the pilot succeeds and
regenerate full validation/test references.

## 4. LLM Config

Copy `cmhh/configs/llm/llm_config.template.json` to a local ignored path, then
fill in provider URL, model, and API key.

Recommended local path:

```text
data/llm_config/cmhh_phase1.json
```

Do not commit the filled config.

## 5. Smoke Run Without LLM

This checks the runner, metrics, checkpointing, and memory artifacts cheaply.
It is not a scientific H1 result.

```powershell
python -m cmhh.cli run-isolated --experiment cmhh/configs/experiments/h1_isolated.yaml --generator baseline --run-id h1_isolated_smoke_seed1 --seed 1
python -m cmhh.cli run-stream --experiment cmhh/configs/experiments/h1_population_carryover.yaml --generator baseline --run-id h1_population_smoke_seed1 --seed 1 --cold-start-scores cmhh/results/h1_isolated_smoke_seed1/cold_start_scores.json
python -m cmhh.cli run-stream --experiment cmhh/configs/experiments/h1_naive_sequential.yaml --generator baseline --run-id h1_naive_smoke_seed1 --seed 1 --cold-start-scores cmhh/results/h1_isolated_smoke_seed1/cold_start_scores.json
```

Audit the stream runs:

```powershell
python -m cmhh.cli audit-run --experiment cmhh/configs/experiments/h1_population_carryover.yaml --run-id h1_population_smoke_seed1
python -m cmhh.cli audit-run --experiment cmhh/configs/experiments/h1_naive_sequential.yaml --run-id h1_naive_smoke_seed1
```

## 6. Real Phase 1 Runs

Run the isolated cold-start condition first because it produces
`cold_start_scores.json` for forward transfer.

```powershell
python -m cmhh.cli run-isolated --experiment cmhh/configs/experiments/h1_isolated.yaml --generator heuragenix --llm-config data/llm_config/cmhh_phase1.json --run-id h1_isolated_seed1 --seed 1
```

Run H1 population carryover:

```powershell
python -m cmhh.cli run-stream --experiment cmhh/configs/experiments/h1_population_carryover.yaml --generator heuragenix --llm-config data/llm_config/cmhh_phase1.json --run-id h1_population_carryover_seed1 --seed 1 --cold-start-scores cmhh/results/h1_isolated_seed1/cold_start_scores.json
```

Run H1b naive external memory:

```powershell
python -m cmhh.cli run-stream --experiment cmhh/configs/experiments/h1_naive_sequential.yaml --generator heuragenix --llm-config data/llm_config/cmhh_phase1.json --run-id h1_naive_memory_seed1 --seed 1 --cold-start-scores cmhh/results/h1_isolated_seed1/cold_start_scores.json
```

If a run is interrupted, resume with the same run id:

```powershell
python -m cmhh.cli run-stream --experiment cmhh/configs/experiments/h1_naive_sequential.yaml --generator heuragenix --llm-config data/llm_config/cmhh_phase1.json --run-id h1_naive_memory_seed1 --seed 1 --cold-start-scores cmhh/results/h1_isolated_seed1/cold_start_scores.json --resume
```

## 7. Multi-Seed Loop

After one audited seed succeeds, repeat for seeds 1, 2, and 3.

```powershell
foreach ($seed in 1,2,3) {
  python -m cmhh.cli run-isolated --experiment cmhh/configs/experiments/h1_isolated.yaml --generator heuragenix --llm-config data/llm_config/cmhh_phase1.json --run-id "h1_isolated_seed$seed" --seed $seed
  python -m cmhh.cli run-stream --experiment cmhh/configs/experiments/h1_population_carryover.yaml --generator heuragenix --llm-config data/llm_config/cmhh_phase1.json --run-id "h1_population_carryover_seed$seed" --seed $seed --cold-start-scores "cmhh/results/h1_isolated_seed$seed/cold_start_scores.json"
  python -m cmhh.cli run-stream --experiment cmhh/configs/experiments/h1_naive_sequential.yaml --generator heuragenix --llm-config data/llm_config/cmhh_phase1.json --run-id "h1_naive_memory_seed$seed" --seed $seed --cold-start-scores "cmhh/results/h1_isolated_seed$seed/cold_start_scores.json"
}
```

## 8. Artifacts To Inspect

For every stream run:

- `cmhh/results/<run-id>/performance_matrix.csv`
- `cmhh/results/<run-id>/metrics.json`
- `cmhh/results/<run-id>/events.jsonl`
- `cmhh/results/<run-id>/checkpoints/latest.json`

For naive-memory runs:

- `cmhh/results/<run-id>/memory/memory.jsonl`
- `cmhh/results/<run-id>/memory/diagnostics.json`
- `cmhh/results/<run-id>/candidates/<task-id>/memory_context.json`

Key diagnostics in `memory/diagnostics.json`:

- `retrieval_coverage`
- `top_k_concentration`
- `duplicate_key_rate_mean`
- `source_task_distribution`
- `memory_age_distribution`
- `post_reuse_validation_delta_mean`
- `failure_mode_labels`

## 9. Interpretation

H1 compares `h1_isolated` against `h1_population_carryover`.

H1b compares `h1_population_carryover` against `h1_naive_sequential`.

Use `average_final_performance`, `backward_transfer`, and `forward_transfer`
from `metrics.json`. Use the naive-memory diagnostics only to explain why H1b
helped or hurt; do not use test results for memory writing, retrieval scoring,
candidate selection, or stopping decisions.
