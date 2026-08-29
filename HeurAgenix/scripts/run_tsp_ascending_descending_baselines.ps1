param(
    [int[]]$Seeds = @(1),
    [string]$LlmConfig = "cmhh/configs/llm/llm_config.local.json",
    [string]$RunPrefix = "",
    [switch]$SmokeOnly,
    [switch]$SkipReferences,
    [switch]$PrepareOnly,
    [switch]$Resume,
    [switch]$SkipEOH,
    [switch]$SkipManaged,
    [int]$EohEvaluationTimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot
$env:PYTHONPATH = "src"
$env:CMHH_EOH_EVALUATION_TIMEOUT_SECONDS = "$EohEvaluationTimeoutSeconds"

if (-not $RunPrefix) {
    $RunPrefix = "tsp_orders_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

$Streams = @(
    @{
        Label = "asc"
        Path = "cmhh/configs/streams/tsp_size_ascending.yaml"
    },
    @{
        Label = "desc"
        Path = "cmhh/configs/streams/tsp_size_descending.yaml"
    }
)

function Invoke-Cmhh {
    param([string[]]$Arguments)

    Write-Host ""
    Write-Host ">>> python -m cmhh.cli --repo-root . $($Arguments -join ' ')" -ForegroundColor Cyan
    & python -m cmhh.cli --repo-root . @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

function Run-Isolated {
    param(
        [string]$Experiment,
        [string]$Stream,
        [string]$Generator,
        [string]$RunId,
        [int]$Seed
    )

    $args = @(
        "run-isolated",
        "--experiment", $Experiment,
        "--stream", $Stream,
        "--generator", $Generator,
        "--run-id", $RunId,
        "--seed", "$Seed",
        "--no-wandb"
    )
    if ($Generator -ne "baseline") {
        $args += @("--llm-config", $LlmConfig)
    }
    Invoke-Cmhh $args
}

function Run-Stream {
    param(
        [string]$Experiment,
        [string]$Stream,
        [string]$Generator,
        [string]$RunId,
        [int]$Seed,
        [string]$ColdStartScores
    )

    $args = @(
        "run-stream",
        "--experiment", $Experiment,
        "--stream", $Stream,
        "--generator", $Generator,
        "--run-id", $RunId,
        "--seed", "$Seed",
        "--cold-start-scores", $ColdStartScores,
        "--no-wandb"
    )
    if ($Generator -ne "baseline") {
        $args += @("--llm-config", $LlmConfig)
    }
    if ($Resume) {
        $args += "--resume"
    }
    Invoke-Cmhh $args
}

function Audit-Run {
    param(
        [string]$Experiment,
        [string]$Stream,
        [string]$RunId
    )
    Invoke-Cmhh @("audit-run", "--experiment", $Experiment, "--stream", $Stream, "--run-id", $RunId)
}

$Generator = if ($SmokeOnly) { "baseline" } else { "heuragenix" }
$EffectiveSkipEOH = $SkipEOH -or $SmokeOnly

Write-Host "CM-HH TSP ascending/descending baseline run" -ForegroundColor Green
Write-Host "Repo      : $RepoRoot"
Write-Host "Seeds     : $($Seeds -join ', ')"
Write-Host "RunPrefix : $RunPrefix"
Write-Host "Mode      : $(if ($SmokeOnly) { 'SmokeOnly: built-in baseline generator, no LLM calls' } else { 'Full: HeurAgenix plus optional EOH' })"
Write-Host "EOH       : $(if ($EffectiveSkipEOH) { 'skipped' } else { 'enabled' })"
Write-Host "Managed   : $(if ($SkipManaged) { 'skipped' } else { 'enabled' })"
Write-Host ""
Write-Host "Monitor with:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1 -RunPrefix $RunPrefix"

if (-not $SmokeOnly -and -not (Test-Path $LlmConfig)) {
    throw "Missing LLM config: $LlmConfig"
}

$summary = @()

foreach ($streamSpec in $Streams) {
    $label = $streamSpec.Label
    $stream = $streamSpec.Path

    Write-Host ""
    Write-Host "=== Stream ${label}: $stream ===" -ForegroundColor Yellow

    Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/h1_isolated.yaml", "--stream", $stream)
    Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/h1_population_carryover.yaml", "--stream", $stream)
    Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/h1_naive_sequential.yaml", "--stream", $stream)
    Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/h1_naive_unbounded.yaml", "--stream", $stream)
    if (-not $SkipManaged) {
        Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/archivist_managed.yaml", "--stream", $stream)
    }
    if (-not $EffectiveSkipEOH) {
        Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/eoh_cold_start.yaml", "--stream", $stream)
    }

    Invoke-Cmhh @("generate-data", "--experiment", "cmhh/configs/experiments/h1_isolated.yaml", "--stream", $stream, "--seed", "42")

    if (-not $SkipReferences) {
        Invoke-Cmhh @(
            "generate-references",
            "--experiment", "cmhh/configs/experiments/h1_isolated.yaml",
            "--stream", $stream,
            "--split", "validation",
            "--split", "test"
        )
        Invoke-Cmhh @(
            "verify-references",
            "--experiment", "cmhh/configs/experiments/h1_isolated.yaml",
            "--stream", $stream,
            "--split", "validation",
            "--split", "test"
        )
    }

    if ($PrepareOnly) {
        continue
    }

    foreach ($seed in $Seeds) {
        Write-Host ""
        Write-Host "--- Stream $label / Seed $seed ---" -ForegroundColor Yellow

        $cold = "${RunPrefix}_${label}_${Generator}_cold_seed${seed}"
        $population = "${RunPrefix}_${label}_population_carryover_seed${seed}"
        $naiveBounded = "${RunPrefix}_${label}_naive_bounded_seed${seed}"
        $naiveUnbounded = "${RunPrefix}_${label}_naive_unbounded_seed${seed}"
        $managed = "${RunPrefix}_${label}_archivist_managed_seed${seed}"
        $coldStartScores = "cmhh/results/$cold/cold_start_scores.json"

        if (-not $EffectiveSkipEOH) {
            $eohCold = "${RunPrefix}_${label}_eoh_cold_seed${seed}"
            Run-Isolated "cmhh/configs/experiments/eoh_cold_start.yaml" $stream "eoh" $eohCold $seed
            $summary += $eohCold
        }

        Run-Isolated "cmhh/configs/experiments/h1_isolated.yaml" $stream $Generator $cold $seed
        Run-Stream "cmhh/configs/experiments/h1_population_carryover.yaml" $stream $Generator $population $seed $coldStartScores
        Run-Stream "cmhh/configs/experiments/h1_naive_sequential.yaml" $stream $Generator $naiveBounded $seed $coldStartScores
        Run-Stream "cmhh/configs/experiments/h1_naive_unbounded.yaml" $stream $Generator $naiveUnbounded $seed $coldStartScores
        if (-not $SkipManaged) {
            Run-Stream "cmhh/configs/experiments/archivist_managed.yaml" $stream $Generator $managed $seed $coldStartScores
        }

        Audit-Run "cmhh/configs/experiments/h1_population_carryover.yaml" $stream $population
        Audit-Run "cmhh/configs/experiments/h1_naive_sequential.yaml" $stream $naiveBounded
        Audit-Run "cmhh/configs/experiments/h1_naive_unbounded.yaml" $stream $naiveUnbounded
        if (-not $SkipManaged) {
            Audit-Run "cmhh/configs/experiments/archivist_managed.yaml" $stream $managed
        }

        $summary += $cold
        $summary += $population
        $summary += $naiveBounded
        $summary += $naiveUnbounded
        if (-not $SkipManaged) {
            $summary += $managed
        }
    }
}

if ($PrepareOnly) {
    Write-Host ""
    Write-Host "PrepareOnly complete for ascending and descending streams." -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "Completed runs:" -ForegroundColor Green
foreach ($runId in $summary) {
    Write-Host "  cmhh/results/$runId"
}

Write-Host ""
Write-Host "Report files to inspect:" -ForegroundColor Green
Write-Host "  cmhh/results/<run-id>/metrics.json"
Write-Host "  cmhh/results/<run-id>/performance_matrix.csv"
Write-Host "  cmhh/results/<run-id>/pre_learning_scores.json"
Write-Host "  cmhh/results/<run-id>/memory/diagnostics.json"
