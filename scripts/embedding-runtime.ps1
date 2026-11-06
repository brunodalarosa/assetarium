# Reuse project-local dependency downloads; isolate all installed packages.
$ErrorActionPreference = 'Stop'
$embeddingRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $embeddingRoot 'cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $embeddingRoot 'cache\python'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $embeddingRoot '.venv-embedding'
$env:UV_LINK_MODE = 'hardlink'
$env:TEMP = Join-Path $embeddingRoot 'scratch\tmp-embedding'
$env:TMP = $env:TEMP
$env:HF_HOME = Join-Path $embeddingRoot 'cache\embedding-hf'
$env:HF_HUB_DISABLE_XET = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$env:TORCH_HOME = Join-Path $embeddingRoot 'cache\torch-embedding'
$env:CUDA_CACHE_PATH = Join-Path $embeddingRoot 'cache\cuda-embedding'
$env:XDG_CACHE_HOME = Join-Path $embeddingRoot 'cache'
$env:PYTHONPYCACHEPREFIX = Join-Path $embeddingRoot 'cache\pycache-embedding'
$env:PYTHONPATH = Join-Path $embeddingRoot 'src'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
# Without --project uv falls back to the base pyproject.toml, and an exact sync strips this runtime.
if ($args.Count -and @('sync', 'run', 'lock', 'add', 'remove', 'tree', 'export') -contains $args[0] -and
    -not ($args | Where-Object { "$_" -eq '--project' -or "$_".StartsWith('--project=') })) {
    [Console]::Error.WriteLine('embedding-runtime: pass --project runtime/embedding (NVIDIA GPU) or --project runtime/embedding-cpu (CPU). Without it uv would install the base project into .venv-embedding and remove this runtime.')
    exit 2
}
Push-Location $embeddingRoot
try {
    & uv @args
    $embeddingResult = $LASTEXITCODE
} finally { Pop-Location }
exit $embeddingResult
