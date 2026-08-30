param(
    [object[]]$Seeds = @(1),
    [switch]$FullBenchmark,
    [switch]$SmokeOnly,
    [switch]$Pilot,
    [switch]$Resume
)

$modeFlag = "-QuickSmoke"
if ($FullBenchmark) { $modeFlag = "" }
elseif ($SmokeOnly) { $modeFlag = "-SmokeOnly" }
elseif ($Pilot) { $modeFlag = "-Pilot" }

$resumeFlag = if ($Resume) { "-Resume" } else { "" }
$seedStr = $Seeds -join ","

powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run_single_stream.ps1") `
    -Stream "cross_problem_tsp_cvrp_jssp" `
    -Seeds $seedStr `
    -SkipReferences `
    $modeFlag `
    $resumeFlag
