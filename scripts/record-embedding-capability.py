"""Record the search check (decisions 0018 and 0031) from a terminal; the app runs the same check with Run check.

It runs on two built-in sample images (local_asset_library.search_check), never library assets, and writes only
data/embeddings/capability.json. Run it again after changing the search device.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from local_asset_library.search_check import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
