param(
    [string]$Stream = "tsp_size_ascending",
    [object[]]$Seeds = @(1),
    [string]$LlmConfig = "cmhh/configs/llm/llm_config.local.json",
    [string]$RunPrefix = "",
    [object[]]$Conditions = @("isolated", "population", "naive-bounded", "naive-unbounded", "managed"),
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
    "--streams", $Stream,
    "--seeds", ($Seeds -join ","),
    "--conditions", ($Conditions -join ","),
    "--mode", $mode,
    "--llm-config", $LlmConfig
)

if ($RunPrefix) { $args += @("--run-prefix", $RunPrefix) }
if ($SkipReferences) { $args += "--skip-references" }
if ($PrepareOnly) { $args += "--prepare-only" }
if ($Resume) { $args += "--resume" }
if ($SkipManaged) { $args += "--skip-managed" }
if ($SkipIsolated) { $args += "--skip-isolated" }
if ($mode -eq "smoke") { $args += "--no-wandb" }

& uv run cmhh @args
exit $LASTEXITCODE
