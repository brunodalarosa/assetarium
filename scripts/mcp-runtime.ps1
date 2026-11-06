# Installation/testing only. Clients launch Python directly; stdout stays protocol-only.
$ErrorActionPreference = 'Stop'
$mcpRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $mcpRoot 'cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $mcpRoot 'cache\python'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $mcpRoot '.venv-mcp'
$env:UV_LINK_MODE = 'hardlink'
$env:TEMP = Join-Path $mcpRoot 'scratch\tmp-mcp'
$env:TMP = $env:TEMP
$env:PYTHONPATH = Join-Path $mcpRoot 'src'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
# Without --project uv falls back to the base pyproject.toml, and an exact sync strips this runtime.
if ($args.Count -and @('sync', 'run', 'lock', 'add', 'remove', 'tree', 'export') -contains $args[0] -and
    -not ($args | Where-Object { "$_" -eq '--project' -or "$_".StartsWith('--project=') })) {
    [Console]::Error.WriteLine('mcp-runtime: pass --project runtime/mcp. Without it uv would install the base project into .venv-mcp and remove this runtime.')
    exit 2
}
Push-Location $mcpRoot
try {
    & uv @args
    $mcpResult = $LASTEXITCODE
} finally { Pop-Location }
exit $mcpResult
