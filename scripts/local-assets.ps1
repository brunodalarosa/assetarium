# Owner CLI from the prepared mcp environment (has Pillow for exports). Installs nothing.
$ErrorActionPreference = 'Stop'
$cliRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $cliRoot '.venv-mcp\Scripts\python.exe'
if (-not (Test-Path $python)) { [Console]::Error.WriteLine('Prepare the mcp environment first: .\scripts\mcp-runtime.ps1 sync --locked --project runtime/mcp'); exit 2 }
$env:PYTHONPATH = Join-Path $cliRoot 'src'
& $python -m local_asset_library.cli @args
exit $LASTEXITCODE
