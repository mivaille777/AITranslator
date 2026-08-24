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
    Write-Host "Verifying local embedding stack after dependency resolution..." -ForegroundColor Yellow
    & $CondaExe run -n $CondaEnvironment python -c "import importlib.metadata as m, torch, transformers, sentence_transformers; print('torch:', torch.__version__); print('transformers:', transformers.__version__); print('sentence-transformers:', m.version('sentence-transformers')); print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
    Assert-LastExitCode "Docling installed, but the local embedding Python stack is no longer importable."

    Write-Host ""
    Write-Host "Advanced PDF ingestion is ready." -ForegroundColor Green
    Write-Host "OCR and formula enrichment remain disabled by default; layout and table parsing are enabled."
    Write-Host "Docling parsing runs on CPU by default; CUDA remains reserved for Qwen embedding/reranking."
}
finally {
    Pop-Location
}
