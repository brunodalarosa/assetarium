#!/bin/sh
# Owner CLI from the prepared mcp environment (has Pillow for exports). Installs nothing.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ ! -x "$root/.venv-mcp/bin/python" ]; then
  echo "Prepare the mcp environment first: ./scripts/mcp-runtime.sh sync --locked --project runtime/mcp" >&2; exit 2
fi
export PYTHONPATH="$root/src"
exec "$root/.venv-mcp/bin/python" -m local_asset_library.cli "$@"
