param(
    # Batch-specific Python tests to run before the complete suite.
    # Examples:
    #   -NewTest "tests/test_translation_provider_persistence.py"
    #   -NewTest "tests/test_a.py","tests/test_b.py::test_case"
    [string[]]$NewTest = @(),

    # Batch-specific Vitest targets to run before the complete frontend suite.
    # Examples:
    #   -NewFrontendTest "src/desktop/overlay-sizing.test.ts"
    #   -NewFrontendTest "src/features/companion/companion-runtime.test.ts","src/components/OverlayCompactChat.test.ts"
    [string[]]$NewFrontendTest = @(),

    # Run verification only; do not launch Backend/Tauri afterwards.
    [switch]$NoStart,

    # Development-only shortcut. Formal acceptance should not use this switch.
    [switch]$SkipFullPythonTests
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# ============================================================
# AITranslator - fixed verification + development startup
# ============================================================

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DesktopDir = Join-Path $RepoRoot "apps\desktop"
$TauriDir = Join-Path $DesktopDir "src-tauri"
$ExpectedBranch = "WebReBuild"
$ExpectedCondaEnvironment = "aitrans"

function Write-Step {
    param(
        [string]$Title,
        [int]$Index,
        [int]$Total = 8
    )

    Write-Host ""
    Write-Host "[$Index/$Total] $Title" -ForegroundColor Yellow
}

function Assert-LastExitCode {
    param([string]$Message)

    if ($LASTEXITCODE -ne 0) {
        throw $Message
    }
}

function Resolve-CondaExecutable {
    $command = Get-Command conda -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "$env:USERPROFILE\anaconda3\Scripts\conda.exe",
        "$env:USERPROFILE\miniconda3\Scripts\conda.exe",
        "C:\ProgramData\anaconda3\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\Scripts\conda.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Conda executable was not found. Install Conda or add it to PATH."
}

function Resolve-PowerShellExecutable {
    $pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    if ($pwsh) {
        return $pwsh.Source
    }

    $windowsPowerShell = Get-Command powershell.exe -ErrorAction SilentlyContinue
    if ($windowsPowerShell) {
        return $windowsPowerShell.Source
    }

    throw "Neither pwsh.exe nor powershell.exe was found."
}

function ConvertTo-EncodedPowerShellCommand {
    param([string]$Command)

    # PowerShell -EncodedCommand expects UTF-16LE input.
    return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
}

function Get-GitDirtyClassification {
    param([string[]]$Lines)

    $generated = [System.Collections.Generic.List[string]]::new()
    $blocking = [System.Collections.Generic.List[string]]::new()

    foreach ($line in $Lines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $status = if ($line.Length -ge 2) { $line.Substring(0, 2) } else { "" }
        $path = if ($line.Length -ge 4) { $line.Substring(3).Trim() } else { $line.Trim() }

        # These are local artifacts created by normal verification/runtime use.
        # Ignore them only while they are UNTRACKED. If any of these files ever
        # become tracked, modifications must block the pull like normal source files.
        $safeGenerated = $status -eq "??" -and (
            $path -eq "apps/desktop/src-tauri/Cargo.lock" -or
            $path -match '^config/.+\.sqlite3(?:-shm|-wal)?$'
        )

        if ($safeGenerated) {
            $generated.Add($line)
        }
        else {
            $blocking.Add($line)
        }
    }

    return [PSCustomObject]@{
        Generated = @($generated)
        Blocking = @($blocking)
    }
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " AITranslator verification pipeline" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "Repository : $RepoRoot"
Write-Host ""

# ------------------------------------------------------------
# 1. Conda
# ------------------------------------------------------------

Write-Step "Activate Conda environment: $ExpectedCondaEnvironment" 1

$CondaExe = Resolve-CondaExecutable

(& $CondaExe "shell.powershell" "hook") |
    Out-String |
    Invoke-Expression

conda activate $ExpectedCondaEnvironment
Assert-LastExitCode "Failed to activate Conda environment '$ExpectedCondaEnvironment'."

if ($env:CONDA_DEFAULT_ENV -ne $ExpectedCondaEnvironment) {
    throw "Wrong Conda environment: '$env:CONDA_DEFAULT_ENV'. Expected '$ExpectedCondaEnvironment'."
}

Write-Host "Conda environment : $env:CONDA_DEFAULT_ENV" -ForegroundColor Green
python -c "import sys; print('Python executable  :', sys.executable); print('Python version     :', sys.version.split()[0])"
Assert-LastExitCode "Python is not usable inside Conda environment '$ExpectedCondaEnvironment'."

# ------------------------------------------------------------
# 2. Git synchronization
# ------------------------------------------------------------

Write-Step "Verify and synchronize Git branch" 2
Set-Location $RepoRoot

$CurrentBranch = (git branch --show-current).Trim()
Assert-LastExitCode "Unable to read the current Git branch."

if ($CurrentBranch -ne $ExpectedBranch) {
    throw "Wrong Git branch '$CurrentBranch'. Expected '$ExpectedBranch'. Refusing to touch another branch."
}

# Protect real source/config changes, but do not block normal verification on
# known untracked runtime artifacts such as the local SQLite DB or Cargo.lock.
$DirtyFiles = @(git status --porcelain --untracked-files=all)
Assert-LastExitCode "Unable to read Git working tree status."
$DirtyClassification = Get-GitDirtyClassification $DirtyFiles

if ($DirtyClassification.Generated.Count -gt 0) {
    Write-Host "Generated/runtime artifacts detected (allowed):" -ForegroundColor DarkYellow
    $DirtyClassification.Generated | ForEach-Object {
        Write-Host "  $_" -ForegroundColor DarkYellow
    }
}

if ($DirtyClassification.Blocking.Count -gt 0) {
    Write-Host "Source-controlled or unknown local changes detected:" -ForegroundColor Red
    $DirtyClassification.Blocking | ForEach-Object {
        Write-Host "  $_" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Inspect tracked changes before deciding whether to keep or restore them:" -ForegroundColor Yellow
    Write-Host "  git diff -- apps/desktop/package-lock.json apps/desktop/src-tauri/Cargo.toml" -ForegroundColor Cyan
    Write-Host "  git status --short" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "If those tracked changes are NOT intentional, restore only after reviewing the diff:" -ForegroundColor Yellow
    Write-Host "  git restore -- apps/desktop/package-lock.json apps/desktop/src-tauri/Cargo.toml" -ForegroundColor Cyan
    throw "Tracked/unknown working-tree changes require review before automatic git pull."
}

Write-Host "Branch            : $CurrentBranch" -ForegroundColor Green

git fetch origin $ExpectedBranch
Assert-LastExitCode "git fetch failed."

git pull --ff-only origin $ExpectedBranch
Assert-LastExitCode "git pull --ff-only failed."

$CurrentCommit = (git rev-parse --short HEAD).Trim()
Assert-LastExitCode "Unable to read Git HEAD."
Write-Host "Current HEAD      : $CurrentCommit" -ForegroundColor Green

# ------------------------------------------------------------
# 3. Batch-specific tests
# ------------------------------------------------------------

Write-Step "Run batch-specific tests" 3

$ResolvedPythonTests = @($NewTest | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$ResolvedFrontendTests = @($NewFrontendTest | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

if ($ResolvedPythonTests.Count -eq 0 -and $ResolvedFrontendTests.Count -eq 0) {
    Write-Host "No targeted test supplied. Skipping batch-specific tests." -ForegroundColor DarkYellow
}

if ($ResolvedPythonTests.Count -gt 0) {
    Set-Location $RepoRoot
    foreach ($testTarget in $ResolvedPythonTests) {
        Write-Host "-> python -m pytest $testTarget -q" -ForegroundColor Cyan
        python -m pytest $testTarget -q
        Assert-LastExitCode "Batch-specific Python test failed: $testTarget"
    }
    Write-Host "Batch-specific Python tests PASSED." -ForegroundColor Green
}

if ($ResolvedFrontendTests.Count -gt 0) {
    Set-Location $DesktopDir
    foreach ($testTarget in $ResolvedFrontendTests) {
        Write-Host "-> npx vitest run $testTarget" -ForegroundColor Cyan
        npx vitest run $testTarget
        Assert-LastExitCode "Batch-specific frontend test failed: $testTarget"
    }
    Write-Host "Batch-specific frontend tests PASSED." -ForegroundColor Green
}

# ------------------------------------------------------------
# 4. Complete Python suite
# ------------------------------------------------------------

Write-Step "Run complete Python test suite" 4
Set-Location $RepoRoot

if ($SkipFullPythonTests) {
    Write-Host "Full Python suite skipped by -SkipFullPythonTests." -ForegroundColor DarkYellow
}
else {
    python -m pytest tests -q
    Assert-LastExitCode "Python test suite failed."
    Write-Host "Python test suite PASSED." -ForegroundColor Green
}

# ------------------------------------------------------------
# 5. Frontend lint/test/build
# ------------------------------------------------------------

Write-Step "Verify desktop frontend" 5
Set-Location $DesktopDir

Write-Host "-> npm run lint" -ForegroundColor Cyan
npm run lint
Assert-LastExitCode "Frontend lint failed."

Write-Host ""
Write-Host "-> npm run test" -ForegroundColor Cyan
npm run test
Assert-LastExitCode "Frontend unit tests failed."

Write-Host ""
Write-Host "-> npm run build" -ForegroundColor Cyan
npm run build
Assert-LastExitCode "Frontend production build failed."

Write-Host "Frontend verification PASSED." -ForegroundColor Green

# ------------------------------------------------------------
# 6. Rust/Tauri compile check
# ------------------------------------------------------------

Write-Step "Run Cargo check" 6
Set-Location $TauriDir

cargo check
Assert-LastExitCode "cargo check failed."
Write-Host "Cargo check PASSED." -ForegroundColor Green

# ------------------------------------------------------------
# 7. Summary
# ------------------------------------------------------------

Write-Step "Verification complete" 7
Write-Host "Branch             : $CurrentBranch"
Write-Host "HEAD               : $CurrentCommit"
Write-Host "Conda environment  : $env:CONDA_DEFAULT_ENV"
Write-Host ""
Write-Host "All requested checks passed." -ForegroundColor Green

if ($NoStart) {
    Write-Host "Development startup skipped because -NoStart was supplied." -ForegroundColor Yellow
    Set-Location $RepoRoot
    exit 0
}

# ------------------------------------------------------------
# 8. Launch Backend + Tauri concurrently
# ------------------------------------------------------------

Write-Step "Start Backend + Tauri concurrently" 8

$PowerShellExe = Resolve-PowerShellExecutable

# Explicitly activate Conda inside BOTH child shells. Child processes do not
# rely on the parent's PowerShell profile or inherited Conda function state.
$BackendCommand = @"
`$ErrorActionPreference = 'Stop'
(& '$CondaExe' 'shell.powershell' 'hook') | Out-String | Invoke-Expression
conda activate '$ExpectedCondaEnvironment'
Set-Location '$DesktopDir'
Write-Host ''
Write-Host '====================================' -ForegroundColor Cyan
Write-Host ' AITranslator Backend' -ForegroundColor Cyan
Write-Host ' Conda: $ExpectedCondaEnvironment' -ForegroundColor Cyan
Write-Host ' Directory: $DesktopDir' -ForegroundColor Cyan
Write-Host '====================================' -ForegroundColor Cyan
Write-Host ''
npm run backend:dev
"@

$TauriCommand = @"
`$ErrorActionPreference = 'Stop'
(& '$CondaExe' 'shell.powershell' 'hook') | Out-String | Invoke-Expression
conda activate '$ExpectedCondaEnvironment'
Set-Location '$DesktopDir'
Write-Host ''
Write-Host '====================================' -ForegroundColor Magenta
Write-Host ' AITranslator Tauri Desktop' -ForegroundColor Magenta
Write-Host ' Conda: $ExpectedCondaEnvironment' -ForegroundColor Magenta
Write-Host ' Directory: $DesktopDir' -ForegroundColor Magenta
Write-Host '====================================' -ForegroundColor Magenta
Write-Host ''
npm run tauri:dev
"@

$BackendEncoded = ConvertTo-EncodedPowerShellCommand $BackendCommand
$TauriEncoded = ConvertTo-EncodedPowerShellCommand $TauriCommand

# Start both processes immediately. We intentionally do not wait for Backend
# to exit before starting Tauri: the two development services run together.
$BackendProcess = Start-Process `
    -FilePath $PowerShellExe `
    -ArgumentList "-NoExit", "-EncodedCommand", $BackendEncoded `
    -PassThru

$TauriProcess = Start-Process `
    -FilePath $PowerShellExe `
    -ArgumentList "-NoExit", "-EncodedCommand", $TauriEncoded `
    -PassThru

Write-Host "Backend PID        : $($BackendProcess.Id)" -ForegroundColor Green
Write-Host "Tauri PID          : $($TauriProcess.Id)" -ForegroundColor Green
Write-Host ""
Write-Host "Backend and Tauri were launched concurrently in separate PowerShell windows." -ForegroundColor Green
Write-Host "Keep both windows open while manually testing the desktop app." -ForegroundColor Cyan

Set-Location $RepoRoot
