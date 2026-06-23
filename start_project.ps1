$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$runtimePython = "C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$venvWorks = $false
if (Test-Path -LiteralPath $venvPython) {
    try {
        & $venvPython -c "import sys" 2>$null | Out-Null
        $venvWorks = $LASTEXITCODE -eq 0
    }
    catch {
        $venvWorks = $false
    }
}
$python = if ($venvWorks) { $venvPython } elseif (Test-Path -LiteralPath $runtimePython) { $runtimePython } else { "python" }
$jupyter = Join-Path $root ".venv\Scripts\jupyter-lab.exe"

function Pause-Menu {
    Write-Host ""
    Read-Host "Press Enter to return to the menu"
}

function Run-Checked {
    param([scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

Push-Location $root
try {
    while ($true) {
        Clear-Host
        Write-Host "Sber Procurement Analytics" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "[1] Prepare Stage 2 data"
        Write-Host "[2] Update PostgreSQL"
        Write-Host "[3] Rebuild Stage 3 analytics"
        Write-Host "[4] Run next 25 Qwen tasks"
        Write-Host "[5] Build final Stage 4 report"
        Write-Host "[6] Open Jupyter Notebook"
        Write-Host "[7] Run Stages 2, 3 and 4"
        Write-Host "[8] Check installed software"
        Write-Host "[9] Install or repair Python environment"
        Write-Host "[0] Exit"
        Write-Host ""
        $choice = Read-Host "Select an option"

        try {
            switch ($choice) {
                "1" {
                    Run-Checked { & $python stages\stage2\scripts\process_stage2.py }
                    Write-Host "Stage 2 data prepared." -ForegroundColor Green
                    Pause-Menu
                }
                "2" {
                    & (Join-Path $root "update_database.ps1")
                    Pause-Menu
                }
                "3" {
                    Run-Checked { & $python stages\stage3\scripts\analyze_stage3.py }
                    Run-Checked { & $python stages\stage3\scripts\summarize_llm_results.py }
                    Write-Host "Stage 3 analytics rebuilt." -ForegroundColor Green
                    Pause-Menu
                }
                "4" {
                    & (Join-Path $root "run_stage3_qwen.ps1") -Limit 25
                    Pause-Menu
                }
                "5" {
                    Run-Checked { & $python stages\stage4\scripts\build_stage4.py }
                    Write-Host "Final Notebook and HTML report created." -ForegroundColor Green
                    Pause-Menu
                }
                "6" {
                    if (-not $venvWorks -or -not (Test-Path -LiteralPath $jupyter)) {
                        throw "Jupyter Lab was not found. Run setup_environment.cmd first."
                    }
                    Start-Process -FilePath $jupyter -ArgumentList "notebooks\final_sber_procurement_report.ipynb" -WorkingDirectory $root
                    Write-Host "Jupyter Lab started." -ForegroundColor Green
                    Pause-Menu
                }
                "7" {
                    Run-Checked { & $python stages\stage2\scripts\process_stage2.py }
                    Run-Checked { & $python stages\stage3\scripts\analyze_stage3.py }
                    if (Test-Path -LiteralPath "data\processed\stage3\llm_results.jsonl") {
                        Run-Checked { & $python stages\stage3\scripts\summarize_llm_results.py }
                    }
                    Run-Checked { & $python stages\stage4\scripts\build_stage4.py }
                    Write-Host "Stages 2, 3 and 4 completed." -ForegroundColor Green
                    Pause-Menu
                }
                "8" {
                    Write-Host "Python: $python"
                    Write-Host "Python available: $(Test-Path -LiteralPath $python)"
                    Write-Host "Jupyter available: $(Test-Path -LiteralPath $jupyter)"
                    Write-Host "PostgreSQL 16 available: $(Test-Path 'C:\Program Files\PostgreSQL\16\bin\psql.exe')"
                    $ollama = Test-Path (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe")
                    Write-Host "Ollama available: $ollama"
                    if ($ollama) {
                        try {
                            $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
                            $models = @($tags.models | ForEach-Object { $_.name })
                            Write-Host "Model qwen3.5:9b available: $($models -contains 'qwen3.5:9b')"
                        }
                        catch {
                            Write-Host "Ollama server is not responding."
                        }
                    }
                    Pause-Menu
                }
                "9" {
                    & (Join-Path $root "setup_environment.ps1")
                    Pause-Menu
                }
                "0" {
                    break
                }
                default {
                    Write-Host "Unknown option." -ForegroundColor Yellow
                    Start-Sleep -Seconds 1
                }
            }
            if ($choice -eq "0") {
                break
            }
        }
        catch {
            Write-Host ""
            Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
            Pause-Menu
        }
    }
}
finally {
    Pop-Location
}
