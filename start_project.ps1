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
    Read-Host "Нажмите Enter, чтобы вернуться в меню"
}

function Run-Checked {
    param([scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Команда завершилась с кодом $LASTEXITCODE"
    }
}

Push-Location $root
try {
    while ($true) {
        Clear-Host
        Write-Host "Анализ закупок группы Сбер" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "[1] Установить или восстановить Python-окружение"
        Write-Host "[2] Скачать данные из открытых источников"
        Write-Host "[3] Объединить, обогатить и обезличить данные"
        Write-Host "[4] Очистить данные и удалить дубли"
        Write-Host "[5] Создать структуру и загрузить данные в PostgreSQL"
        Write-Host "[6] Выполнить аналитический модуль"
        Write-Host "[7] Обработать следующие 25 задач локальной Qwen"
        Write-Host "[8] Построить графики и финальный Notebook"
        Write-Host "[9] Открыть финальный Jupyter Notebook"
        Write-Host "[10] Проверить установленное программное обеспечение"
        Write-Host "[0] Выход"
        Write-Host ""
        $choice = (Read-Host "Выберите действие").Trim()

        try {
            switch ($choice) {
                "1" {
                    & (Join-Path $root "setup_environment.ps1")
                    Pause-Menu
                }
                "2" {
                    Run-Checked { & $python stages\stage1\scripts\collect_eis.py }
                    Run-Checked { & $python stages\stage1\scripts\collect_eis_queries.py --pages 10 }
                    Run-Checked { & $python stages\stage1\scripts\collect_sberbank_ast.py --all-orgs --term-mode inn --pages 5 }
                    Run-Checked { & $python stages\stage1\scripts\probe_sources.py }
                    Write-Host "Сбор данных завершён." -ForegroundColor Green
                    Pause-Menu
                }
                "3" {
                    Run-Checked { & $python stages\stage1\scripts\build_stage1_dataset.py }
                    Run-Checked { & $python stages\stage1\scripts\anonymize_exports.py }
                    Run-Checked { & $python stages\stage1\scripts\audit_anonymization.py }
                    Run-Checked { & $python stages\stage1\scripts\enrich_multisource.py }
                    Run-Checked { & $python stages\stage1\scripts\summarize_stage1.py }
                    Write-Host "Данные объединены, обогащены и обезличены." -ForegroundColor Green
                    Pause-Menu
                }
                "4" {
                    Run-Checked { & $python stages\stage2\scripts\process_stage2.py }
                    Write-Host "Очистка и дедупликация завершены." -ForegroundColor Green
                    Pause-Menu
                }
                "5" {
                    & (Join-Path $root "update_database.ps1")
                    Pause-Menu
                }
                "6" {
                    Run-Checked { & $python stages\stage3\scripts\collect_cbr_factors.py }
                    Run-Checked { & $python stages\stage3\scripts\analyze_stage3.py }
                    if (Test-Path -LiteralPath "data\processed\stage3\llm_results.jsonl") {
                        Run-Checked { & $python stages\stage3\scripts\summarize_llm_results.py }
                    }
                    Write-Host "Аналитический модуль выполнен." -ForegroundColor Green
                    Pause-Menu
                }
                "7" {
                    & (Join-Path $root "run_stage3_qwen.ps1") -Limit 25
                    Pause-Menu
                }
                "8" {
                    Run-Checked { & $python stages\stage4\scripts\build_stage4.py }
                    Write-Host "Графики, Notebook и HTML-отчёт сформированы." -ForegroundColor Green
                    Pause-Menu
                }
                "9" {
                    if (-not $venvWorks -or -not (Test-Path -LiteralPath $jupyter)) {
                        throw "Jupyter Lab не найден. Сначала выполните пункт 1."
                    }
                    Start-Process -FilePath $jupyter -ArgumentList "notebooks\final_sber_procurement_report.ipynb" -WorkingDirectory $root
                    Write-Host "Jupyter Lab запущен." -ForegroundColor Green
                    Pause-Menu
                }
                "10" {
                    Write-Host "Python: $python"
                    Write-Host "Python доступен: $(Test-Path -LiteralPath $python)"
                    Write-Host "Jupyter доступен: $(Test-Path -LiteralPath $jupyter)"
                    Write-Host "PostgreSQL 16 доступен: $(Test-Path 'C:\Program Files\PostgreSQL\16\bin\psql.exe')"
                    $ollama = Test-Path (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe")
                    Write-Host "Ollama доступна: $ollama"
                    if ($ollama) {
                        try {
                            $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
                            $models = @($tags.models | ForEach-Object { $_.name })
                            Write-Host "Модель qwen3.5:9b доступна: $($models -contains 'qwen3.5:9b')"
                        }
                        catch {
                            Write-Host "Сервер Ollama не отвечает."
                        }
                    }
                    Pause-Menu
                }
                "0" {
                    break
                }
                default {
                    Write-Host "Неизвестный пункт." -ForegroundColor Yellow
                    Start-Sleep -Seconds 1
                }
            }
            if ($choice -eq "0") {
                break
            }
        }
        catch {
            Write-Host ""
            Write-Host "Ошибка: $($_.Exception.Message)" -ForegroundColor Red
            Pause-Menu
        }
    }
}
finally {
    Pop-Location
}
