param(
    [string]$Database = "Sber",
    [string]$User = "admin",
    [string]$HostName = "localhost",
    [int]$Port = 5432
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$loadScript = "stages\stage2\sql\load_data.psql"

$psqlCandidates = @(
    "C:\Program Files\PostgreSQL\17\bin\psql.exe",
    "C:\Program Files\PostgreSQL\16\bin\psql.exe",
    "C:\Program Files\PostgreSQL\15\bin\psql.exe"
)

$psql = $psqlCandidates |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1

if (-not $psql) {
    $command = Get-Command psql.exe -ErrorAction SilentlyContinue
    if ($command) {
        $psql = $command.Source
    }
}

if (-not $psql) {
    Write-Host "PostgreSQL psql.exe was not found." -ForegroundColor Red
    Write-Host "Install PostgreSQL or add PostgreSQL\bin to PATH."
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $loadScript))) {
    Write-Host "Load script was not found: $loadScript" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "Updating the Sber procurement database" -ForegroundColor Cyan
Write-Host "Server: $HostName`:$Port"
Write-Host "Database: $Database"
Write-Host "User: $User"
Write-Host ""
Write-Host "Enter the PostgreSQL password for user $User."
Write-Host ""

$securePassword = Read-Host "Password" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

Push-Location $projectRoot
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)

    & $psql `
        -v ON_ERROR_STOP=1 `
        -h $HostName `
        -p $Port `
        -U $User `
        -d $Database `
        -w `
        -f $loadScript

    if ($LASTEXITCODE -ne 0) {
        throw "psql exited with code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "Database update completed successfully." -ForegroundColor Green
    Write-Host "Refresh the sber_procurement schema in DB Browser."
}
catch {
    Write-Host ""
    Write-Host "Database update failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    Pop-Location
}
