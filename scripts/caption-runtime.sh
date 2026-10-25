#!/bin/sh
# POSIX twin of caption-runtime.ps1: caches stay in this project; weights use configured shared storage.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export UV_CACHE_DIR="$root/cache/uv" UV_PYTHON_INSTALL_DIR="$root/cache/python"
export UV_PROJECT_ENVIRONMENT="$root/.venv-caption" UV_LINK_MODE=hardlink
export TEMP="$root/scratch/tmp-caption" TMP="$root/scratch/tmp-caption" TMPDIR="$root/scratch/tmp-caption"
export HF_HOME="$root/cache/caption-hf" HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_SYMLINKS_WARNING=1
export TORCH_HOME="$root/cache/torch-caption" CUDA_CACHE_PATH="$root/cache/cuda-caption"
export XDG_CACHE_HOME="$root/cache" PYTHONPYCACHEPREFIX="$root/cache/pycache-caption"
export PYTHONPATH="$root/src"
mkdir -p "$TMPDIR"
cd "$root"
exec uv "$@"
