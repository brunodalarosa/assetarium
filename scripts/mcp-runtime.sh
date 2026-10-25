#!/bin/sh
# POSIX twin of mcp-runtime.ps1. Installation/testing only; clients launch Python directly.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export UV_CACHE_DIR="$root/cache/uv" UV_PYTHON_INSTALL_DIR="$root/cache/python"
export UV_PROJECT_ENVIRONMENT="$root/.venv-mcp" UV_LINK_MODE=hardlink
export TEMP="$root/scratch/tmp-mcp" TMP="$root/scratch/tmp-mcp" TMPDIR="$root/scratch/tmp-mcp"
export PYTHONPATH="$root/src"
mkdir -p "$TMPDIR"
cd "$root"
exec uv "$@"
