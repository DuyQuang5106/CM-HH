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
    -Stream "tsp_size_descending" `
    -Seeds $seedStr `
    $modeFlag `
    $resumeFlag
