"""Owner-approved removal of old pytest/verification folders in scratch/ (decision 0006).

Two steps: ``--plan`` writes a reviewed list to data/maintenance/; ``--apply PLAN``
removes exactly that list. Only top-level folders whose contents look like pytest
temp trees or synthetic verification fixtures qualify; runtime temp folders,
scripts and logs are never selected. Links are removed as links (never followed)
and only when they point inside their own folder or nowhere; every file is
re-hashed immediately before removal and changed files are retained as faults.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.maintenance_files import manifest, remove_empty_parents, remove_empty_tree, remove_manifest  # noqa: E402
from local_asset_library.publication import filesystem_path  # noqa: E402

SCRATCH = ROOT / 'scratch'
PYTEST = re.compile(r'^(test_|hash-cache|popen-gw|pytest-of)')
FIXTURE = {'project', 'source', 'sources', 'empty-source'}


def qualifies(folder):
    if folder.name.startswith('tmp') or folder.name == 'pytest' or folder.is_symlink() or folder.is_junction():
        return False
    children = [c.name for c in folder.iterdir()]
    return bool(children) and (all(PYTEST.match(c) for c in children) or set(children) <= FIXTURE)


def links(folder):
    found = []
    def linked(native):
        return os.path.islink(native) or os.path.isjunction(native)
    # Walk with long-path syntax (deep pytest trees); report plain paths.
    for directory, dirs, files in os.walk(filesystem_path(folder), followlinks=False):
        for name in dirs + files:
            native = os.path.join(directory, name)
            if linked(native):
                plain = Path(native.removeprefix('\\\\?\\'))
                target = Path(os.readlink(native).removeprefix('\\\\?\\'))
                target = target if target.is_absolute() else (plain.parent / target)
                inside = (not os.path.exists(filesystem_path(target))
                          or Path(os.path.realpath(filesystem_path(target)).removeprefix('\\\\?\\')).is_relative_to(folder.resolve()))
                found.append({'path': plain.relative_to(SCRATCH).as_posix(), 'target': str(target), 'inside': inside,
                              'directory': os.path.isdir(native)})
        dirs[:] = [d for d in dirs if not linked(os.path.join(directory, d))]
    return found


def plan():
    folders, retained = [], []
    for folder in sorted(p for p in SCRATCH.iterdir() if p.is_dir()):
        if not qualifies(folder):
            continue
        found = links(folder)
        if any(not link['inside'] for link in found):
            retained.append({'folder': folder.name, 'reason': 'Contains a link pointing outside its folder'})
            continue
        folders.append({'folder': folder.name, 'links': found})
    value = {'schema_version': 1, 'utc': datetime.now(timezone.utc).isoformat(), 'policy': 'docs/decisions/0006-retention.md',
             'folders': folders, 'retained': retained}
    path = ROOT / 'data/maintenance' / f'scratch-plan-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'plan': str(path), 'folders': len(folders), 'links': sum(len(f['links']) for f in folders),
                      'retained': retained}, indent=2))


def apply(plan_path):
    value = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    receipt = {'schema_version': 1, 'plan': str(plan_path), 'utc': datetime.now(timezone.utc).isoformat(),
               'folders': [], 'bytes': 0, 'faults': []}
    for entry in value['folders']:
        folder = SCRATCH / entry['folder']
        try:
            for link in entry['links']:
                native = filesystem_path(SCRATCH / link['path'])
                if not (os.path.islink(native) or os.path.isjunction(native)):
                    raise ValueError('Planned link changed: ' + link['path'])
                os.rmdir(native) if link['directory'] else os.unlink(native)  # Removes the link only.
            rows = manifest(SCRATCH, [folder])
            outcome = remove_manifest(SCRATCH, rows, clear_readonly=True)  # Test publications are read-only.
            remove_empty_parents(SCRATCH, rows)
            receipt['faults'].extend(remove_empty_tree(SCRATCH, folder))
            removed = set(outcome['removed'])
            size = sum(r['bytes'] for r in rows if r['path'] in removed)
            receipt['folders'].append({'folder': entry['folder'], 'files': len(removed), 'bytes': size})
            receipt['bytes'] += size
            receipt['faults'].extend(outcome['faults'])
        except (OSError, ValueError) as exc:
            receipt['faults'].append({'folder': entry['folder'], 'status': 'faulty', 'reason': str(exc)})
    path = ROOT / 'data/maintenance' / ('scratch-cleanup-' + Path(plan_path).stem.removeprefix('scratch-plan-') + '.json')
    path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': str(path), 'folders': len(receipt['folders']), 'bytes': receipt['bytes'],
                      'faults': receipt['faults'][:10]}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--plan', action='store_true')
    group.add_argument('--apply')
    args = parser.parse_args()
    plan() if args.plan else apply(args.apply)
