#!/bin/sh
# POSIX twin of uv.ps1: keep project state isolated from any working directory.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export UV_CACHE_DIR="$root/cache/uv" UV_PYTHON_INSTALL_DIR="$root/cache/python"
export UV_PROJECT_ENVIRONMENT="$root/.venv" UV_LINK_MODE=hardlink
export TEMP="$root/scratch/tmp" TMP="$root/scratch/tmp" TMPDIR="$root/scratch/tmp"
export HF_HOME="$root/cache/huggingface" TORCH_HOME="$root/cache/torch"
export XDG_CACHE_HOME="$root/cache" PYTHONPYCACHEPREFIX="$root/cache/pycache"
mkdir -p "$TMPDIR"
cd "$root"
exec uv "$@"
