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
# Without --project uv falls back to the base pyproject.toml, and an exact sync strips this runtime.
case "${1-}" in sync|run|lock|add|remove|tree|export)
  case " $* " in *" --project "*|*" --project="*) ;;
  *) echo "caption-runtime: pass --project runtime/caption. Without it uv would install the base project into .venv-caption and remove this runtime." >&2; exit 2 ;; esac ;; esac
cd "$root"
exec uv "$@"
