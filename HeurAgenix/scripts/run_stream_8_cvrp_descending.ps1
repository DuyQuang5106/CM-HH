param([object[]]$Seeds = @(1), [object[]]$Conditions = @("isolated", "population", "naive-bounded", "naive-unbounded", "managed"), [switch]$FullBenchmark, [switch]$SmokeOnly, [switch]$Pilot, [switch]$Resume)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Resolve-Path (Join-Path $ScriptDir "..\.."))
$mode = "quick-smoke"
if ($FullBenchmark) { $mode = "full" } elseif ($SmokeOnly) { $mode = "smoke" } elseif ($Pilot) { $mode = "pilot" }
$args = @("run-suite", "--streams", "cvrp_size_descending", "--seeds", ($Seeds -join ","), "--conditions", ($Conditions -join ","), "--mode", $mode, "--skip-references")
if ($Resume) { $args += "--resume" }
if ($mode -eq "smoke") { $args += "--no-wandb" }
& uv run cmhh @args
exit $LASTEXITCODE
