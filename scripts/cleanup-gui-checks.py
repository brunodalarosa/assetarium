"""Retain verification evidence, then remove only reviewed synthetic fixture directories."""
import json
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = (ROOT / 'scratch').resolve(strict=True)
targets = ['pytest-gui-policy', 'pytest-gui-approved', 'pytest-gui-unit-fixed', 'pytest-gui-unit-final', 'pytest-gui-strict-inputs']
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', default='fixture-cleanup')
parser.add_argument('--caption-classification', action='store_true', help='Only the synthetic fixture directory for caption severity verification')
args = parser.parse_args()
if args.caption_classification:
    targets = ['pytest-caption-classification', 'pytest-caption-rules', 'pytest-caption-rules-final', 'pytest-caption-rules-banner']
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
report = {'status': 'running', 'targets': [], 'faults': [],
          'scope': 'This GUI implementation synthetic pytest fixtures only; no historical test trees, real asset data or caches'}
for name in targets:
    path = SCRATCH / name
    item = {'target': str(path), 'status': 'running'}
    report['targets'].append(item)
    try:
        if not path.exists():
            item['status'] = 'absent'
            continue
        if path.resolve(strict=True) != path or path.parent != SCRATCH or path.is_symlink() or path.is_junction():
            raise ValueError('Target must be this exact directory inside project scratch')
        paths = list(path.rglob('*'))
        if any(p.is_symlink() or p.is_junction() for p in paths):
            raise ValueError('Directory contains a link; no recursive delete permitted')
        item['containment_review'] = 'Exact absolute target inside scratch; every descendant checked; no links or junctions'
        item['logical_fixture_bytes'] = sum(p.stat().st_size for p in paths if p.is_file())
        preserved = []
        for data in [p for p in paths if p.is_dir() and p.name == 'data']:
            for relative in ('gui', 'mcp', 'reports', 'evidence', *(('captions',) if args.caption_classification else ())):
                source = data / relative
                if source.is_dir():
                    destination = OUT / 'preserved' / name / data.relative_to(path) / relative
                    shutil.copytree(source, destination)
                    preserved.append(str(destination.relative_to(OUT)))
        item['preserved_evidence'] = preserved
        shutil.rmtree(path)
        item['status'] = 'removed'
    except Exception as exc:
        item.update(status='faulty', reason=str(exc), retained=True)
        report['faults'].append(item)
report['status'] = 'faulty' if report['faults'] else 'passed'
(OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
