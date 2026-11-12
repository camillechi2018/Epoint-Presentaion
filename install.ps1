$ErrorActionPreference = 'Stop'
$entry = Join-Path $PSScriptRoot 'scripts/install_runtime.py'
if ($env:EPOINT_PYTHON) {
    & $env:EPOINT_PYTHON -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 2)' 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Error 'EPOINT_PYTHON must point to an executable Python 3.10+.'
        exit 2
    }
    & $env:EPOINT_PYTHON $entry @args
    exit $LASTEXITCODE
}
foreach ($candidate in @('py', 'python', 'python3')) {
    $command = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $command) { continue }
    if ($command.Source -match '\\Microsoft\\WindowsApps\\') { continue }
    $prefix = @()
    if ($candidate -eq 'py') { $prefix = @('-3') }
    & $command.Source @prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 2)' 2>$null
    if ($LASTEXITCODE -eq 0) {
        & $command.Source @prefix $entry @args
        exit $LASTEXITCODE
    }
}
Write-Error 'No executable Python 3.10+ found. Install Python, then run this installer again.'
exit 2
