"""Owner-approved, bounded texture repairs with durable one-attempt receipts."""
import argparse
from contextlib import closing
from copy import deepcopy
from collections import Counter
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.config import load_project_config, venv_python
from local_asset_library.catalog import detail, digest
from local_asset_library.incremental import (working, update_record, inspection_input, run_inspection,
                                             ledger, checkpoint, stage_content, publish)
from local_asset_library.membership import records
from local_asset_library.publication import atomic_json, read_json
from local_asset_library.texture_repair import build_recipe, material_table
from local_asset_library.gpu_queue import lease

FOLDER = ROOT / 'data/texture-repairs/20261014'


def repair_plan():
    path = FOLDER / 'plan.json'
    if path.stat().st_size > 16 * 1024**2:
        raise RuntimeError('Repair plan exceeds its bounded size')
    return json.loads(path.read_text(encoding='utf-8'))


def storage(label):
    name = f'texture-repair-{label}-{uuid.uuid4().hex}.json'
    subprocess.run([str(venv_python(ROOT)), str(ROOT / 'scripts/storage-report.py'),
                    '--output', name], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    value = read_json(ROOT / 'data/storage' / name)
    base = read_json(ROOT / 'data/storage/texture-repair-before-20261014.json')['totals']['allocated_bytes']
    if value['status'] != 'passed' or value['totals']['allocated_bytes'] > 10 * 1024**3 or value['totals']['allocated_bytes'] - base > 2 * 1024**3:
        raise RuntimeError('Repair storage ceiling exceeded or measurement faulty; work retained')
    return {'receipt': name, 'allocated_bytes': value['totals']['allocated_bytes'], 'growth_bytes': value['totals']['allocated_bytes'] - base}


def prepare(config):
    if (FOLDER / 'plan.json').exists():
        return repair_plan()
    before = json.loads((FOLDER / 'before.json').read_text(encoding='utf-8'))
    textures = [p.relative_to(config.source_root).as_posix() for p in config.source_root.rglob('*')
                if p.is_file() and p.suffix.casefold() in {'.png', '.tga', '.jpg', '.jpeg'}]
    tables = [(p.relative_to(config.source_root).as_posix(), material_table(p))
              for p in config.source_root.rglob('MaterialList*.txt')]
    recipes, unresolved = {}, {}
    for identifier in before['targets']:
        r = before['records'][identifier]
        recipe, faults = build_recipe(config, r, textures, tables)
        if recipe:
            recipes[identifier] = recipe
            atomic_json(FOLDER / 'overrides' / (identifier + '.json'), recipe)
        else:
            unresolved[identifier] = faults
    # Cover subpacks and mapping types with a bounded representative sample.
    representatives, seen = [], set()
    for identifier, recipe in recipes.items():
        key = (recipe['source_path'].split('/')[0], tuple((b['path'], b['evidence']['kind']) for b in recipe['bindings']))
        if key not in seen and len(representatives) < 12:
            representatives.append(identifier)
            seen.add(key)
    # Ensure all recoverable packs appear even if Generic consumed the first slots.
    for pack in ('craftpix-free-packs', 'synty-part1'):
        candidate = next((k for k, v in recipes.items() if v['source_path'].startswith(pack + '/')), None)
        if candidate and candidate not in representatives:
            representatives.append(candidate)
    value = {'schema_version': 1, 'approved_targets': before['targets'], 'recipes': recipes,
             'unresolved': unresolved, 'representatives': representatives, 'bulk_review': 'pending',
             'budget': {'additional_bytes': 2*1024**3, 'total_bytes': 10*1024**3},
             'caption_failures_excluded': True, 'originals_modified': False}
    atomic_json(FOLDER / 'plan.json', value)
    return value


def render(config, phase):
    work = working(config)
    plan = repair_plan()
    if phase == 'bulk' and read_json(FOLDER / 'representatives-review.json').get('status') != 'technical_pass':
        raise RuntimeError('Representative visual checks required before bulk repairs')
    ids = plan['representatives'] if phase == 'representatives' else list(plan['recipes'])
    atomic_json(FOLDER / f'{phase}-storage-before.json', storage(phase + '-before'))
    with lease(config, 'manual-texture-repairs', timeout=0, resource='operations'):
        for n, identifier in enumerate(ids, 1):
            receipt = FOLDER / 'outcomes' / (identifier + '.json')
            if receipt.exists():
                continue  # Completed and failed attempts are never repeated on resume.
            r = detail(work, identifier)
            recipe = plan['recipes'][identifier]
            if r.get('texture_repair') and r['texture_repair'] != recipe:
                raise RuntimeError('Conflicting repair override; explicit review required')
            r['texture_repair'] = recipe
            r.setdefault('texture_repair_history', {'original_record_receipt': 'data/texture-repairs/20261014/before.json',
                                         'inspection_run': deepcopy(r.get('inspection_run')),
                                         'dependencies': deepcopy(r['dependencies']),
                                         'stage_faults': deepcopy(r.get('stage_faults'))})
            update_record(work, r)
            atomic_json(receipt, {'asset_id': identifier, 'status': 'running', 'attempt': 1})
            print(f"Repair {n}/{len(ids)}: {r['pack_id']} / {r['display_name']}", flush=True)
            try:
                fp = inspection_input(work, r)[3]
                outcome = run_inspection(work, r, fp, timeout=600)
                updated = detail(work, identifier)
                if outcome['status'] == 'complete':
                    # Only stale Blender-discovered image paths superseded by this
                    # complete repair are moved into the retained history above.
                    updated['dependencies'] = [d for d in updated['dependencies'] if not (
                        d.get('inspection_version') and d.get('from') == recipe['source_path']
                        and d.get('required_for_render') and d.get('status') != 'available')]
                    from local_asset_library.retrieval import source_check
                    source_check(work, updated)
                    updated.get('stage_faults', {}).pop('inspection', None)
                update_record(work, updated)
                final_fp = inspection_input(work, updated)[3]
                updated['inspection_run']['fingerprint'] = final_fp
                update_record(work, updated)
                with closing(ledger(config)) as db:
                    checkpoint(db, identifier, 'inspection', final_fp, outcome['status'],
                               {**outcome, 'fault_content': stage_content(work, updated, 'inspection')})
            except (OSError, ValueError, RuntimeError, KeyError, TimeoutError) as exc:
                outcome = {'status': 'failed', 'error': str(exc), 'type': type(exc).__name__}
                updated = detail(work, identifier)
                updated['processing']['previews'] = 'failed'
                updated.setdefault('stage_faults', {})['inspection'] = outcome
                update_record(work, updated)
                with closing(ledger(config)) as db:
                    checkpoint(db, identifier, 'inspection', digest(recipe), 'failed',
                               {**outcome, 'fault_content': stage_content(work, updated, 'inspection')})
            atomic_json(receipt, {'asset_id': identifier, 'attempt': 1, **outcome})
            if n % 40 == 0:
                atomic_json(FOLDER / f'{phase}-storage-{n}.json', storage(phase + '-' + str(n)))
    atomic_json(FOLDER / f'{phase}-storage-after.json', storage(phase + '-after'))
    return dict(Counter(read_json(p)['status'] for p in (FOLDER / 'outcomes').glob('*.json')))


def index(config):
    from local_asset_library.embedding_backend import EmbeddingBackend
    from local_asset_library.library_index import index_library
    work = working(config)
    with lease(config, 'texture-repair-index', timeout=0, resource='operations'), lease(config, 'batch-texture-repair-index'):
        atomic_json(FOLDER / 'index-storage-before.json', storage('index-before'))
        # Existing clients already return dependency evidence. Include the actual
        # import bindings there, in addition to the newer top-level handoff field.
        for receipt in (FOLDER / 'outcomes').glob('*.json'):
            if read_json(receipt)['status'] != 'complete':
                continue
            record = detail(work, receipt.stem)
            recipe = record['texture_repair']
            for dependency in record['dependencies']:
                bindings = [b for b in recipe['bindings'] if b['path'] == dependency.get('path')
                            and dependency.get('from') == recipe['source_path']]
                if bindings:
                    dependency['texture_overrides'] = [{
                        **{k:b[k] for k in ('image','original_path','role','preserve_supplied_alpha') if k in b},
                        'material_users': next((t['render_users'] for t in record['technical']['textures']
                                                if t['name'] == b['image']), []),
                        'original_source_unmodified': True} for b in bindings]
                    dependency['evidence'] = 'Library texture override for unchanged source; apply these bindings when importing.'
            update_record(work, record)
        backend = EmbeddingBackend(work)
        try:
            while index_library(work, dry_run=True)['pending']:
                result = index_library(work, backend, limit=250)
                atomic_json(FOLDER / ('index-' + uuid.uuid4().hex + '.json'), result)
                print(json.dumps({k:v for k,v in result.items() if k not in {'outcomes','resources'}}), flush=True)
                storage('index-batch')
            projected = sum(work.output_path('data', n).stat().st_size for n in ('catalog.sqlite','embeddings/index.sqlite'))
            measured = storage('before-preview-publication')
            if measured['growth_bytes'] + projected > 2 * 1024**3 or measured['allocated_bytes'] + projected > 10 * 1024**3:
                raise RuntimeError('Projected snapshot exceeds approved repair storage')
            value = publish(config)
            atomic_json(FOLDER / 'preview-publication.json', value)
        finally:
            backend.model.to('cpu')
            backend.model = None
            import gc
            gc.collect()
            backend.torch.cuda.empty_cache()
    recovered = [p.stem for p in (FOLDER/'outcomes').glob('*.json') if read_json(p)['status']=='complete']
    atomic_json(FOLDER / 'recovered-asset-ids.json', recovered)
    return {'recovered': len(recovered), 'generation': value['generation'], 'storage': storage('after-preview-publication')}


parser = argparse.ArgumentParser()
parser.add_argument('operation', choices=['prepare', 'representatives', 'bulk', 'index'])
args = parser.parse_args()
config = load_project_config(ROOT)
if args.operation == 'prepare':
    value = prepare(config)
    print(json.dumps({'eligible': len(value['recipes']), 'unresolved': len(value['unresolved']),
                      'packs': dict(Counter(v['source_path'].split('/')[0] for v in value['recipes'].values())),
                      'representatives': value['representatives']}))
elif args.operation == 'index':
    print(json.dumps(index(config)))
else:
    print(json.dumps(render(config, args.operation)))
