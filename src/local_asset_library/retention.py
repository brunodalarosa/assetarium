"""Owner-approved retention of superseded generated data (decision 0006).

Keeps the active publication plus the two newest older generations, and the
ten newest desktop launch audit folders. Everything else in those exact
locations is removed through the reviewed manifest flow: links are refused,
each file is re-hashed immediately before removal, changed files are retained
as faults, and a receipt is written under ``data/maintenance/``.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from .config import ConfigError
from .maintenance_files import manifest, remove_empty_parents, remove_empty_tree, remove_manifest

KEEP_GENERATIONS = 2
KEEP_GUI_RUNS = 10
GENERATION = re.compile(r'v_[0-9a-f]{32}')


def _newest_first(paths):
    return sorted(paths, key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)


def generation_targets(config, keep=KEEP_GENERATIONS):
    """Superseded ``v_*`` generations of one publication root (central or source)."""
    from .publication import read_json
    root = config.output_path('data', 'library/generations')
    active_path = config.output_path('data', 'library/active.json')
    if not root.is_dir() or not active_path.is_file():
        return root, []
    active = read_json(active_path).get('generation')
    older = [p for p in root.iterdir() if p.is_dir() and GENERATION.fullmatch(p.name) and p.name != active]
    return root, _newest_first(older)[keep:]


def run_targets(config, keep=KEEP_GUI_RUNS):
    root = config.output_path('data', 'gui/runs')
    if not root.is_dir():
        return root, []
    return root, _newest_first([p for p in root.iterdir() if p.is_dir()])[keep:]


def retire(root, targets):
    """Remove whole target trees after a fresh manifest; returns a compact outcome."""
    if not targets:
        return {'root': str(root), 'targets': [], 'removed_files': 0, 'bytes': 0, 'faults': []}
    rows = manifest(root, targets)
    outcome = remove_manifest(root, rows, clear_readonly=True)  # Published generations are read-only.
    parents = remove_empty_parents(root, rows)
    faults = outcome['faults'] + parents['faults']
    for target in targets:
        faults.extend(remove_empty_tree(root, target))  # Empty directories without files.
    removed = set(outcome['removed'])
    return {'root': str(root), 'targets': [t.name for t in targets], 'removed_files': len(removed),
            'bytes': sum(r['bytes'] for r in rows if r['path'] in removed), 'faults': faults}


def _drop_stale_projections(config, retired):
    """Combined-publication shortcuts that point at a retired generation are rebuilt on demand."""
    from .publication import read_json
    folder = config.project_root / 'data/library/combined-publications'
    stale = []
    if retired and folder.is_dir():
        for path in folder.glob('*.json'):
            try:
                if read_json(path).get('generation') in retired:
                    stale.append(path)
            except (OSError, ValueError):
                continue
    return retire(folder, stale) if stale else None


def write_receipt(config, kind, outcomes):
    receipt = {'schema_version': 1, 'kind': kind, 'utc': datetime.now(timezone.utc).isoformat(),
               'policy': 'Assetarium KnowledgeBase/Decisions/0006-retention.md', 'outcomes': outcomes,
               'bytes': sum(o.get('bytes', 0) for o in outcomes if o),
               'faults': [f for o in outcomes if o for f in o.get('faults', [])]}
    path = config.project_root / 'data/maintenance' / f'{kind}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


def retire_generations(config, sources=True):
    """Central generations, and each registered source's, after a publication."""
    from .sources import registry, bound
    outcomes, retired = [], set()
    scopes = [config] + ([bound(config, s) for s in registry(config)['sources'] + registry(config).get('detached', [])]
                         if sources and config.sources_registry and not config.source_key else [])
    for scoped in scopes:
        try:
            root, targets = generation_targets(scoped)
            outcome = retire(root, targets)
            retired.update(outcome['targets'])
            outcomes.append(outcome)
        except (OSError, ValueError) as exc:
            outcomes.append({'root': str(getattr(scoped, 'metadata_root', None) or scoped.project_root),
                             'targets': [], 'bytes': 0, 'faults': [{'status': 'faulty', 'reason': str(exc)}]})
    if not config.source_key:
        outcomes.append(_drop_stale_projections(config, retired))
    outcomes = [o for o in outcomes if o]
    if any(o['targets'] or o['faults'] for o in outcomes):
        return write_receipt(config, 'generation-retention', outcomes)
    return None


def retire_gui_runs(config):
    root, targets = run_targets(config)
    if not targets:
        return None
    try:
        return write_receipt(config, 'gui-run-retention', [retire(root, targets)])
    except (OSError, ValueError, ConfigError) as exc:
        return write_receipt(config, 'gui-run-retention', [{'root': str(root), 'targets': [], 'bytes': 0,
                                                            'faults': [{'status': 'faulty', 'reason': str(exc)}]}])
