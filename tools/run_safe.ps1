# Runs experiment steps one at a time, detached-safe, with a memory guard.
# Usage: powershell -ExecutionPolicy Bypass -File tools\run_safe.ps1 -Steps partA,partC,figures,partB
# Each step logs to results\logs\<step>.log; progress goes to results\logs\status.txt (UTF-8).
param([string[]]$Steps = @("small", "load", "partC", "figures", "partB"), [int]$MinFreeGB = 8)

Set-Location (Split-Path $PSScriptRoot -Parent)
$env:OPENBLAS_NUM_THREADS = "1"; $env:OMP_NUM_THREADS = "1"; $env:MKL_NUM_THREADS = "1"
$py = ".venv\Scripts\python.exe"
New-Item -ItemType Directory -Force results\logs | Out-Null
$status = "results\logs\status.txt"

$commands = @{
    small   = @("experiments\run_partA.py", "--config", "small", "--workers", "12")
    load    = @("experiments\run_partA.py", "--config", "load", "--workers", "12")
    audit   = @("experiments\audit_invariants.py", "--workers", "12")
    partC   = @("experiments\run_partC.py", "--workers", "12")
    figures = @("experiments\make_figures.py")
    partB   = @("-m", "partB_qunetsim.run_partB")
}

function Write-Status([string]$line) {
    Add-Content -Path $status -Value "$(Get-Date -Format s) $line" -Encoding utf8
}

foreach ($step in $Steps) {
    $os = Get-CimInstance Win32_OperatingSystem
    $freeGB = [math]::Round($os.FreeVirtualMemory / 1MB, 1)
    if ($freeGB -lt $MinFreeGB) {
        Write-Status "SKIP $step : only $freeGB GB of commit free (need $MinFreeGB)"
        break
    }
    Write-Status "START $step (free commit $freeGB GB)"
    $args = $commands[$step]
    & $py @args *>&1 | Out-File -FilePath "results\logs\$step.log" -Encoding utf8
    Write-Status "END $step exit=$LASTEXITCODE"
    if ($LASTEXITCODE -ne 0) { break }
}
Write-Status "FINISHED"
