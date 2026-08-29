# CM-HH Implementation Log

This file is the cumulative engineering and research log for CM-HH. Future
phases must append to it instead of creating a separate implementation log.

## Conventions

- `Done`: implemented and verified locally.
- `In progress`: implementation exists but its milestone is not fully verified.
- `Planned`: agreed scope, not implemented yet.
- Experimental results are never inferred from development smoke runs.
- Test data is reserved for final evaluation; candidate selection uses validation
  data only.

## 2026-08-14 — Phase 0 started

### Goal

Build a reproducible experimental foundation before testing H1. The first
end-to-end target is the within-problem stream:

`TSP-20 -> TSP-50 -> TSP-100 -> TSP-200`.

OBP and PFSP remain registered for later phases, but their adapters are outside
the Phase 0 critical path.

### Decisions

1. Generated TSP instances use integer coordinates and TSPLIB `EUC_2D`
   distances so the evaluator and an external exact solver can share precisely
   the same problem definition.
2. Data generation is deterministic. Every instance seed is derived from the
   experiment seed, task, split, and instance index.
3. Reference records distinguish `optimal` from `best_known`. Phase 0 does not
   claim optimality unless an exact solver certifies it.
4. Raw relative gap remains a lower-is-better reporting metric. Continual
   metrics consume `score = -relative_gap`, making higher consistently better.
5. LLM-generated heuristics must run in a child process with a timeout. The
   existing HeurAgenix `load_function()` uses `exec()` and is therefore only
   allowed inside the worker process for CM-HH evaluation.
6. Phase 0 uses existing TSP heuristics as the initial integration baseline.
   LLM evolution is connected only after data and evaluation are trustworthy.

### Work packages

- [x] Task registry expanded to TSP/OBP/PFSP at n20/n50/n100/n200.
- [x] 0A: protocol and stream configuration.
- [x] 0B: domain models and config validation.
- [x] 0C: deterministic TSP data generation and manifests.
- [~] 0D: reference schema and relative-gap calculation; exact reference files pending.
- [x] 0E: subprocess evaluator and failure handling.
- [x] 0F: baseline smoke evaluation.
- [~] 0G: LLM adapter implemented and tested structurally; live provider run pending.
- [~] 0H: resumable stream runner implemented; end-to-end run awaits references.
- [x] 0I: continual metrics and performance matrix implementation.
- [~] 0J: reproducibility manifest and audit implemented; live full-run audit pending.

### Known external dependency

Exact reference generation requires a separately installed Concorde executable.
The repository will support importing solver output and will never silently
label a heuristic result as optimal. Until certified references are available,
development runs may use explicitly labelled `best_known` references.

### Implemented files

- `cmhh/configs/experiments/phase0_tsp.yaml`: development budgets and data sizes.
- `cmhh/configs/streams/tsp_size_ascending.yaml`: initial four-task stream.
- `docs/cmhh/experimental_protocol.md`: data isolation and fairness rules.
- `src/cmhh/config.py`, `models.py`, `validation.py`: typed configuration boundary.
- `src/cmhh/data/`: deterministic generator, checksums, TSPLIB fallback reader, and
  reference record schema.
- `src/cmhh/evaluation/`: subprocess evaluator and worker.
- `src/cmhh/metrics/`: relative gap, normalized score, average performance, BWT,
  and FWT.
- `src/cmhh/agents/generator.py`: generator protocol plus no-LLM baseline generator.
- `src/cmhh/runner.py`, `checkpoint.py`, `reproducibility.py`: resumable stream
  orchestration and audit metadata.
- `src/cmhh/cli.py`: config validation, data generation, baseline evaluation, and
  stream-run commands.

### Verification performed

Commands were executed from the HeurAgenix repository root with
`PYTHONPATH=src`.

1. `python -m unittest discover -s tests/cmhh -v`
   - 5 tests passed.
   - Covers deterministic/unique coordinates, TSPLIB parsing, objective and
     continual metrics, and termination of a deliberately infinite heuristic.
2. `python -m cmhh.cli validate-config`
   - Loaded 12 registered tasks and the four-task TSP stream.
   - TSP data paths exist after generation; reference files remain pending.
   - OBP/PFSP correctly report missing adapters and artifacts as warnings.
3. `python -m cmhh.cli generate-data --seed 42`
   - Generated train/validation/test/smoke datasets and checksummed manifests for
     TSP n20, n50, n100, and n200.
4. `python -m cmhh.cli evaluate-baselines --split smoke`
   - `nearest_neighbor_f91d`, `random_80a0`, and `greedy_algorithm_3ca7` completed
     valid solutions on both smoke instances at every TSP size.
   - All 12 task/heuristic combinations reported zero failure rate.
   - Relative gap is intentionally `null` until external references exist.
5. `python -m compileall -q src/cmhh tests/cmhh` and `git diff --check`
   completed without code or whitespace errors.

### Environment finding

The active Windows Python installation does not contain `tsplib95`, although it
is declared in `environment.yml`. CM-HH now supplies a narrowly scoped fallback
reader for generated `EUC_2D` instances. The evaluator will still use the real
`tsplib95` package automatically when it is installed. The fallback follows the
TSPLIB nearest-integer distance rule and is covered by tests.

### Remaining Phase 0 critical path

1. Install/configure Concorde and generate immutable test/validation references.
2. Verify reference checksums and run the baseline stream to produce the first
   complete performance matrix.
3. Supply an LLM config, adapt `HeuristicEvolver` behind `HeurAgenixGenerator`,
   and run one low-budget TSP-n20 evolution.
4. Run and resume an interrupted four-task stream, then audit its manifest,
   checkpoint, evaluations, matrix, and metrics.

The runner deliberately stops if references are absent. It does not substitute
raw objectives for normalized continual scores, because objectives from
different TSP sizes are not comparable.

## 2026-08-14 — Concorde reference pipeline

### Motivation

Concorde reference generation is treated as one-time dataset preparation, not
as part of each experimental condition. The same frozen test instances and
reference files will be reused across algorithm seeds, memory policies, and
curriculum orders.

The data seed is now independent from experiment seeds:

- `data.seed: 42` controls instance generation and therefore reference identity.
- `experiment.seeds` controls future heuristic evolution randomness.

This prevents a multi-seed experiment from accidentally generating a new test
set and requiring Concorde to run again for every seed.

### Implemented

1. Added `cmhh/configs/solvers/concorde.yaml` with a configurable command,
   per-size timeouts, and bounded worker count.
2. Added `src/cmhh/references/concorde.py`:
   - validates the external executable before starting work;
   - invokes each solver job in an isolated temporary directory;
   - enforces a per-instance timeout;
   - distinguishes timeout, process failure, missing output, and invalid tour;
   - only emits an `optimal` record after a successful solver exit and tour
     validation.
3. Added `src/cmhh/references/tour.py`:
   - accepts common Concorde tour output with or without a leading dimension;
   - normalizes one-based and zero-based node IDs;
   - verifies the tour is a complete permutation;
   - recomputes the objective using CM-HH's TSPLIB `EUC_2D` distance rule.
4. Added `src/cmhh/references/pipeline.py`:
   - parallel execution with a configurable maximum worker count;
   - pilot mode using the first N instances;
   - incremental atomic reference writes;
   - checksum-based cache/resume;
   - structured solver-failure logs.
5. Added `src/cmhh/references/verification.py` to check coverage, instance
   checksum, tour existence, tour validity, objective equality, and counts of
   `optimal` versus `best_known` records.
6. Added CLI commands:

   ```powershell
   python -m cmhh.cli generate-references --pilot-count 5 --split test
   python -m cmhh.cli generate-references --split test
   python -m cmhh.cli verify-references --split test
   ```

7. The default workflow generates test references only. Validation candidates
   can be ranked by mean objective on the same validation instances, so exact
   validation references are optional and can be requested explicitly.

### Verification performed

- Added a fake Concorde executable fixture that follows the command/output
  contract without requiring a local Concorde installation.
- The adapter test executes it as a subprocess, parses the generated tour,
  normalizes it, and independently recomputes the objective.
- Full CM-HH test suite result: 6 tests passed.
- `compileall`, config validation, and `git diff --check` passed.
- The deliberately infinite heuristic timeout test continues to pass.
- Running the real command currently exits before starting jobs with the clear
  message that `tools/concorde/concorde.exe` is missing. No partial reference is
  created and no fake objective is substituted.

### External action still required

Place a licensed academic Concorde executable at
`tools/concorde/concorde.exe`, or update `command_prefix` in
`cmhh/configs/solvers/concorde.yaml` to its actual location. Then run the
five-instance-per-size pilot before the full test set.

Suggested sequence:

```powershell
$env:PYTHONPATH = "src"
python -m cmhh.cli generate-references --pilot-count 5 --split test
python -m cmhh.cli verify-references --split test
python -m cmhh.cli generate-references --split test
python -m cmhh.cli verify-references --split test
```

The pilot verification is expected to report missing references for non-pilot
instances; this is coverage information, not solver corruption. Full
verification must pass before producing the Phase 0 performance matrix.

## 2026-08-15 - Memory architecture decision

### Research decision

CM-HH adopts the memory architecture from *When Continual Learning Moves to
Memory: A Study of Experience Reuse in LLM Agents* as the main conceptual
memory model for Phase 1.

In this model, memory is not a loose archive of logs. It is a shared external
experience pool `M` that grows across tasks. Each memory item is a retrievable
unit represented as a key-value pair:

- `key`: the retrieval-facing description of when the item should be reused.
  In CM-HH this may include task identity, problem features, search state
  signature, bottleneck type, heuristic family, and applicability conditions.
- `value`: the reusable content. In CM-HH this should usually be a distilled
  insight, rule, warning, or code-adjustment rationale, with raw trajectories
  retained only as evidence.

This separates memory representation from memory access:

- Representation axis: raw trajectory versus abstract procedural insight.
- Organization axis: aggregated task-level bundle versus individual insight
  entries, plus retrieval timing and top-k policy.

The default research stance is that CM-HH should prefer abstract procedural
insights over raw run transcripts for cross-task reuse, because raw traces are
more likely to overfit to a source task and create harmful retrieval pollution.

### Archivist role

The Archivist is the memory writer, curator, and compactor. It does not merely
append artifacts. Its responsibilities are:

1. convert candidate-generation traces, bottleneck analyses, validation
   outcomes, selected heuristics, rejected heuristics, and refinement
   suggestions into structured memory units;
2. assign retrieval keys that describe applicability rather than only origin;
3. keep evidence links to raw artifacts, scores, hashes, and task context;
4. update confidence after later reuse succeeds or fails;
5. compact or evict memory under the configured capacity policy;
6. protect experimental isolation by never allowing test results into memory
   used for generation, retrieval scoring, candidate selection, or stopping.

The existing `naive_overwrite` archive config is therefore only one concrete
memory policy. It should be interpreted as a baseline policy over the external
memory pool, not as the definition of memory itself.

### Provisional memory unit schema

The Phase 1 implementation should make memory explicit with a schema equivalent
to:

```json
{
  "id": "stable memory id",
  "created_at": "run/task/generation step",
  "scope": {
    "problem": "tsp",
    "task_id": "tsp_n50_uniform",
    "heuristic_family": "nearest_neighbor"
  },
  "key": {
    "task_signature": {},
    "state_signature": {},
    "bottleneck_type": "construction_bias | local_optimum | invalid_code | ...",
    "applicability": "short natural-language retrieval key"
  },
  "value": {
    "type": "insight | rule | warning | code_adjustment | trajectory",
    "content": "reusable distilled content"
  },
  "evidence": {
    "source_artifacts": [],
    "validation_before": {},
    "validation_after": {},
    "code_hashes": []
  },
  "policy": {
    "confidence": 0.0,
    "reuse_count": 0,
    "success_count": 0,
    "failure_count": 0
  }
}
```

### H1 theory work still required

Before running scientific H1 experiments, the hypothesis must specify the
memory condition, control condition, and failure modes more sharply.

Required theory definitions:

1. Define the H1 claim in memory terms: external insight memory across a task
   stream improves sequential heuristic search relative to isolated or
   memoryless search under the same LLM/evaluation budget.
2. Define the unit of transfer: memory-assisted improvement should be measured
   through candidate quality, selected heuristic quality, and final test score,
   not only by the number of retrieved memories.
3. Define negative-transfer diagnostics: harmful reuse, ineffective reuse,
   retrieval pollution, context competition, memory dilution, and retrieval
   diversity collapse.
4. Define memory policy variants before experiments:
   - no-memory isolated baseline;
   - naive sequential memory with capacity and deterministic eviction;
   - insight memory with retrieval keys and Archivist distillation;
   - optionally raw-trajectory memory as an ablation.
5. Define retrieval metrics that can be audited without test leakage:
   retrieval coverage, top-k concentration, duplicate-key rate, age/source
   distribution, and post-reuse validation delta.
6. Define fairness constraints: same task order, data seed, experiment seeds,
   LLM model/config, LLM-call budget, candidate budget, timeout, validation
   split, test split, and archive capacity across compared policies.

The core theoretical risk is that memory can improve adaptation to later tasks
while degrading earlier-task performance through retrieval-side interference.
Therefore H1 should be evaluated with both final average performance and
continual metrics such as FWT/BWT, plus retrieval diagnostics that explain why
transfer helped or harmed.

### Status after this increment

- Reference code path: done and tested.
- Exact reference artifacts: blocked on the external Concorde executable.
- LKH/best-known fallback: still planned; it is only needed for exact-solver
  timeouts, primarily possible at n200.
- LLM evolution adapter: implemented later in this log; live provider validation remains pending.

## 2026-08-14 — Generator, isolated baseline, resume, and H1 boundary

### Scope

Implemented the remaining code-level work from Milestones B–D. No live LLM
request and no scientific H1 run were performed because the local LLM config,
API credentials, and exact reference artifacts are not available yet.

### Secret-safe LLM configuration

- Added `cmhh/configs/llm/llm_config.template.json` as a commit-safe example.
- Real credentials remain under the already ignored `data/` directory.
- Added `src/cmhh/llm/config.py` to redact API keys/tokens/passwords before
  snapshots and compute a fingerprint that does not contain or depend on the
  secret value.
- Generated run artifacts store model/config metadata but never the API key.

### Hard LLM budget

Added `BudgetedLLMClient` in `src/cmhh/llm/budgeted_client.py`.

- The budget counts actual provider attempts, including retries.
- Both normal chat and tool calls consume the same global budget.
- Indirect calls from methods such as `load_background()` are intercepted; they
  cannot bypass the proxy by calling the underlying client's `self.chat()`.
- Exhaustion raises `LLMBudgetExceeded` before another provider request starts.

This is required for fair comparisons: `max_llm_calls: 10` is now enforceable,
not merely descriptive configuration.

### HeurAgenix evolution adapter

Added:

- `src/cmhh/agents/heuragenix_generator.py`
- `src/cmhh/agents/heuragenix_worker.py`

The adapter:

1. accepts a CM-HH task, seed population, search budget, and seed;
2. creates a sanitized LLM config snapshot;
3. launches the complete HeurAgenix evolution inside a subprocess;
4. maps train to `evolution_dir` and validation to `validation_dir`;
5. enforces both the LLM-call budget and a whole-worker timeout;
6. parses generated Python with `ast` before creating an artifact;
7. records code hash, parent ID, task ID, generation, prompt hash, model, and
   LLM calls used;
8. leaves smoke and validation acceptance to the existing isolated CM-HH
   evaluator.

`HeuristicEvolver` received an optional `output_root`. The default remains
`output`, preserving the original CLI behavior, while CM-HH writes evolution
artifacts under `cmhh/results/<run_id>/candidates` rather than changing source
heuristic directories.

The subprocess boundary is intentional. The upstream evolver imports and
executes generated code during its internal analysis; running the whole
evolver in a worker prevents a generated-code crash from terminating the CM-HH
orchestrator. Final candidate acceptance still uses the stricter per-instance
CM-HH evaluator.

### Candidate selection

Both `evolve-task` and stream execution now follow:

`syntax -> smoke -> validation -> deterministic rank`.

Candidates with smoke or validation failures are rejected. Ranking uses mean
validation objective, failure rate where applicable, mean runtime, then
heuristic ID. Test results are not used for selection.

Added development command:

```powershell
python -m cmhh.cli evolve-task `
  --task tsp_n20_uniform `
  --llm-config data/llm_config/cmhh_phase0.json `
  --seed 42 `
  --max-llm-calls 3
```

This command has not been executed against a real provider.

### Isolated baseline and FWT plumbing

Added `run-isolated` to evolve/select each task independently from the same
built-in seed pool and write `cold_start_scores.json`.

```powershell
python -m cmhh.cli run-isolated `
  --experiment cmhh/configs/experiments/h1_isolated.yaml `
  --generator heuragenix `
  --llm-config data/llm_config/cmhh_phase0.json `
  --run-id phase0_isolated_seed1
```

Sequential `run-stream` accepts `--cold-start-scores`; when supplied,
`metrics.json` includes FWT in addition to average final performance and BWT.
References remain mandatory for test scores.

### Resume and audit

- `run-stream` now requires `--resume` when a checkpoint already exists and
  rejects resume if no checkpoint exists.
- Resume timestamps are appended to the run manifest.
- A verified unit test interrupts before task two, resumes, and confirms task
  one is not generated again.
- The runner writes ordered selection/test-evaluation events.
- Added `audit-run`, which verifies input config/data hashes, selected code
  hashes, candidate selection before test evaluation, and possible test-path
  leakage in generation artifacts.

```powershell
python -m cmhh.cli audit-run --run-id <run_id>
```

### Provisional H1 configuration boundary

Added:

- `cmhh/configs/experiments/h1_isolated.yaml`
- `cmhh/configs/experiments/h1_naive_sequential.yaml`
- `cmhh/configs/archive/naive_overwrite.yaml`

The provisional naive archive capacity is 20, with no protected exemplars and
deterministic eviction tie-breakers. These values are not frozen for the paper
until Phase 0 live runs establish a reasonable development budget. The actual
Archivist/eviction implementation belongs to Phase 1 and has not been added
prematurely.

### Verification performed

- Full test suite: 10 tests passed.
- New coverage includes secret redaction, config fingerprinting, hard provider
  budget across retries and indirect calls, minimal run audit, and checkpoint
  resume without regenerating completed tasks.
- `compileall` passed for CM-HH, the modified evolver, and tests.
- Both Phase 0 and provisional H1 configs validate.
- `git diff --check` passed.

### Remaining live gates before Phase 1 experiments

1. Install/configure Concorde, run the five-instance pilot, then generate and
   verify all frozen test references.
2. Create a real ignored LLM config and perform the three-call TSP-n20
   `evolve-task` smoke run.
3. Run all four isolated tasks and produce `cold_start_scores.json`.
4. Run/resume the four-task sequential integration with those cold-start scores.
5. Run `audit-run`, inspect raw outputs, and freeze H1 capacity/budget before
   collecting multi-seed results.

Code paths for these gates now exist. Their scientific artifacts cannot be
claimed until the external solver and LLM provider have actually run.

## 2026-08-14 — Local Concorde installation

### Source and license scope

Downloaded the official Windows/Cygwin executable from the University of
Waterloo Concorde distribution page for academic research use:

`https://math.uwaterloo.ca/tsp/concorde/downloads/codes/cygwin/concorde.exe.gz`

The official executable is 32-bit and requires a 32-bit Cygwin runtime. A
minimal archived Cygwin environment was installed locally under
`tools/concorde/`, using the archive URL documented by Cygwin. The required
`cygwin1.dll` was copied next to `concorde.exe`. The installer and compressed
Concorde download were removed. The local Cygwin package/cache directories are
retained but ignored by Git; cleanup was attempted, but their Cygwin-created
ACLs prevented a complete non-elevated deletion. Nothing was installed
system-wide and the system PATH was not changed.

Installed runtime files (ignored by Git):

- `tools/concorde/concorde.exe`
  - SHA-256: `91DF25374C16C407A9EEC8F03EFB846DDB72A2AB8EEEFD0BF5F6345A3998859A`
- `tools/concorde/cygwin1.dll`
  - SHA-256: `F1F04586DA69854A6E00F978DCA5EDB8318BD585F51AA88C5FD6BA9B0E3FBB65`

The downloaded compressed executable had SHA-256
`3A37CEF9EA805B367D6F35724374541CF516E71B213A9822AC8A8507F8720001`.

### Compatibility fixes

1. The Cygwin executable cannot consume Windows drive-letter paths reliably.
   The wrapper now copies each instance into its isolated temporary directory
   and passes relative `problem.tsp`/`solution.sol` paths.
2. This legacy build returns process exit code 255 even when it writes a valid
   tour and proves optimality. CM-HH accepts this special case only when all of
   the following hold:
   - a complete valid tour file exists;
   - stdout contains `Optimal Solution`;
   - stdout contains `DIFF: 0`;
   - the printed objective equals the objective independently recomputed by
     CM-HH.
   The original exit code is retained in each reference record for audit.

### Installation verification

- Native smoke command `concorde -s 99 -k 20` completed and reported exact
  optimum 72.
- `cygcheck` showed the only non-system runtime dependency was `cygwin1.dll`.
- CM-HH reference generation succeeded on one frozen test instance per size:

| Task | Status | Objective | Solver runtime |
| --- | --- | ---: | ---: |
| TSP-20 | optimal | 45442 | 0.110 s |
| TSP-50 | optimal | 55865 | 0.242 s |
| TSP-100 | optimal | 77442 | 0.216 s |
| TSP-200 | optimal | 107815 | 0.327 s |

These are installation pilots, not experimental results. The remaining 29 test
instances per size still require reference generation and full verification.

## 2026-08-16 - Phase 1A population carryover and memory schema scaffold

### Scope

Started Phase 1 implementation from `../planning/Implementation_plan.md`.

This increment implements the lowest-level H1 baseline:

`population_carryover`: no explicit external memory, no Archivist retrieval, no
distillation, no protection, and no eviction. The final ranked candidate
population after task `k` is persisted in the stream checkpoint and used as the
seed population for task `k+1`.

This separates H1 from H1b:

- H1 tests forgetting from sequential adaptation and population drift.
- H1b will later test retrieval-side interference from naive external memory.

### Implemented

1. Added `experiment.condition` to `ExperimentConfig`.
   - Default is `independent_seed`, preserving Phase 0 behavior.
   - Allowed conditions include `isolated_task`, `population_carryover`, and
     `naive_memory_sequential`.
2. Added `cmhh/configs/experiments/h1_population_carryover.yaml`.
3. Updated `StreamRunner`:
   - ranks all smoke/validation-valid candidates, not only the best one;
   - selects the first ranked candidate as before;
   - stores ranked population in checkpoints as `carryover_population`;
   - when condition is `population_carryover`, seeds the next task from that
     ranked population if the problem family is compatible;
   - logs `population_carried_over` events.
4. Updated manifest metadata to record the experiment condition.
5. Renamed the naive-memory config condition from `naive_sequential` to
   `naive_memory_sequential`.
6. Added `src/cmhh/memory.py` as the Phase 1B schema scaffold:
   - `MemoryScope`
   - `MemoryKey`
   - `MemoryValue`
   - `MemoryEvidence`
   - `MemoryPolicyState`
   - `MemoryUnit`
7. Restored the missing `src/cmhh/data` package required by existing CM-HH
   imports and tests:
   - `manifest.py`
   - `references.py`
   - `tsp_io.py`
   - `tsp_generator.py`
8. Updated `tour_objective()` to support both matrix-style distance graphs and
   dict-edge graphs.

### Tests added

- `test_population_carryover_seeds_next_task_from_ranked_population`
  verifies that task 2 receives the ranked valid population from task 1 rather
  than falling back to built-in baselines.
- `test_memory_unit_round_trips_through_dict` verifies the schema can be
  serialized and reloaded.

### Verification performed

Commands executed from the HeurAgenix repository root with `PYTHONPATH=src`.

1. `python -m unittest discover -s tests/cmhh -v`
   - 12 tests passed.
2. `python -m compileall -q src/cmhh tests/cmhh`
   - passed.
3. `python -m cmhh.cli validate-config`
   - passed with expected pending-artifact/adapter warnings.
4. `python -m cmhh.cli validate-config --experiment cmhh/configs/experiments/h1_population_carryover.yaml`
   - passed with expected pending-artifact/adapter warnings.
5. `git diff --check -- HeurAgenix`
   - passed; Git only reported Windows CRLF/LF conversion warnings.

### Remaining Phase 1 work

1. Implement persisted memory records and deterministic memory IDs.
2. Implement `naive_memory_sequential` retrieval over `MemoryUnit`.
3. Add retrieval diagnostics for H1b.
4. Run the H1 population-carryover pilot only after Phase 0 references and live
   LLM gates are complete.

## 2026-08-16 - Phase 1B persisted memory object model

### Scope

Completed the remaining Phase 1B memory-object work from
`../planning/Implementation_plan.md`.

This increment still does not enable memory retrieval in the runner. It makes
memory auditable and persistable so Phase 1C can implement naive external
memory without inventing ad hoc dict formats.

### Implemented

1. Added deterministic memory IDs.
   - `create_memory_unit()` now derives IDs from stable memory content.
   - `created_at` and policy counters do not affect the ID.
2. Added `MemoryStore`.
   - Persists memory as JSONL.
   - Supports `load_all()`, `save_all()`, and `upsert()`.
   - Rewrites atomically to avoid partial JSONL writes.
3. Added validation-only evidence updates.
   - `update_validation_evidence()` accepts only `split="validation"`.
   - Attempts to update memory evidence from `test` raise an error.
4. Kept retrieval, scoring, and prompt insertion out of this increment. Those
   belong to Phase 1C.

### Tests added

- `test_memory_id_is_deterministic`
- `test_memory_store_persists_jsonl_and_updates_validation_only`

### Verification performed

Command executed from the HeurAgenix repository root with `PYTHONPATH=src`.

1. `python -m unittest discover -s tests/cmhh -v`
   - 14 tests passed.

## 2026-08-16 - Phase 1C control freeze

### Decision

Before implementing Phase 1C, freeze the H1b control as:

`naive_memory_sequential = population_carryover + naive external memory`.

This means the naive-memory condition must preserve the full Phase 1A behavior:

- task `k+1` is seeded from task `k`'s final ranked population;
- no fallback to a memory-only seed path should replace population carryover;
- the only experimental difference from `population_carryover` is that an
  uncurated external memory pool is written, retrieved, and inserted into the
  generation context.

### Rationale

H1b is defined as retrieval-side interference beyond population drift. If
`naive_memory_sequential` removed population carryover, any difference from H1
could come from either changed population transfer or memory retrieval. Keeping
carryover identical isolates the marginal effect of naive external memory.

## 2026-08-16 - Phase 1C naive external memory baseline

### Scope

Implemented the Phase 1C `naive_memory_sequential` condition.

The control freeze is enforced in code:

`naive_memory_sequential = population_carryover + naive external memory`.

The condition keeps task-to-task final-population carryover and adds an
uncurated memory pool as generation context. It does not replace carryover with
memory retrieval.

### Implemented

1. Extended the generator protocol with optional `memory_context`.
   - `BaselineGenerator` ignores it.
   - `HeurAgenixGenerator` snapshots retrieved memory to
     `memory_context.json`.
2. Added worker/evolver threading for memory context.
   - The worker formats retrieved memory units.
   - `HeuristicEvolver.evolve()` accepts `external_memory_context`.
   - The context is appended to heuristic-doc/context material used by the
     evolution prompts.
3. Added naive retrieval over `MemoryUnit`.
   - Retrieval scores by problem match, task-signature overlap, and
     applicability text.
   - Top-k default is 5.
4. Added naive memory writing in `StreamRunner`.
   - After validation ranking, all valid ranked candidates become uncurated
     memory units.
   - Memory value type is `trajectory` to reflect weak/no distillation.
   - Evidence includes source code path, code hash, and validation summary.
5. Added naive-overwrite capacity enforcement.
   - Default capacity is 20.
   - Evicts the lowest validation score first with deterministic tie breakers.
6. Added retrieval/memory events:
   - `memory_retrieved`
   - `memory_written`
   - `memory_evicted`
   - retrieval logs include memory IDs, ranks, scores, source tasks,
     duplicate-key rate, and whether the memory was used in generation.

### Tests added

- `test_naive_memory_preserves_carryover_and_retrieves_memory`
  verifies that the naive-memory condition keeps the ranked carryover
  population while also retrieving memory for the next task.

### Verification performed

Command executed from the HeurAgenix repository root with `PYTHONPATH=src`.

1. `python -m unittest discover -s tests/cmhh -v`
   - 15 tests passed.

## 2026-08-16 - Phase 1D memory diagnostics and experiment guide

### Scope

Completed the code-side Phase 1 diagnostics needed to audit H1b.

Phase 1 remains scientifically gated on real references, live HeurAgenix runs,
multi-seed reruns, and audit. The implementation now produces the artifacts
needed to run those gates without adding the Phase 2 Archivist.

### Implemented

1. Added `memory_diagnostics.py`.
   - Computes retrieval coverage.
   - Computes top-k concentration.
   - Computes duplicate-key rate summaries.
   - Computes source-task and memory-age distributions.
   - Computes post-reuse validation delta values.
   - Adds heuristic failure-mode labels for harmful reuse, ineffective reuse,
     retrieval pollution, context competition, memory dilution, and retrieval
     diversity collapse.
2. Added validation-only carryover baseline scoring for naive-memory runs.
   - The runner evaluates the carried-over seed population on the current
     validation task.
   - It compares that score with the selected post-generation candidate score.
   - Test results are not used for memory writing, retrieval scoring, candidate
     selection, stopping, or diagnostics.
3. Added `memory_reuse_outcome` events.
   - Logs retrieved memory IDs, selected validation score, carryover validation
     score, and post-reuse validation delta.
4. Added persisted diagnostics output.
   - Naive-memory runs now write `memory/diagnostics.json`.
5. Added the Phase 1 run guide.
   - `docs/cmhh/phase1_experiment_guide.md` documents config validation, data
     generation, reference generation, smoke runs, real H1/H1b runs, resume,
     multi-seed execution, audit, and artifact interpretation.

### Tests added

- Extended `test_naive_memory_preserves_carryover_and_retrieves_memory` to
  verify that naive-memory runs write `memory/diagnostics.json` with retrieval
  and validation-delta diagnostics.

### Verification performed

Commands executed from the HeurAgenix repository root with `PYTHONPATH=src`.

1. `python -m unittest discover -s tests/cmhh -v`
   - 15 tests passed.
2. `python -m compileall -q src/cmhh tests/cmhh`
   - passed.
3. `python -m cmhh.cli validate-config --experiment cmhh/configs/experiments/h1_isolated.yaml`
   - passed with expected pending-artifact/adapter warnings.
4. `python -m cmhh.cli validate-config --experiment cmhh/configs/experiments/h1_population_carryover.yaml`
   - passed with expected pending-artifact/adapter warnings.
5. `python -m cmhh.cli validate-config --experiment cmhh/configs/experiments/h1_naive_sequential.yaml`
   - passed with expected pending-artifact/adapter warnings.
6. `git diff --check -- HeurAgenix`
   - passed; Git only reported Windows CRLF/LF conversion warnings.

## 2026-08-29 - Managed Archivist condition wiring

### Scope

Started the Phase 2 transition from baseline-only memory experiments toward
full CM-HH managed memory.

This increment fixes the experiment semantics before adding heavier Archivist
features: the naive persistent-memory baseline no longer uses protected
Archivist behavior, and `archivist_managed` is now a first-class runnable
condition.

### Implemented

1. Added `NaiveMemoryManager`.
   - Admits all working-buffer experiences.
   - Uses raw trajectory-style memory content.
   - Applies no protection, no selective admission, no distillation, and no
     managed utility update.
   - Supports bounded overwrite and unbounded memory through the same archive
     capacity config.
2. Enabled `archivist_managed` / `managed_archivist` as valid experiment
   conditions.
3. Updated `StreamRunner`.
   - `naive_memory_sequential` uses `NaiveMemoryManager`.
   - `archivist_managed` uses `DefaultArchivist`.
   - Managed memory keeps the matched population-carryover behavior used by
     naive memory, so naive-vs-managed comparisons isolate memory management.
4. Implemented executable Stage A pre-learning probes.
   - Probes select retained competence from memory or compatible carryover.
   - Probes execute before learning the current task.
   - Probe scores are persisted to `pre_learning_scores.json`.
   - Forward transfer in `metrics.json` now uses Stage A probe scores rather
     than post-learning diagonal matrix cells.
5. Added learner-visible state hashing around Stage A and Stage C probes.
   - The invariant checks that probes do not mutate selected artifacts,
     carryover population, or persistent memory state.
6. Updated the TSP run script and watcher.
   - Managed Archivist runs are included by default.
   - `-SkipManaged` keeps the old baseline-only behavior.
   - Watcher prints `pre_learning_scores.json` when available.

### Tests added

- `test_naive_memory_does_not_protect_units`
- `test_archivist_managed_writes_protected_anchor`
- Extended the end-to-end stream test to assert Stage A scores and FWT source.

### Verification performed

Commands executed from the HeurAgenix repository root with `PYTHONPATH=src`.

1. `python -m unittest tests.cmhh.test_end_to_end_stream -v`
   - 3 tests passed.
2. `python -m unittest discover -s tests/cmhh -v`
   - 42 tests passed.
3. `python -m compileall -q src/cmhh tests/cmhh`
   - passed.
4. `python -m cmhh.cli validate-config --experiment cmhh/configs/experiments/archivist_managed.yaml --stream cmhh/configs/streams/tsp_size_ascending.yaml`
   - passed with expected OBP/PFSP warnings.

### Remaining Phase 2 work

1. Add a stronger managed distillation backend for `DefaultArchivist`.
2. Add exact/near-duplicate consolidation.
3. Add validation-only utility updates from reuse outcomes.
4. Add matched-capacity naive-vs-managed audit checks.
5. Add validation-oracle retrieval and controlled pollution diagnostics.
6. Run a real one-seed TSP managed Archivist pilot against naive bounded memory.
