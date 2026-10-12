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
Push-Location $mcpRoot
try {
    & uv @args
    $mcpResult = $LASTEXITCODE
} finally { Pop-Location }
exit $mcpResult
