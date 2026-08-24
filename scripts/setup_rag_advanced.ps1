param(
    [string]$CondaEnvironment = "aitrans"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot

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

function Assert-LastExitCode {
    param([string]$Message)

    if ($LASTEXITCODE -ne 0) {
        throw $Message
    }
}

$CondaExe = Resolve-CondaExecutable

Write-Host "Repository        : $RepoRoot"
Write-Host "Conda environment : $CondaEnvironment"
Write-Host ""
Write-Host "Installing optional scientific PDF ingestion dependencies..." -ForegroundColor Yellow

Push-Location $RepoRoot
try {
    & $CondaExe run -n $CondaEnvironment python -m pip install -e ".[rag-advanced]"
    Assert-LastExitCode "Failed to install the rag-advanced optional dependency."

    Write-Host ""
    Write-Host "Verifying Docling import..." -ForegroundColor Yellow
    & $CondaExe run -n $CondaEnvironment python -c "import importlib.metadata as m; import docling; print('Docling:', m.version('docling'))"
    Assert-LastExitCode "Docling import verification failed."

    Write-Host ""
    Write-Host "Advanced PDF ingestion is ready." -ForegroundColor Green
    Write-Host "OCR and formula enrichment remain disabled by default; layout and table parsing are enabled."
}
finally {
    Pop-Location
}
