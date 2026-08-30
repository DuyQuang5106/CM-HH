param(
    [object[]]$Seeds = @(1),
    [object[]]$Conditions = @("Isolated", "Population", "NaiveBounded", "NaiveUnbounded", "Managed"),
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
$condStr = $Conditions -join ","

powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "run_single_stream.ps1") `
    -Stream "cvrp_size_descending" `
    -Seeds $seedStr `
    -Conditions $condStr `
    -SkipReferences `
    $modeFlag `
    $resumeFlag
