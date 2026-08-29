param(
    [int[]]$Seeds = @(1),
    [string]$LlmConfig = "cmhh/configs/llm/llm_config.local.json",
    [string]$Stream = "cmhh/configs/streams/tsp_size_ascending.yaml",
    [string]$RunPrefix = "",
    [switch]$SkipReferences,
    [switch]$PrepareOnly,
    [switch]$Resume,
    [switch]$SkipEOH,
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
    $RunPrefix = "phase1_tsp_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

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
        [string]$Generator,
        [string]$RunId,
        [int]$Seed
    )

    $args = @(
        "run-isolated",
        "--experiment", $Experiment,
        "--stream", $Stream,
        "--generator", $Generator,
        "--llm-config", $LlmConfig,
        "--run-id", $RunId,
        "--seed", "$Seed",
        "--no-wandb"
    )
    Invoke-Cmhh $args
}

function Run-Stream {
    param(
        [string]$Experiment,
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
        "--llm-config", $LlmConfig,
        "--run-id", $RunId,
        "--seed", "$Seed",
        "--cold-start-scores", $ColdStartScores,
        "--no-wandb"
    )
    if ($Resume) {
        $args += "--resume"
    }
    Invoke-Cmhh $args
}

Write-Host "CM-HH Phase 1 TSP size-ascending experiment" -ForegroundColor Green
Write-Host "Repo      : $RepoRoot"
Write-Host "Stream    : $Stream"
Write-Host "LLM config: $LlmConfig"
Write-Host "Seeds     : $($Seeds -join ', ')"
Write-Host "RunPrefix : $RunPrefix"
Write-Host "EOH eval timeout: ${EohEvaluationTimeoutSeconds}s"
Write-Host ""
Write-Host "Open another PowerShell to monitor progress:" -ForegroundColor Green
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1 -RunPrefix $RunPrefix"

if (-not (Test-Path $LlmConfig)) {
    throw "Missing LLM config: $LlmConfig"
}

Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/h1_isolated.yaml", "--stream", $Stream)
Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/h1_population_carryover.yaml", "--stream", $Stream)
Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/h1_naive_sequential.yaml", "--stream", $Stream)
Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/h1_naive_unbounded.yaml", "--stream", $Stream)
if (-not $SkipEOH) {
    Invoke-Cmhh @("validate-config", "--experiment", "cmhh/configs/experiments/eoh_cold_start.yaml", "--stream", $Stream)
}

Invoke-Cmhh @("generate-data", "--experiment", "cmhh/configs/experiments/h1_isolated.yaml", "--stream", $Stream, "--seed", "42")

if (-not $SkipReferences) {
    Invoke-Cmhh @(
        "generate-references",
        "--experiment", "cmhh/configs/experiments/h1_isolated.yaml",
        "--stream", $Stream,
        "--split", "validation",
        "--split", "test"
    )
    Invoke-Cmhh @(
        "verify-references",
        "--experiment", "cmhh/configs/experiments/h1_isolated.yaml",
        "--stream", $Stream,
        "--split", "validation",
        "--split", "test"
    )
}

if ($PrepareOnly) {
    Write-Host ""
    Write-Host "PrepareOnly complete. Data/references are ready." -ForegroundColor Green
    exit 0
}

$summary = @()

foreach ($seed in $Seeds) {
    Write-Host ""
    Write-Host "=== Seed $seed ===" -ForegroundColor Yellow

    $hxCold = "${RunPrefix}_heuragenix_cold_seed${seed}"
    $population = "${RunPrefix}_population_carryover_seed${seed}"
    $naiveBounded = "${RunPrefix}_naive_bounded_seed${seed}"
    $naiveUnbounded = "${RunPrefix}_naive_unbounded_seed${seed}"
    $coldStartScores = "cmhh/results/$hxCold/cold_start_scores.json"

    if (-not $SkipEOH) {
        $eohCold = "${RunPrefix}_eoh_cold_seed${seed}"
        Run-Isolated "cmhh/configs/experiments/eoh_cold_start.yaml" "eoh" $eohCold $seed
        $summary += $eohCold
    }

    Run-Isolated "cmhh/configs/experiments/h1_isolated.yaml" "heuragenix" $hxCold $seed
    Run-Stream "cmhh/configs/experiments/h1_population_carryover.yaml" "heuragenix" $population $seed $coldStartScores
    Run-Stream "cmhh/configs/experiments/h1_naive_sequential.yaml" "heuragenix" $naiveBounded $seed $coldStartScores
    Run-Stream "cmhh/configs/experiments/h1_naive_unbounded.yaml" "heuragenix" $naiveUnbounded $seed $coldStartScores

    Invoke-Cmhh @("audit-run", "--experiment", "cmhh/configs/experiments/h1_population_carryover.yaml", "--stream", $Stream, "--run-id", $population)
    Invoke-Cmhh @("audit-run", "--experiment", "cmhh/configs/experiments/h1_naive_sequential.yaml", "--stream", $Stream, "--run-id", $naiveBounded)
    Invoke-Cmhh @("audit-run", "--experiment", "cmhh/configs/experiments/h1_naive_unbounded.yaml", "--stream", $Stream, "--run-id", $naiveUnbounded)

    $summary += $hxCold
    $summary += $population
    $summary += $naiveBounded
    $summary += $naiveUnbounded
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
Write-Host "  cmhh/results/<run-id>/memory/diagnostics.json"
