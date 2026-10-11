"""Absolute-path entry point for both clients, independent of their working directory."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from local_asset_library.mcp_server import main
if __name__ == '__main__':
    main()
