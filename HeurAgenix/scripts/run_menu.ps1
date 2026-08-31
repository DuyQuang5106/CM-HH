param(
    [switch]$QuickSmoke,
    [switch]$SmokeOnly,
    [switch]$FullBenchmark
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $ProjectRoot

$predefinedStreams = @(
    @{ Id = 1; Name = "tsp_size_ascending"; Label = "TSP Size Ascending (n20 -> n50 -> n100 -> n200)"; SkipRef = $false },
    @{ Id = 2; Name = "tsp_size_descending"; Label = "TSP Size Descending (n200 -> n100 -> n50 -> n20)"; SkipRef = $false },
    @{ Id = 3; Name = "cvrp_size_ascending"; Label = "CVRP Size Ascending (n20 -> n50 -> n100)"; SkipRef = $true },
    @{ Id = 4; Name = "cvrp_size_descending"; Label = "CVRP Size Descending (n100 -> n50 -> n20)"; SkipRef = $true },
    @{ Id = 5; Name = "jssp_size_ascending"; Label = "JSSP Size Ascending"; SkipRef = $true },
    @{ Id = 6; Name = "jssp_size_descending"; Label = "JSSP Size Descending"; SkipRef = $true },
    @{ Id = 7; Name = "cross_problem_tsp_cvrp_jssp"; Label = "Cross-Problem Transfer (TSP -> CVRP -> JSSP)"; SkipRef = $true },
    @{ Id = 8; Name = "tsp_stationary"; Label = "TSP Stationary Control"; SkipRef = $false },
    @{ Id = 9; Name = "tsp_revisit"; Label = "TSP Revisit"; SkipRef = $false },
    @{ Id = 10; Name = "related_pair_tsp_cvrp_tsp"; Label = "Related Pair (TSP -> CVRP -> TSP)"; SkipRef = $true },
    @{ Id = 11; Name = "unrelated_pair_tsp_jssp_tsp"; Label = "Unrelated Pair (TSP -> JSSP -> TSP)"; SkipRef = $true },
    @{ Id = 12; Name = "ALL_STREAMS"; Label = "All streams"; SkipRef = $false }
)

Write-Host "CM-HH experiment stream selector" -ForegroundColor Green
Write-Host ""
foreach ($item in $predefinedStreams) {
    Write-Host ("  [{0}] {1}" -f $item.Id, $item.Label)
}
Write-Host "  [0] Exit"
Write-Host ""

$choice = Read-Host "Select stream"
if ($choice -eq "0" -or [string]::IsNullOrWhiteSpace($choice)) {
    exit 0
}

$selectedStream = $predefinedStreams | Where-Object { $_.Id -eq [int]$choice }
if (-not $selectedStream) {
    Write-Host "Invalid choice." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Execution mode:"
Write-Host "  [1] quick-smoke"
Write-Host "  [2] smoke"
Write-Host "  [3] pilot"
Write-Host "  [4] full"
$modeChoice = Read-Host "Select mode"
if ([string]::IsNullOrWhiteSpace($modeChoice)) {
    $modeChoice = "1"
}

$mode = switch ($modeChoice) {
    "2" { "smoke" }
    "3" { "pilot" }
    "4" { "full" }
    default { "quick-smoke" }
}
if ($SmokeOnly) { $mode = "smoke" }
elseif ($FullBenchmark) { $mode = "full" }
elseif ($QuickSmoke) { $mode = "quick-smoke" }

$args = @("run-suite", "--mode", $mode)
if ($selectedStream.Name -eq "ALL_STREAMS") {
    $args += "--all-streams"
} else {
    $args += @("--streams", $selectedStream.Name)
    if ($selectedStream.SkipRef) {
        $args += "--skip-references"
    }
}
if ($mode -eq "smoke") {
    $args += "--no-wandb"
}

& uv run cmhh @args
exit $LASTEXITCODE
