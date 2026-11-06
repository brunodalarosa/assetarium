# Runtime caches and dependencies stay in this project; model weights use configured shared storage.
$ErrorActionPreference = 'Stop'
$captionRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $captionRoot 'cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $captionRoot 'cache\python'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $captionRoot '.venv-caption'
$env:UV_LINK_MODE = 'hardlink'
$env:TEMP = Join-Path $captionRoot 'scratch\tmp-caption'
$env:TMP = $env:TEMP
$env:HF_HOME = Join-Path $captionRoot 'cache\caption-hf'
$env:HF_HUB_DISABLE_XET = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$env:TORCH_HOME = Join-Path $captionRoot 'cache\torch-caption'
$env:CUDA_CACHE_PATH = Join-Path $captionRoot 'cache\cuda-caption'
$env:XDG_CACHE_HOME = Join-Path $captionRoot 'cache'
$env:PYTHONPYCACHEPREFIX = Join-Path $captionRoot 'cache\pycache-caption'
$env:PYTHONPATH = Join-Path $captionRoot 'src'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
# Without --project uv falls back to the base pyproject.toml, and an exact sync strips this runtime.
if ($args.Count -and @('sync', 'run', 'lock', 'add', 'remove', 'tree', 'export') -contains $args[0] -and
    -not ($args | Where-Object { "$_" -eq '--project' -or "$_".StartsWith('--project=') })) {
    [Console]::Error.WriteLine('caption-runtime: pass --project runtime/caption. Without it uv would install the base project into .venv-caption and remove this runtime.')
    exit 2
}
Push-Location $captionRoot
try {
    & uv @args
    $captionResult = $LASTEXITCODE
} finally { Pop-Location }
exit $captionResult
