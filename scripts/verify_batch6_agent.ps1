param(
    [switch]$NoStart,
    [switch]$SkipFullPythonTests
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Verifier = Join-Path $PSScriptRoot "verify_and_start.ps1"
if (-not (Test-Path $Verifier)) {
    throw "Shared verifier not found: $Verifier"
}

$Parameters = @{
    NewTest = @(
        "tests/test_backend_agent_tools.py"
    )
}

if ($NoStart) {
    $Parameters.NoStart = $true
}
if ($SkipFullPythonTests) {
    $Parameters.SkipFullPythonTests = $true
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " AITranslator Batch 6 Agent verification" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Checks the Agent tool contract, deterministic capability registry," -ForegroundColor DarkGray
Write-Host "side-effect boundaries, full project tests, frontend build, and Tauri." -ForegroundColor DarkGray
Write-Host ""

& $Verifier @Parameters
