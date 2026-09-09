param(
    [object[]]$Seeds = @(1),
    [string]$LlmConfig = "cmhh/configs/llm/llm_config.local.json",
    [string]$Stream = "tsp_size_ascending",
    [string]$RunPrefix = "",
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

$args = @(
    "run-suite",
    "--streams", $Stream,
    "--seeds", ($Seeds -join ","),
    "--mode", "full",
    "--generator", "heuragenix",
    "--llm-config", $LlmConfig,
    "--eoh-evaluation-timeout", "$EohEvaluationTimeoutSeconds",
    "--evolution-timeout", "$EvolutionTimeoutSeconds"
)

if ($RunPrefix) { $args += @("--run-prefix", $RunPrefix) }
if ($SkipReferences) { $args += "--skip-references" }
if ($PrepareOnly) { $args += "--prepare-only" }
if ($Resume) { $args += "--resume" }
if ($SkipManaged) { $args += "--skip-managed" }
if (-not $SkipEOH) { $args += "--include-eoh" }

& uv run cmhh @args
exit $LASTEXITCODE
