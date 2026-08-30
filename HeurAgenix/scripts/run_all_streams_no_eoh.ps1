param(
    [object[]]$Seeds = @(1),
    [string]$LlmConfig = "cmhh/configs/llm/llm_config.local.json",
    [string]$RunPrefix = "",
    [object[]]$Streams = @(
        "tsp_size_ascending",
        "tsp_size_descending",
        "tsp_random_perm_1",
        "tsp_random_perm_2",
        "cvrp_size_ascending",
        "cvrp_size_descending",
        "jssp_size_ascending",
        "jssp_size_descending",
        "cross_problem_tsp_cvrp_jssp",
        "tsp_revisit",
        "tsp_stationary",
        "related_pair_tsp_cvrp_tsp",
        "unrelated_pair_tsp_jssp_tsp"
    ),
    [switch]$SkipReferences,
    [switch]$PrepareOnly,
    [switch]$Resume,
    [switch]$SkipManaged,
    [switch]$SkipIsolated,
    [switch]$SmokeOnly,
    [switch]$NoLLM,
    [switch]$QuickSmoke,
    [switch]$QuickTest,
    [switch]$FastSmoke,
    [switch]$HandoffSmoke,
    [switch]$Pilot,
    [switch]$AllStreams,
    [int]$OverrideGenerations = 0,
    [int]$OverrideCandidatesPerGeneration = 0,
    [int]$OverrideMaxLlmCalls = 0,
    [double]$EvolutionTimeoutSeconds = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Normalize Seeds
$cleanSeeds = @()
foreach ($s in $Seeds) {
    if ($s -is [string] -and $s -match ",") {
        $cleanSeeds += ($s -split "," | ForEach-Object { [int]$_.Trim() })
    } else {
        $cleanSeeds += [int]$s
    }
}
$Seeds = $cleanSeeds

# Normalize Streams
$cleanStreams = @()
foreach ($item in $Streams) {
    if ($item -is [string] -and $item -match ",") {
        $cleanStreams += ($item -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    } else {
        $cleanStreams += [string]$item
    }
}
$Streams = $cleanStreams


$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot
$env:PYTHONPATH = "src"

if (-not $RunPrefix) {
    $RunPrefix = "all_streams_no_eoh_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

$ResultsRoot = Join-Path $RepoRoot "cmhh/results"
New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
$DriverLog = Join-Path $ResultsRoot "${RunPrefix}_driver.log"
Start-Transcript -Path $DriverLog -Append | Out-Null

$isSmokeOnly = $SmokeOnly -or $NoLLM
$isQuick = $QuickSmoke -or $QuickTest -or $FastSmoke
$isPilot = $HandoffSmoke -or $Pilot

$Generator = if ($isSmokeOnly) { "baseline" } else { "heuragenix" }

$ModeName = "Full Benchmark (production budget)"
if ($isSmokeOnly) {
    $ModeName = "SmokeOnly (built-in baseline heuristics, 0 LLM calls, ~1-2 min total)"
    if ($OverrideGenerations -le 0) { $OverrideGenerations = 1 }
    if ($OverrideCandidatesPerGeneration -le 0) { $OverrideCandidatesPerGeneration = 1 }
    if ($OverrideMaxLlmCalls -le 0) { $OverrideMaxLlmCalls = 1 }
    if ($EvolutionTimeoutSeconds -le 0) { $EvolutionTimeoutSeconds = 60 }
}
elseif ($isQuick) {
    $ModeName = "QuickSmoke (minimal 1 gen / 2 LLM calls per task for ultra-fast verification)"
    if ($OverrideGenerations -le 0) { $OverrideGenerations = 1 }
    if ($OverrideCandidatesPerGeneration -le 0) { $OverrideCandidatesPerGeneration = 1 }
    if ($OverrideMaxLlmCalls -le 0) { $OverrideMaxLlmCalls = 2 }
    if ($EvolutionTimeoutSeconds -le 0) { $EvolutionTimeoutSeconds = 120 }
}
elseif ($isPilot) {
    $ModeName = "Pilot / HandoffSmoke (mini-pilot: 2 gens / 5 LLM calls per task)"
    if (-not $PSBoundParameters.ContainsKey("Streams") -and -not $AllStreams) {
        $Streams = @(
            "tsp_size_ascending",
            "cvrp_size_ascending",
            "jssp_size_ascending",
            "cross_problem_tsp_cvrp_jssp",
            "tsp_stationary"
        )
    }
    if ($OverrideGenerations -le 0) { $OverrideGenerations = 2 }
    if ($OverrideCandidatesPerGeneration -le 0) { $OverrideCandidatesPerGeneration = 1 }
    if ($OverrideMaxLlmCalls -le 0) { $OverrideMaxLlmCalls = 5 }
    if ($EvolutionTimeoutSeconds -le 0) { $EvolutionTimeoutSeconds = 300 }
}
else {
    if ($EvolutionTimeoutSeconds -le 0) { $EvolutionTimeoutSeconds = 21600 }
}

$ExperimentConfigs = @{
    Isolated = "cmhh/configs/experiments/h1_isolated.yaml"
    Population = "cmhh/configs/experiments/h1_population_carryover.yaml"
    NaiveBounded = "cmhh/configs/experiments/h1_naive_sequential.yaml"
    NaiveUnbounded = "cmhh/configs/experiments/h1_naive_unbounded.yaml"
    Managed = "cmhh/configs/experiments/archivist_managed.yaml"
}

function Set-YamlScalar {
    param(
        [string]$Content,
        [string]$Key,
        [int]$Value
    )
    return [regex]::Replace(
        $Content,
        "(?m)^(\s*$([regex]::Escape($Key)):\s*)\d+\s*$",
        { param($match) $match.Groups[1].Value + $Value }
    )
}

function New-ExperimentConfigCopies {
    param(
        [hashtable]$Configs,
        [int]$Generations,
        [int]$CandidatesPerGeneration,
        [int]$MaxLlmCalls
    )

    if ($Generations -le 0 -and $CandidatesPerGeneration -le 0 -and $MaxLlmCalls -le 0) {
        return $Configs
    }

    $overrideDir = Join-Path $ResultsRoot "${RunPrefix}_experiment_configs"
    New-Item -ItemType Directory -Force -Path $overrideDir | Out-Null
    $updated = @{}

    foreach ($key in $Configs.Keys) {
        $source = $Configs[$key]
        $content = Get-Content $source -Raw
        if ($Generations -gt 0) {
            $content = Set-YamlScalar $content "generations" $Generations
        }
        if ($CandidatesPerGeneration -gt 0) {
            $content = Set-YamlScalar $content "candidates_per_generation" $CandidatesPerGeneration
        }
        if ($MaxLlmCalls -gt 0) {
            $content = Set-YamlScalar $content "max_llm_calls" $MaxLlmCalls
        }

        $target = Join-Path $overrideDir (Split-Path $source -Leaf)
        Set-Content -Path $target -Value $content -Encoding UTF8
        $updated[$key] = $target
    }

    return $updated
}

function Stop-DriverTranscript {
    try {
        Stop-Transcript | Out-Null
    }
    catch {
        # Transcript may already be stopped after a terminating error.
    }
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
        [string]$Stream,
        [string]$RunId,
        [int]$Seed
    )

    $args = @(
        "run-isolated",
        "--experiment", $ExperimentConfigs.Isolated,
        "--stream", $Stream,
        "--generator", $Generator,
        "--run-id", $RunId,
        "--seed", "$Seed",
        "--evolution-timeout", "$EvolutionTimeoutSeconds",
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
        "--evolution-timeout", "$EvolutionTimeoutSeconds",
        "--no-wandb"
    )
    if ($ColdStartScores -and (Test-Path $ColdStartScores)) {
        $args += @("--cold-start-scores", $ColdStartScores)
    }
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

    Invoke-Cmhh @(
        "audit-run",
        "--experiment", $Experiment,
        "--stream", $Stream,
        "--run-id", $RunId
    )
}

try {
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "  CM-HH All-Streams Multi-Condition Experiment Runner" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "Repo        : $RepoRoot"
    Write-Host "Mode        : $ModeName"
    Write-Host "Generator   : $Generator"
    Write-Host "LLM config  : $(if ($Generator -eq 'baseline') { 'none (baseline)' } else { $LlmConfig })"
    Write-Host "Seeds       : $($Seeds -join ', ')"
    Write-Host "RunPrefix   : $RunPrefix"
    Write-Host "Driver log  : $DriverLog"
    Write-Host "Isolated    : $(if ($SkipIsolated) { 'skipped' } else { 'enabled' })"
    Write-Host "Managed     : $(if ($SkipManaged) { 'skipped' } else { 'enabled' })"
    Write-Host "References  : $(if ($SkipReferences) { 'skipped' } else { 'generate + verify' })"
    Write-Host "Streams ($($Streams.Count)): $($Streams -join ', ')"
    Write-Host "Budget      : generations=$OverrideGenerations, candidates_per_gen=$OverrideCandidatesPerGeneration, max_llm_calls=$OverrideMaxLlmCalls, timeout=${EvolutionTimeoutSeconds}s"
    Write-Host ""
    Write-Host "Monitor with:" -ForegroundColor Cyan
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\watch_phase1_tsp_run.ps1 -RunPrefix $RunPrefix"
    Write-Host ""

    if ($Generator -ne "baseline" -and -not (Test-Path $LlmConfig)) {
        throw "Missing LLM config: $LlmConfig"
    }

    $ExperimentConfigs = New-ExperimentConfigCopies `
        $ExperimentConfigs `
        $OverrideGenerations `
        $OverrideCandidatesPerGeneration `
        $OverrideMaxLlmCalls

    Write-Host "Experiment configs:"
    Write-Host "  isolated       : $($ExperimentConfigs.Isolated)"
    Write-Host "  population     : $($ExperimentConfigs.Population)"
    Write-Host "  naive bounded  : $($ExperimentConfigs.NaiveBounded)"
    Write-Host "  naive unbounded: $($ExperimentConfigs.NaiveUnbounded)"
    Write-Host "  managed        : $($ExperimentConfigs.Managed)"

    $summary = @()

    foreach ($streamId in $Streams) {
        $stream = "cmhh/configs/streams/$streamId.yaml"
        if (-not (Test-Path $stream)) {
            throw "Missing stream config: $stream"
        }

        Write-Host ""
        Write-Host "==========================================" -ForegroundColor Yellow
        Write-Host "=== Stream $streamId ===" -ForegroundColor Yellow
        Write-Host "==========================================" -ForegroundColor Yellow

        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.Isolated, "--stream", $stream)
        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.Population, "--stream", $stream)
        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.NaiveBounded, "--stream", $stream)
        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.NaiveUnbounded, "--stream", $stream)
        if (-not $SkipManaged) {
            Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.Managed, "--stream", $stream)
        }

        Invoke-Cmhh @("generate-data", "--experiment", $ExperimentConfigs.Isolated, "--stream", $stream, "--seed", "42")

        if (-not $SkipReferences) {
            Invoke-Cmhh @(
                "generate-references",
                "--experiment", $ExperimentConfigs.Isolated,
                "--stream", $stream,
                "--split", "validation",
                "--split", "test"
            )
            Invoke-Cmhh @(
                "verify-references",
                "--experiment", $ExperimentConfigs.Isolated,
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
            Write-Host "--- Stream $streamId / Seed $seed ---" -ForegroundColor Yellow

            $cold = "${RunPrefix}_${streamId}_${Generator}_cold_seed${seed}"
            $population = "${RunPrefix}_${streamId}_population_carryover_seed${seed}"
            $naiveBounded = "${RunPrefix}_${streamId}_naive_bounded_seed${seed}"
            $naiveUnbounded = "${RunPrefix}_${streamId}_naive_unbounded_seed${seed}"
            $managed = "${RunPrefix}_${streamId}_archivist_managed_seed${seed}"
            $coldStartScores = "cmhh/results/$cold/cold_start_scores.json"

            if (-not $SkipIsolated) {
                Run-Isolated $stream $cold $seed
                $summary += $cold
            } else {
                Write-Host "  Isolated cold run skipped (-SkipIsolated)" -ForegroundColor DarkGray
            }

            Run-Stream $ExperimentConfigs.Population $stream $population $seed $coldStartScores
            Run-Stream $ExperimentConfigs.NaiveBounded $stream $naiveBounded $seed $coldStartScores
            Run-Stream $ExperimentConfigs.NaiveUnbounded $stream $naiveUnbounded $seed $coldStartScores

            Audit-Run $ExperimentConfigs.Population $stream $population
            Audit-Run $ExperimentConfigs.NaiveBounded $stream $naiveBounded
            Audit-Run $ExperimentConfigs.NaiveUnbounded $stream $naiveUnbounded

            $summary += $population
            $summary += $naiveBounded
            $summary += $naiveUnbounded

            if (-not $SkipManaged) {
                Run-Stream $ExperimentConfigs.Managed $stream $managed $seed $coldStartScores
                Audit-Run $ExperimentConfigs.Managed $stream $managed
                $summary += $managed
            }
        }
    }

    if ($PrepareOnly) {
        Write-Host ""
        Write-Host "PrepareOnly complete. Data and references are ready." -ForegroundColor Green
        Stop-DriverTranscript
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
    Write-Host "  $DriverLog"
    Stop-DriverTranscript
}
catch {
    Write-Host ""
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Driver log: $DriverLog" -ForegroundColor Red
    Stop-DriverTranscript
    throw
}

