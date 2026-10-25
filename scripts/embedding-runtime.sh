#!/bin/sh
# POSIX twin of embedding-runtime.ps1: caches stay in this project; weights use configured shared storage.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export UV_CACHE_DIR="$root/cache/uv" UV_PYTHON_INSTALL_DIR="$root/cache/python"
export UV_PROJECT_ENVIRONMENT="$root/.venv-embedding" UV_LINK_MODE=hardlink
export TEMP="$root/scratch/tmp-embedding" TMP="$root/scratch/tmp-embedding" TMPDIR="$root/scratch/tmp-embedding"
export HF_HOME="$root/cache/embedding-hf" HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_SYMLINKS_WARNING=1
export TORCH_HOME="$root/cache/torch-embedding" CUDA_CACHE_PATH="$root/cache/cuda-embedding"
export XDG_CACHE_HOME="$root/cache" PYTHONPYCACHEPREFIX="$root/cache/pycache-embedding"
export PYTHONPATH="$root/src"
mkdir -p "$TMPDIR"
cd "$root"
exec uv "$@"
