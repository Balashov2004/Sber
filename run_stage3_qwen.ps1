param(
    [int]$Limit = 25
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
$python = "C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path -LiteralPath $ollama)) {
    $ollamaCommand = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($ollamaCommand) {
        $ollama = $ollamaCommand.Source
    }
}

if (-not (Test-Path -LiteralPath $ollama)) {
    Write-Host "Ollama is not installed." -ForegroundColor Red
    Write-Host "Download: https://ollama.com/download/windows"
    exit 1
}

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Python runtime was not found: $python" -ForegroundColor Red
    exit 1
}

Push-Location $projectRoot
try {
    try {
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
    }
    catch {
        Start-Process -FilePath $ollama -WindowStyle Hidden
        Start-Sleep -Seconds 5
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10
    }

    $modelNames = @($tags.models | ForEach-Object { $_.name })
    if ($modelNames -notcontains "qwen3.5:9b") {
        Write-Host "Downloading qwen3.5:9b..."
        & $ollama pull qwen3.5:9b
        if ($LASTEXITCODE -ne 0) {
            throw "Model download failed."
        }
    }

    & $python stages\stage3\scripts\analyze_stage3.py
    if ($LASTEXITCODE -ne 0) {
        throw "Stage 3 deterministic analysis failed."
    }

    & $python stages\stage3\scripts\run_llm_analysis.py `
        --provider ollama `
        --model qwen3.5:9b `
        --execute `
        --resume `
        --limit $Limit

    if ($LASTEXITCODE -ne 0) {
        throw "Qwen analysis failed."
    }

    & $python stages\stage3\scripts\summarize_llm_results.py
    if ($LASTEXITCODE -ne 0) {
        throw "LLM result summarization failed."
    }

    Write-Host ""
    Write-Host "Finished. Results were saved after every task." -ForegroundColor Green
    Write-Host "Run this script again to process the next $Limit tasks."
}
finally {
    Pop-Location
}
