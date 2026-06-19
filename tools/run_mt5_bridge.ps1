# Launch the MT5 bridge server with the Python that has the MetaTrader5 package.
#
# On this machine the backend venv is Python 3.14 (no MetaTrader5); the package
# is installed in system Python 3.13, so the bridge MUST run with py -3.13.
#
# Usage:  powershell -ExecutionPolicy Bypass -File tools\run_mt5_bridge.ps1
# Then open the "MT5 Connection" page in the app and click Connect.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# Optional shared secret (must match MT5_BRIDGE_KEY in backend/.env if set).
# $env:MT5_BRIDGE_KEY = "your-shared-secret"

Write-Host "Starting MT5 bridge on http://localhost:8765 (py -3.13)..." -ForegroundColor Cyan
py -3.13 (Join-Path $here "mt5_bridge_server.py")
