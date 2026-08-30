param(
    [switch]$QuickSmoke,
    [switch]$SmokeOnly,
    [switch]$FullBenchmark
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

$predefinedStreams = @(
    @{ Id = 1; Name = "tsp_size_ascending"; Label = "TSP Size Ascending (n20 -> n50 -> n100 -> n200)"; SkipRef = $false },
    @{ Id = 2; Name = "tsp_size_descending"; Label = "TSP Size Descending (n200 -> n100 -> n50 -> n20)"; SkipRef = $false },
    @{ Id = 3; Name = "cvrp_size_ascending"; Label = "CVRP Size Ascending (n20 -> n50 -> n100)"; SkipRef = $true },
    @{ Id = 4; Name = "cvrp_size_descending"; Label = "CVRP Size Descending (n100 -> n50 -> n20)"; SkipRef = $true },
    @{ Id = 5; Name = "jssp_size_ascending"; Label = "JSSP Size Ascending (3x3 -> 6x6 -> 10x10)"; SkipRef = $true },
    @{ Id = 6; Name = "jssp_size_descending"; Label = "JSSP Size Descending (10x10 -> 6x6 -> 3x3)"; SkipRef = $true },
    @{ Id = 7; Name = "cross_problem_tsp_cvrp_jssp"; Label = "Cross-Domain Transfer (TSP -> CVRP -> JSSP)"; SkipRef = $true },
    @{ Id = 8; Name = "tsp_stationary"; Label = "TSP Stationary Control (n50 stationary)"; SkipRef = $false },
    @{ Id = 9; Name = "tsp_revisit"; Label = "TSP Revisit (n50 -> n100 -> n50 -> n200)"; SkipRef = $false },
    @{ Id = 10; Name = "related_pair_tsp_cvrp_tsp"; Label = "Related Pair (TSP -> CVRP -> TSP)"; SkipRef = $true },
    @{ Id = 11; Name = "unrelated_pair_tsp_jssp_tsp"; Label = "Unrelated Pair (TSP -> JSSP -> TSP)"; SkipRef = $true },
    @{ Id = 12; Name = "ALL_STREAMS"; Label = "ALL 13 STREAMS (Full Suite)"; SkipRef = $false }
)

Clear-Host
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "     CM-HH EXPERIMENT STREAM SELECTOR (MENU RUNNER)       " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Chon Stream ban muon chay:" -ForegroundColor Yellow

foreach ($item in $predefinedStreams) {
    $numStr = "[$($item.Id)]".PadRight(5)
    if ($item.Id -eq 12) {
        Write-Host ""
        Write-Host "  $numStr $($item.Label)" -ForegroundColor Magenta
    } else {
        Write-Host "  $numStr $($item.Label)" -ForegroundColor Cyan
    }
}
Write-Host "  [0]   Thoat" -ForegroundColor DarkGray
Write-Host ""

$choice = Read-Host "Nhap so Stream muon chay (1-12, hoac 0 de thoat)"
if ($choice -eq "0" -or [string]::IsNullOrWhiteSpace($choice)) {
    Write-Host "Da huy." -ForegroundColor Yellow
    exit 0
}

$selectedStream = $predefinedStreams | Where-Object { $_.Id -eq [int]$choice }
if (-not $selectedStream) {
    Write-Host "Lua chon khong hop le!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Chon Che Do Chay (Execution Mode):" -ForegroundColor Yellow
Write-Host "  [1] Quick Smoke Test (Test nhanh voi LLM, 1 the he / 2 LLM calls per task, ~2-5 phut) [Khuyen nghi]" -ForegroundColor Green
Write-Host "  [2] Zero-LLM Smoke   (Heuristic baseline, 0 LLM token, ~1 phut)" -ForegroundColor Cyan
Write-Host "  [3] Mini-Pilot       (2 the he / 5 LLM calls per task, ~10-15 phut)" -ForegroundColor Yellow
Write-Host "  [4] Full Benchmark   (100 the he / 500 LLM calls per task, Chay thuc nghiem chinh thuc)" -ForegroundColor Magenta
Write-Host ""

$modeChoice = Read-Host "Nhap che do (1-4, Enter = mac dinh 1)"
if ([string]::IsNullOrWhiteSpace($modeChoice)) {
    $modeChoice = "1"
}

$modeFlag = switch ($modeChoice) {
    "1" { "-QuickSmoke" }
    "2" { "-SmokeOnly" }
    "3" { "-Pilot" }
    "4" { "" }
    default { "-QuickSmoke" }
}

Write-Host ""
Write-Host "Dang khoi dong thuc nghiem cho: $($selectedStream.Label)..." -ForegroundColor Green
Write-Host ""

if ($selectedStream.Name -eq "ALL_STREAMS") {
    $cmd = "powershell -ExecutionPolicy Bypass -File scripts\run_all_streams_no_eoh.ps1 $modeFlag"
    Write-Host ">>> $cmd" -ForegroundColor Cyan
    Invoke-Expression $cmd
} else {
    $skipRefFlag = if ($selectedStream.SkipRef) { "-SkipReferences" } else { "" }
    $cmd = "powershell -ExecutionPolicy Bypass -File scripts\run_single_stream.ps1 -Stream $($selectedStream.Name) $modeFlag $skipRefFlag"
    Write-Host ">>> $cmd" -ForegroundColor Cyan
    Invoke-Expression $cmd
}
