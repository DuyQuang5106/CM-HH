param(
    [string]$RunPrefix = "",
    [int]$IntervalSeconds = 20,
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

function Get-LatestRunPrefix {
    $latest = Get-ChildItem "cmhh/results" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^(phase1_tsp_\d{8}_\d{6})_" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $latest) {
        throw "No phase1_tsp_* run directory found under cmhh/results"
    }
    return [regex]::Match($latest.Name, "^(phase1_tsp_\d{8}_\d{6})_").Groups[1].Value
}

function Show-RunStatus {
    param([string]$Prefix)

    Clear-Host
    Write-Host "CM-HH Phase 1 Watcher" -ForegroundColor Green
    Write-Host "Repo     : $RepoRoot"
    Write-Host "Prefix   : $Prefix"
    Write-Host "Updated  : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host ""

    $runs = Get-ChildItem "cmhh/results" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "$Prefix*" } |
        Sort-Object Name

    if (-not $runs) {
        Write-Host "No runs found for prefix $Prefix" -ForegroundColor Yellow
        return
    }

    foreach ($run in $runs) {
        $checkpointPath = Join-Path $run.FullName "checkpoints/latest.json"
        $matrixPath = Join-Path $run.FullName "performance_matrix.csv"
        $metricsPath = Join-Path $run.FullName "metrics.json"
        $preLearningPath = Join-Path $run.FullName "pre_learning_scores.json"
        $eventsPath = Join-Path $run.FullName "events.jsonl"
        $memoryDiagPath = Join-Path $run.FullName "memory/diagnostics.json"
        $latestChild = Get-ChildItem $run.FullName -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        $completed = "-"
        $currentTask = "-"
        if (Test-Path $checkpointPath) {
            $checkpoint = Get-Content $checkpointPath -Raw | ConvertFrom-Json
            $completed = [string]$checkpoint.completed_tasks
            $taskIds = @("tsp_n20_uniform", "tsp_n50_uniform", "tsp_n100_uniform", "tsp_n200_uniform")
            $idx = [int]$checkpoint.completed_tasks
            if ($idx -lt $taskIds.Count) {
                $currentTask = $taskIds[$idx]
            } else {
                $currentTask = "complete"
            }
        }

        $status = if (Test-Path $metricsPath) { "complete" } elseif (Test-Path $checkpointPath) { "running/partial" } else { "starting" }
        Write-Host $run.Name -ForegroundColor Cyan
        Write-Host "  status          : $status"
        Write-Host "  completed tasks : $completed / 4"
        Write-Host "  current task    : $currentTask"
        if ($latestChild) {
            Write-Host "  last file write : $($latestChild.LastWriteTime)"
        }

        if (Test-Path $matrixPath) {
            Write-Host "  performance_matrix.csv:"
            Get-Content $matrixPath | ForEach-Object { Write-Host "    $_" }
        }

        if (Test-Path $metricsPath) {
            Write-Host "  metrics.json:"
            Get-Content $metricsPath | ForEach-Object { Write-Host "    $_" }
        } elseif (Test-Path $eventsPath) {
            Write-Host "  latest events:"
            Get-Content $eventsPath -Tail 4 | ForEach-Object { Write-Host "    $_" }
        }

        if (Test-Path $preLearningPath) {
            Write-Host "  pre_learning_scores.json:"
            Get-Content $preLearningPath | ForEach-Object { Write-Host "    $_" }
        }

        if (Test-Path $memoryDiagPath) {
            Write-Host "  memory diagnostics: available"
        }

        $latestGeneratorLog = Get-ChildItem (Join-Path $run.FullName "generator") -Recurse -File -Filter "run_log.txt" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($latestGeneratorLog) {
            $relativeLog = $latestGeneratorLog.FullName.Replace($RepoRoot.Path + "\", "")
            Write-Host "  latest generator log: $relativeLog"
            Get-Content $latestGeneratorLog.FullName -Tail 8 | ForEach-Object { Write-Host "    $_" }
        }

        Write-Host ""
    }
}

if (-not $RunPrefix) {
    $RunPrefix = Get-LatestRunPrefix
}

do {
    Show-RunStatus $RunPrefix
    if ($Once) {
        break
    }
    Start-Sleep -Seconds $IntervalSeconds
} while ($true)
