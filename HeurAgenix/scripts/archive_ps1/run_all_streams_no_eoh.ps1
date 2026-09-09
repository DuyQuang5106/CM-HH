param(
    [object[]]$Seeds = @(1),
    [string]$LlmConfig = "cmhh/configs/llm/llm_config.local.json",
    [string]$RunPrefix = "",
    [object[]]$Streams = @(),
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
    [switch]$FullBenchmark
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $ProjectRoot

$mode = "quick-smoke"
if ($FullBenchmark) { $mode = "full" }
elseif ($SmokeOnly -or $NoLLM) { $mode = "smoke" }
elseif ($Pilot -or $HandoffSmoke) { $mode = "pilot" }
elseif ($QuickSmoke -or $QuickTest -or $FastSmoke) { $mode = "quick-smoke" }

$args = @(
    "run-suite",
    "--seeds", ($Seeds -join ","),
    "--mode", $mode,
    "--llm-config", $LlmConfig
)

if ($Streams.Count -gt 0) { $args += @("--streams", ($Streams -join ",")) }
if ($RunPrefix) { $args += @("--run-prefix", $RunPrefix) }
if ($SkipReferences) { $args += "--skip-references" }
if ($PrepareOnly) { $args += "--prepare-only" }
if ($Resume) { $args += "--resume" }
if ($SkipManaged) { $args += "--skip-managed" }
if ($SkipIsolated) { $args += "--skip-isolated" }
if ($AllStreams) { $args += "--all-streams" }
if ($mode -eq "smoke") { $args += "--no-wandb" }

& uv run cmhh @args
exit $LASTEXITCODE
