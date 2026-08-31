param([object[]]$Seeds = @(1), [switch]$FullBenchmark, [switch]$SmokeOnly, [switch]$Pilot, [switch]$Resume)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Resolve-Path (Join-Path $ScriptDir "..\.."))
$mode = "quick-smoke"
if ($FullBenchmark) { $mode = "full" } elseif ($SmokeOnly) { $mode = "smoke" } elseif ($Pilot) { $mode = "pilot" }
$args = @("run-suite", "--streams", "tsp_revisit", "--seeds", ($Seeds -join ","), "--mode", $mode)
if ($Resume) { $args += "--resume" }
if ($mode -eq "smoke") { $args += "--no-wandb" }
& uv run cmhh @args
exit $LASTEXITCODE
