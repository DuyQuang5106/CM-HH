param(
    [string]$Stream = "tsp_size_ascending",
    [object[]]$Seeds = @(1),
    [string]$LlmConfig = "cmhh/configs/llm/llm_config.local.json",
    [string]$RunPrefix = "",
    [object[]]$Conditions = @("Isolated", "Population", "NaiveBounded", "NaiveUnbounded", "Managed"),
    [switch]$ListStreams,
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
    [switch]$Pilot,
    [switch]$HandoffSmoke,
    [int]$OverrideGenerations = 0,
    [int]$OverrideCandidatesPerGeneration = 0,
    [int]$OverrideMaxLlmCalls = 0,
    [double]$EvolutionTimeoutSeconds = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot
$env:PYTHONPATH = "src"

$StreamsDir = Join-Path $RepoRoot "cmhh/configs/streams"

# Feature: List all available streams
if ($ListStreams) {
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "  Available CM-HH Stream Configurations" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    $yamlFiles = Get-ChildItem $StreamsDir -Filter "*.yaml" | Sort-Object Name
    foreach ($file in $yamlFiles) {
        $name = $file.BaseName
        $content = Get-Content $file.FullName -Raw
        $tasksMatch = [regex]::Match($content, "(?ms)tasks:\s*(.+?)(?:^\S|\Z)")
        $tasksStr = ""
        if ($tasksMatch.Success) {
            $taskLines = $tasksMatch.Groups[1].Value.Trim() -split "`r?`n" | ForEach-Object {
                if ($_ -match "-\s*task_id:\s*(.+)") { $matches[1].Trim() }
                elseif ($_ -match "-\s*([a-zA-Z0-9_]+)") { $matches[1].Trim() }
            } | Where-Object { $_ }
            $tasksStr = " (" + ($taskLines -join ", ") + ")"
        }
        Write-Host ("  - " + $name.PadRight(32)) -ForegroundColor Cyan -NoNewline
        Write-Host $tasksStr -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "Usage example:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run_single_stream.ps1 -Stream tsp_size_ascending -QuickSmoke"
    exit 0
}

# Resolve stream path
$resolvedStreamPath = $Stream
if (-not (Test-Path $resolvedStreamPath)) {
    $candidate1 = Join-Path $StreamsDir "$Stream.yaml"
    $candidate2 = Join-Path $StreamsDir $Stream
    if (Test-Path $candidate1) {
        $resolvedStreamPath = $candidate1
    } elseif (Test-Path $candidate2) {
        $resolvedStreamPath = $candidate2
    } else {
        throw "Cannot find stream config: $Stream. Run with -ListStreams to see all options."
    }
}
$StreamId = [System.IO.Path]::GetFileNameWithoutExtension($resolvedStreamPath)

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

# Normalize Conditions
$cleanConditions = @()
foreach ($c in $Conditions) {
    if ($c -is [string] -and $c -match ",") {
        $cleanConditions += ($c -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    } else {
        $cleanConditions += [string]$c
    }
}
$Conditions = $cleanConditions

$isSmokeOnly = $SmokeOnly -or $NoLLM
$isQuick = $QuickSmoke -or $QuickTest -or $FastSmoke
$isPilot = $HandoffSmoke -or $Pilot

$Generator = if ($isSmokeOnly) { "baseline" } else { "heuragenix" }

$ModeName = "Full Benchmark (production budget: 100 gens, 500 LLM calls)"
if ($isSmokeOnly) {
    $ModeName = "SmokeOnly (built-in baseline heuristics, 0 LLM calls)"
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
    if ($OverrideGenerations -le 0) { $OverrideGenerations = 2 }
    if ($OverrideCandidatesPerGeneration -le 0) { $OverrideCandidatesPerGeneration = 1 }
    if ($OverrideMaxLlmCalls -le 0) { $OverrideMaxLlmCalls = 5 }
    if ($EvolutionTimeoutSeconds -le 0) { $EvolutionTimeoutSeconds = 300 }
}
else {
    if ($EvolutionTimeoutSeconds -le 0) { $EvolutionTimeoutSeconds = 21600 }
}

if (-not $RunPrefix) {
    $RunPrefix = "${StreamId}_" + (Get-Date -Format "yyyyMMdd_HHmmss")
}

$ResultsRoot = Join-Path $RepoRoot "cmhh/results"
New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
$DriverLog = Join-Path $ResultsRoot "${RunPrefix}_driver.log"
Start-Transcript -Path $DriverLog -Append | Out-Null

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
        [string]$StreamFile,
        [string]$RunId,
        [int]$Seed
    )

    $args = @(
        "run-isolated",
        "--experiment", $ExperimentConfigs.Isolated,
        "--stream", $StreamFile,
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
        [string]$StreamFile,
        [string]$RunId,
        [int]$Seed,
        [string]$ColdStartScores
    )

    $args = @(
        "run-stream",
        "--experiment", $Experiment,
        "--stream", $StreamFile,
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
        [string]$StreamFile,
        [string]$RunId
    )

    Invoke-Cmhh @(
        "audit-run",
        "--experiment", $Experiment,
        "--stream", $StreamFile,
        "--run-id", $RunId
    )
}

try {
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "  CM-HH Single Stream Runner" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "Repo        : $RepoRoot"
    Write-Host "Stream      : $StreamId ($resolvedStreamPath)"
    Write-Host "Mode        : $ModeName"
    Write-Host "Generator   : $Generator"
    Write-Host "LLM config  : $(if ($Generator -eq 'baseline') { 'none (baseline)' } else { $LlmConfig })"
    Write-Host "Seeds       : $($Seeds -join ', ')"
    Write-Host "RunPrefix   : $RunPrefix"
    Write-Host "Driver log  : $DriverLog"
    Write-Host "Conditions  : $($Conditions -join ', ')"
    Write-Host "References  : $(if ($SkipReferences) { 'skipped' } else { 'generate + verify' })"
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

    Write-Host "=== Validating & Preparing Stream $StreamId ===" -ForegroundColor Yellow

    if ($Conditions -contains "Isolated") {
        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.Isolated, "--stream", $resolvedStreamPath)
    }
    if ($Conditions -contains "Population") {
        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.Population, "--stream", $resolvedStreamPath)
    }
    if ($Conditions -contains "NaiveBounded") {
        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.NaiveBounded, "--stream", $resolvedStreamPath)
    }
    if ($Conditions -contains "NaiveUnbounded") {
        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.NaiveUnbounded, "--stream", $resolvedStreamPath)
    }
    if ($Conditions -contains "Managed" -and -not $SkipManaged) {
        Invoke-Cmhh @("validate-config", "--experiment", $ExperimentConfigs.Managed, "--stream", $resolvedStreamPath)
    }

    Invoke-Cmhh @("generate-data", "--experiment", $ExperimentConfigs.Isolated, "--stream", $resolvedStreamPath, "--seed", "42")

    if (-not $SkipReferences) {
        Invoke-Cmhh @(
            "generate-references",
            "--experiment", $ExperimentConfigs.Isolated,
            "--stream", $resolvedStreamPath,
            "--split", "validation",
            "--split", "test"
        )
        Invoke-Cmhh @(
            "verify-references",
            "--experiment", $ExperimentConfigs.Isolated,
            "--stream", $resolvedStreamPath,
            "--split", "validation",
            "--split", "test"
        )
    }

    if ($PrepareOnly) {
        Write-Host ""
        Write-Host "PrepareOnly complete. Data and references are ready for $StreamId." -ForegroundColor Green
        Stop-DriverTranscript
        exit 0
    }

    $summary = @()

    foreach ($seed in $Seeds) {
        Write-Host ""
        Write-Host "--- Stream $StreamId / Seed $seed ---" -ForegroundColor Yellow

        $cold = "${RunPrefix}_${Generator}_cold_seed${seed}"
        $population = "${RunPrefix}_population_carryover_seed${seed}"
        $naiveBounded = "${RunPrefix}_naive_bounded_seed${seed}"
        $naiveUnbounded = "${RunPrefix}_naive_unbounded_seed${seed}"
        $managed = "${RunPrefix}_archivist_managed_seed${seed}"
        $coldStartScores = "cmhh/results/$cold/cold_start_scores.json"

        # Condition 1: Isolated Cold Start
        if ($Conditions -contains "Isolated" -and -not $SkipIsolated) {
            Write-Host ""
            Write-Host ">>> Running Isolated Cold Start..." -ForegroundColor Yellow
            Run-Isolated $resolvedStreamPath $cold $seed
            $summary += $cold
        }

        # Condition 2: Population Carryover
        if ($Conditions -contains "Population") {
            Write-Host ""
            Write-Host ">>> Running Population Carryover..." -ForegroundColor Yellow
            Run-Stream $ExperimentConfigs.Population $resolvedStreamPath $population $seed $coldStartScores
            Audit-Run $ExperimentConfigs.Population $resolvedStreamPath $population
            $summary += $population
        }

        # Condition 3: Naive Bounded Memory
        if ($Conditions -contains "NaiveBounded") {
            Write-Host ""
            Write-Host ">>> Running Naive Bounded Memory..." -ForegroundColor Yellow
            Run-Stream $ExperimentConfigs.NaiveBounded $resolvedStreamPath $naiveBounded $seed $coldStartScores
            Audit-Run $ExperimentConfigs.NaiveBounded $resolvedStreamPath $naiveBounded
            $summary += $naiveBounded
        }

        # Condition 4: Naive Unbounded Memory
        if ($Conditions -contains "NaiveUnbounded") {
            Write-Host ""
            Write-Host ">>> Running Naive Unbounded Memory..." -ForegroundColor Yellow
            Run-Stream $ExperimentConfigs.NaiveUnbounded $resolvedStreamPath $naiveUnbounded $seed $coldStartScores
            Audit-Run $ExperimentConfigs.NaiveUnbounded $resolvedStreamPath $naiveUnbounded
            $summary += $naiveUnbounded
        }

        # Condition 5: Managed Archivist (CM-HH)
        if ($Conditions -contains "Managed" -and -not $SkipManaged) {
            Write-Host ""
            Write-Host ">>> Running Managed Archivist (CM-HH)..." -ForegroundColor Yellow
            Run-Stream $ExperimentConfigs.Managed $resolvedStreamPath $managed $seed $coldStartScores
            Audit-Run $ExperimentConfigs.Managed $resolvedStreamPath $managed
            $summary += $managed
        }
    }

    Write-Host ""
    Write-Host "Completed runs for ${StreamId}:" -ForegroundColor Green
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
