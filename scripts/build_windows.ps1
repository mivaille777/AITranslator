[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$RunSmokeTest
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot "AITranslator\Scripts\python.exe"
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$python = if (Test-Path -LiteralPath $venvPython) {
    $venvPython
} elseif ($null -ne $pythonCommand) {
    $pythonCommand.Source
} else {
    throw "Python was not found. Activate the AITranslator virtual environment first."
}

$specPath = Join-Path $repoRoot "desktop_translator.spec"
$buildRoot = Join-Path $repoRoot "build\pyinstaller"
$distRoot = Join-Path $repoRoot "dist"
$distApp = Join-Path $distRoot "AITranslator"
$exePath = Join-Path $distApp "AITranslator.exe"

if (-not (Test-Path -LiteralPath $specPath -PathType Leaf)) {
    throw "PyInstaller spec file was not found: $specPath"
}

function Remove-ExactBuildTarget {
    param([Parameter(Mandatory = $true)][string]$Target)

    $resolvedTarget = [IO.Path]::GetFullPath($Target)
    $resolvedRoot = [IO.Path]::GetFullPath($repoRoot).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedTarget.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the repository: $resolvedTarget"
    }
    if ($resolvedTarget -eq $resolvedRoot.TrimEnd([IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to remove the repository root."
    }
    if (Test-Path -LiteralPath $resolvedTarget) {
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
    }
}

if ($Clean) {
    Remove-ExactBuildTarget -Target $buildRoot
    Remove-ExactBuildTarget -Target $distApp
}

& $python -m PyInstaller --version
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is unavailable. Install it with: python -m pip install -e ".[build]"'
}

$pyinstallerArguments = @(
    "--clean",
    "--noconfirm",
    "--distpath",
    $distRoot,
    "--workpath",
    $buildRoot,
    $specPath
)
& $python -m PyInstaller @pyinstallerArguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "The expected GUI executable was not produced: $exePath"
}

$bundledConfig = Join-Path $distApp "_internal\config\default.toml"
if (-not (Test-Path -LiteralPath $bundledConfig -PathType Leaf)) {
    $bundledConfig = Join-Path $distApp "config\default.toml"
}
if (-not (Test-Path -LiteralPath $bundledConfig -PathType Leaf)) {
    throw "The bundled default configuration was not found below $distApp"
}

$forbiddenNames = @(
    "application_default_credentials.json",
    "credentials.json",
    "user.toml",
    "translation_cache.sqlite3",
    "translation_cache.sqlite3-shm",
    "translation_cache.sqlite3-wal"
)
$forbiddenFiles = @(
    Get-ChildItem -LiteralPath $distApp -Recurse -File |
        Where-Object { $forbiddenNames -contains $_.Name }
)
if ($forbiddenFiles.Count -gt 0) {
    $names = ($forbiddenFiles | ForEach-Object { $_.FullName }) -join ", "
    throw "The build contains a forbidden user or credential file: $names"
}

Write-Host "Build complete: $exePath"
Write-Host "Bundled default config: $bundledConfig"
Write-Host "Runtime writable data: $env:APPDATA\AITranslator"
Write-Host "Distribute the entire dist\AITranslator directory, not only the EXE."

if ($RunSmokeTest) {
    $smokeDataRoot = Join-Path $buildRoot "smoke-data"
    New-Item -ItemType Directory -Path $smokeDataRoot -Force | Out-Null
    $previousDataRoot = $env:AITRANSLATOR_DATA_DIR
    try {
        $env:AITRANSLATOR_DATA_DIR = $smokeDataRoot
        $startProcessArguments = @{
            FilePath = $exePath
            ArgumentList = "--smoke-test"
            WindowStyle = "Hidden"
            Wait = $true
            PassThru = $true
        }
        $smokeProcess = Start-Process @startProcessArguments
    } finally {
        if ($null -eq $previousDataRoot) {
            Remove-Item Env:AITRANSLATOR_DATA_DIR -ErrorAction SilentlyContinue
        } else {
            $env:AITRANSLATOR_DATA_DIR = $previousDataRoot
        }
    }
    if ($smokeProcess.ExitCode -ne 0) {
        throw "EXE smoke test failed with exit code $($smokeProcess.ExitCode)."
    }

    foreach ($runtimeDirectory in @(
        (Join-Path $smokeDataRoot "config"),
        (Join-Path $smokeDataRoot "logs")
    )) {
        if (-not (Test-Path -LiteralPath $runtimeDirectory -PathType Container)) {
            throw "EXE smoke test did not create runtime directory: $runtimeDirectory"
        }
    }
    Write-Host "EXE smoke test passed; config and logs directories were created."
}
