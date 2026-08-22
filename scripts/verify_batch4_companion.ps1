param(
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Verifier = Join-Path $PSScriptRoot "verify_and_start.ps1"
if (-not (Test-Path $Verifier)) {
    throw "Shared verifier not found: $Verifier"
}

$Parameters = @{
    NewTest = @(
        "tests/test_backend_companion.py",
        "tests/test_backend_companion_stream.py",
        "tests/test_backend_companion_ownership.py",
        "tests/test_companion_runtime_integration.py",
        "tests/test_backend_overlay.py"
    )
    NewFrontendTest = @(
        "src/features/companion/companion-runtime.test.ts",
        "src/features/companion/companion-ownership.test.ts",
        "src/features/companion/companion-sync.test.ts",
        "src/features/companion/companion-recovery.test.ts",
        "src/features/companion/companion-handoff-navigation.test.ts",
        "src/features/companion/companion-batch4-contract.test.ts",
        "src/components/overlay-chat-behavior.test.ts",
        "src/components/OverlayCompactChat.test.ts",
        "src/desktop/overlay-sizing.test.ts"
    )
}

if ($NoStart) {
    $Parameters.NoStart = $true
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " AITranslator Batch 4 Companion acceptance" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Runs targeted Batch 4 regressions, the complete project suites," -ForegroundColor DarkGray
Write-Host "frontend production build, Tauri check, and optional dev startup." -ForegroundColor DarkGray
Write-Host ""

& $Verifier @Parameters
