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
    NewFrontendTest = @(
        "src/performance/entry-isolation.test.ts"
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
Write-Host " AITranslator Batch 5 performance verification" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Checks entry isolation, lazy workspace boundaries, clean frontend install," -ForegroundColor DarkGray
Write-Host "production chunking, Tauri compatibility, and optional dev startup." -ForegroundColor DarkGray
Write-Host ""

& $Verifier @Parameters
