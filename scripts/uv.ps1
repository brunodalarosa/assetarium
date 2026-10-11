# Use this wrapper from any working directory to keep project state isolated.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot 'cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $projectRoot 'cache\python'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $projectRoot '.venv'
$env:UV_LINK_MODE = 'copy'
$env:TEMP = Join-Path $projectRoot 'scratch\tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
$env:HF_HOME = Join-Path $projectRoot 'cache\huggingface'
$env:TORCH_HOME = Join-Path $projectRoot 'cache\torch'
$env:XDG_CACHE_HOME = Join-Path $projectRoot 'cache'
$env:PYTHONPYCACHEPREFIX = Join-Path $projectRoot 'cache\pycache'
Push-Location $projectRoot
try {
    & uv @args
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
