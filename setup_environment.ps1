$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"

function Find-Python {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            & $py.Source -3.12 -c "import sys; print(sys.executable)" | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return ,@($py.Source, "-3.12")
            }
        }
        catch {
        }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return ,@($python.Source)
    }
    $runtime = "C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $runtime) {
        return ,@($runtime)
    }
    throw "Python 3.12 was not found. Download it from https://www.python.org/downloads/windows/"
}

Push-Location $root
try {
    $basePython = Find-Python
    $venvWorks = $false
    if (Test-Path -LiteralPath $venvPython) {
        try {
            & $venvPython -c "import sys; print(sys.version)" 2>$null | Out-Null
            $venvWorks = $LASTEXITCODE -eq 0
        }
        catch {
            $venvWorks = $false
        }
    }

    if (-not $venvWorks) {
        if (Test-Path -LiteralPath $venv) {
            $answer = Read-Host "The current .venv is broken. Recreate it? [Y/N]"
            if ($answer -notin @("Y", "y")) {
                throw "Environment setup cancelled."
            }
            $resolved = (Resolve-Path -LiteralPath $venv).Path
            if (-not $resolved.StartsWith((Resolve-Path $root).Path)) {
                throw "The environment directory is outside the project."
            }
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
        if ($basePython.Count -eq 2) {
            & $basePython[0] $basePython[1] -m venv .venv
        }
        else {
            & $basePython[0] -m venv .venv
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to create .venv."
        }
    }

    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to update pip."
    }
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to install dependencies."
    }

    Write-Host ""
    Write-Host "Environment is ready." -ForegroundColor Green
    Write-Host "Main menu: .\start_project.cmd"
    Write-Host "Notebook: .\open_notebook.cmd"
}
finally {
    Pop-Location
}
