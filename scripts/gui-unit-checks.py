"""Preserve focused test output and result even when checks fail."""
import json
import argparse
from pathlib import Path
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', default='unit-checks')
parser.add_argument('--desktop-only', action='store_true', help='Focused checks for a desktop-only refinement')
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
folder = root / 'data/gui' / args.run_name
folder.mkdir(parents=True, exist_ok=False)
started = time.perf_counter()
tests = ['tests/test_desktop.py'] if args.desktop_only else ['tests/test_desktop.py', 'tests/test_mcp_assets.py', 'tests/test_retrieval.py']
command = [sys.executable, '-m', 'pytest', *tests, '--basetemp', 'scratch/pytest-gui-' + args.run_name]
process = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8')
(folder / 'stdout.log').write_text(process.stdout, encoding='utf-8')
(folder / 'stderr.log').write_text(process.stderr, encoding='utf-8')
report = {'status': 'passed' if process.returncode == 0 else 'faulty', 'returncode': process.returncode,
          'elapsed_seconds': time.perf_counter() - started, 'output': process.stdout[-3000:],
          'scope': 'Synthetic desktop/shared-policy fixtures only; no real asset processing'}
(folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
sys.exit(process.returncode)
