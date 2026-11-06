#!/bin/sh
# POSIX twin of mcp-runtime.ps1. Installation/testing only; clients launch Python directly.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export UV_CACHE_DIR="$root/cache/uv" UV_PYTHON_INSTALL_DIR="$root/cache/python"
export UV_PROJECT_ENVIRONMENT="$root/.venv-mcp" UV_LINK_MODE=hardlink
export TEMP="$root/scratch/tmp-mcp" TMP="$root/scratch/tmp-mcp" TMPDIR="$root/scratch/tmp-mcp"
export PYTHONPATH="$root/src"
mkdir -p "$TMPDIR"
# Without --project uv falls back to the base pyproject.toml, and an exact sync strips this runtime.
case "${1-}" in sync|run|lock|add|remove|tree|export)
  case " $* " in *" --project "*|*" --project="*) ;;
  *) echo "mcp-runtime: pass --project runtime/mcp. Without it uv would install the base project into .venv-mcp and remove this runtime." >&2; exit 2 ;; esac ;; esac
cd "$root"
exec uv "$@"
