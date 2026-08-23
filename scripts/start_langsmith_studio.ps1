param(
    [switch]$Install,
    [switch]$EnableTracing
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$previousPythonUtf8 = $env:PYTHONUTF8
$previousLangSmithTracing = $env:LANGSMITH_TRACING

Push-Location $repoRoot
try {
    # LangGraph API currently reads one of its packaged OpenAPI files with the
    # process default encoding. Chinese Windows commonly defaults to GBK, so
    # force Python UTF-8 mode before any LangGraph subprocess is started.
    $env:PYTHONUTF8 = "1"

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Python is unavailable. Activate the 'aitrans' conda environment first."
    }

    $pythonExecutable = (& python -c "import sys; print(sys.executable)").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to resolve the active Python executable."
    }

    $pythonVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read the active Python version."
    }
    if ($pythonVersion -ne "3.11") {
        throw "Python 3.11 is required for LangSmith Studio in this project. Current version: $pythonVersion"
    }

    $isAitransCondaEnv = $env:CONDA_DEFAULT_ENV -eq "aitrans"
    $isAitransPython = $pythonExecutable -match "[\\/]envs[\\/]aitrans[\\/]"
    if (-not $isAitransCondaEnv -and -not $isAitransPython) {
        throw "The 'aitrans' conda environment is not active. Run 'conda activate aitrans' first."
    }

    $langGraphConfig = Join-Path $repoRoot "langgraph.json"
    if (-not (Test-Path $langGraphConfig)) {
        throw "langgraph.json was not found at the repository root: $repoRoot"
    }

    try {
        $null = Get-Content -Raw -Encoding UTF8 $langGraphConfig | ConvertFrom-Json
    }
    catch {
        throw "langgraph.json is not valid UTF-8 JSON: $($_.Exception.Message)"
    }

    if ($Install) {
        Write-Host "Installing LangSmith Studio development dependencies..."
        & python -m pip install -e ".[studio]"
        if ($LASTEXITCODE -ne 0) {
            throw "Studio dependency installation failed with exit code $LASTEXITCODE."
        }
    }

    $langgraphCommand = Get-Command langgraph -ErrorAction SilentlyContinue
    if ($null -eq $langgraphCommand) {
        throw "The 'langgraph' CLI is unavailable. Run this script again with -Install."
    }

    if ([string]::IsNullOrWhiteSpace($env:LANGSMITH_API_KEY)) {
        throw "LANGSMITH_API_KEY is not set in this PowerShell session. Set it as an environment variable before starting Studio."
    }

    $env:LANGSMITH_TRACING = if ($EnableTracing) { "true" } else { "false" }

    Write-Host "Starting LangSmith Studio development server..."
    Write-Host "Repository: $repoRoot"
    Write-Host "Python:     $pythonExecutable ($pythonVersion)"
    Write-Host "UTF-8 mode: enabled (PYTHONUTF8=1)"
    Write-Host "Tracing:    $env:LANGSMITH_TRACING"
    Write-Host "API:        http://127.0.0.1:2024"
    Write-Host "Studio:     https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024"
    Write-Host "Press Ctrl+C to stop the development server."
    Write-Host ""

    & langgraph dev
    if ($LASTEXITCODE -ne 0) {
        throw "langgraph dev exited with code $LASTEXITCODE."
    }
}
finally {
    if ($null -eq $previousPythonUtf8) {
        Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONUTF8 = $previousPythonUtf8
    }

    if ($null -eq $previousLangSmithTracing) {
        Remove-Item Env:LANGSMITH_TRACING -ErrorAction SilentlyContinue
    }
    else {
        $env:LANGSMITH_TRACING = $previousLangSmithTracing
    }

    Pop-Location
}
