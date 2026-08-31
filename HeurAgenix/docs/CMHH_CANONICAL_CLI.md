# CM-HH Canonical CLI

The canonical experiment interface is the Python CLI exposed by `uv`:

```bash
uv sync
uv run cmhh --help
uv run cmhh run-stream --help
uv run cmhh run-suite --help
```

Execution boundary:

```text
experiment YAML   stream YAML
       \             /
        \           /
         Python CLI + CLI runtime overrides
                    |
                    v
              CM-HH runner
                    |
                    v
       artifacts, W&B logs, metrics, manifest
```

YAML files remain the source of truth for scientific configuration. The CLI is for runtime choices such as seed, run ID, resume, mode, generator, W&B mode, and temporary budget overrides. Shell scripts are optional Windows convenience wrappers only.

## Modes

```text
smoke       baseline generator, 1 generation, 1 candidate, 1 max LLM call, 60s timeout
quick-smoke HeurAgenix generator, 1 generation, 1 candidate, 2 max LLM calls, 120s timeout
pilot       HeurAgenix generator, 2 generations, 1 candidate, 5 max LLM calls, 300s timeout
full        HeurAgenix generator by convention; uses experiment YAML budget, 21600s timeout
```

## Examples

Smoke:

```bash
uv run cmhh run-suite --streams tsp_size_ascending --seeds 1 --mode smoke --skip-references --no-wandb
```

Pilot:

```bash
uv run cmhh run-suite --streams tsp_size_ascending --seeds 1 --mode pilot --llm-config cmhh/configs/llm/llm_config.local.json
```

Full:

```bash
uv run cmhh run-suite --streams tsp_size_ascending --seeds 1 --mode full --llm-config cmhh/configs/llm/llm_config.local.json
```

Multi-seed:

```bash
uv run cmhh run-suite --streams tsp_size_ascending --seeds 1 2 3 4 5 --mode smoke --skip-references --no-wandb
```

Resume:

```bash
uv run cmhh run-suite --streams tsp_size_ascending --seeds 1 2 3 --mode full --resume --llm-config cmhh/configs/llm/llm_config.local.json
```

Single experiment:

```bash
uv run cmhh run-stream --experiment cmhh/configs/experiments/h1_population_carryover.yaml --stream tsp_size_ascending --seed 1 --mode smoke --generator baseline --no-wandb
```

macOS, Linux, Windows, and server:

```bash
uv run cmhh run-suite --streams tsp_size_ascending --seeds 1 --mode smoke --skip-references --no-wandb
```

SLURM array:

```bash
uv run cmhh run-suite --streams tsp_size_ascending --seeds "$SLURM_ARRAY_TASK_ID" --mode full --llm-config cmhh/configs/llm/llm_config.local.json
```

Every runner invocation writes `resolved_config.yaml` next to run artifacts, alongside `manifest.json`, so runtime overrides are captured rather than only copying raw YAML.

## Old Commands

Old Windows wrapper:

```powershell
.\HeurAgenix\scripts\run_stream_1_tsp_ascending.ps1 -SmokeOnly -Seeds 1,2,3
```

New canonical command:

```bash
uv run cmhh run-suite --streams tsp_size_ascending --mode smoke --seeds 1 2 3 --skip-references --no-wandb
```

Old all-stream wrapper:

```powershell
.\HeurAgenix\scripts\run_all_streams_no_eoh.ps1 -Pilot -Seeds 1,2,3
```

New canonical command:

```bash
uv run cmhh run-suite --mode pilot --seeds 1 2 3
```
