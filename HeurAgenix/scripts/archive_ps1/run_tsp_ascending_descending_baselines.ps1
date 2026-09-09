param(
    [object[]]$Seeds = @(1),
    [string]$LlmConfig = "cmhh/configs/llm/llm_config.local.json",
    [string]$RunPrefix = "",
    [switch]$SmokeOnly,
    [switch]$SkipReferences,
    [switch]$PrepareOnly,
    [switch]$Resume,
    [switch]$SkipEOH,
    [switch]$SkipManaged,
    [int]$EohEvaluationTimeoutSeconds = 180,
    [double]$EvolutionTimeoutSeconds = 21600
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Set-Location $ProjectRoot

$mode = if ($SmokeOnly) { "smoke" } else { "full" }
$generator = if ($SmokeOnly) { "baseline" } else { "heuragenix" }

$args = @(
    "run-suite",
    "--streams", "tsp_size_ascending,tsp_size_descending",
    "--seeds", ($Seeds -join ","),
    "--mode", $mode,
    "--generator", $generator,
    "--llm-config", $LlmConfig,
    "--eoh-evaluation-timeout", "$EohEvaluationTimeoutSeconds",
    "--evolution-timeout", "$EvolutionTimeoutSeconds"
)

if ($RunPrefix) { $args += @("--run-prefix", $RunPrefix) }
if ($SkipReferences) { $args += "--skip-references" }
if ($PrepareOnly) { $args += "--prepare-only" }
if ($Resume) { $args += "--resume" }
if ($SkipManaged) { $args += "--skip-managed" }
if (-not $SkipEOH -and -not $SmokeOnly) { $args += "--include-eoh" }
if ($SmokeOnly) { $args += "--no-wandb" }

& uv run cmhh @args
exit $LASTEXITCODE
