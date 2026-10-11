# All downloads, dependencies and runtime writes stay in this project.
$ErrorActionPreference = 'Stop'
$captionRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $captionRoot 'cache\uv-caption'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $captionRoot 'cache\python'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $captionRoot '.venv-caption'
$env:UV_LINK_MODE = 'copy'
$env:TEMP = Join-Path $captionRoot 'scratch\tmp-caption'
$env:TMP = $env:TEMP
$env:HF_HOME = Join-Path $captionRoot 'models\caption-hf'
$env:HF_HUB_DISABLE_XET = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$env:TORCH_HOME = Join-Path $captionRoot 'cache\torch-caption'
$env:CUDA_CACHE_PATH = Join-Path $captionRoot 'cache\cuda-caption'
$env:XDG_CACHE_HOME = Join-Path $captionRoot 'cache'
$env:PYTHONPYCACHEPREFIX = Join-Path $captionRoot 'cache\pycache-caption'
$env:PYTHONPATH = Join-Path $captionRoot 'src'
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
Push-Location $captionRoot
try {
    & uv @args
    $captionResult = $LASTEXITCODE
} finally { Pop-Location }
exit $captionResult
