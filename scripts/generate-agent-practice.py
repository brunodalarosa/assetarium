"""Generate a new practice folder; the app uses the same generator for its disposable sessions."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from local_asset_library.agent_practice_assets import generate

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, help='A new folder to create')
    args = parser.parse_args()
    print(f'Generated {len(generate(args.destination))} files in {args.destination}')
