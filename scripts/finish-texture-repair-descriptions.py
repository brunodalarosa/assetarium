"""Finish the explicitly approved repaired-ID description run in the background."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.publication import atomic_json, read_json
from local_asset_library.config import load_config
from local_asset_library.overnight import run_path

folder = ROOT / 'data/texture-repairs/20261014'
intent = folder / 'description-launch-intent.json'
follow_existing = sys.argv[1:] == ['--follow-existing-run']
if sys.argv[1:] and not follow_existing:
    raise RuntimeError('Unknown finalization option')
if intent.exists() and not follow_existing:
    raise RuntimeError('A description launch was already recorded; inspect/resume its saved run instead of retrying faults')
if read_json(folder / 'preview-verification.json')['status'] != 'passed':
    raise RuntimeError('Preview publication preservation check has not passed')
before = read_json(ROOT / 'data/storage/texture-repair-before-20261014.json')['totals']['allocated_bytes']
preflight_receipt = ('texture-repair-before-finalization-' + uuid.uuid4().hex + '.json'
                     if follow_existing else 'texture-repair-before-descriptions-20261014.json')
command = [str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'scripts/storage-report.py'),
           '--output', preflight_receipt]
subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
measured = read_json(ROOT / 'data/storage' / preflight_receipt)
allocated = measured['totals']['allocated_bytes']
reserve = 512 * 1024**2
if measured['status'] != 'passed' or allocated + reserve > 10 * 1024**3 or allocated - before + reserve > 2 * 1024**3:
    raise RuntimeError('Conservative description reserve exceeds the approved combined repair budget; all work retained')
ids = read_json(folder / 'recovered-asset-ids.json')
command = [str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'scripts/overnight-descriptions.py'),
           '--new-run', '--asset-ids-file', str(folder / 'recovered-asset-ids.json'), '--peak-reserve-mib', '512']
if not follow_existing:
    atomic_json(intent, {'status': 'starting', 'selected_assets': len(ids), 'pid': os.getpid(),
                         'selection': 'data/texture-repairs/20261014/recovered-asset-ids.json', 'originals_modified': False})
env = os.environ.copy()
env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
try:
    c = load_config(ROOT / 'config.example.toml', ROOT)
    latest = read_json(ROOT / 'data/overnight-descriptions/latest.json')
    if follow_existing:
        identifier = latest['run_id']
        path = run_path(c, identifier)
        saved = read_json(path / 'plan.json')
        if set(saved['plan']['asset_ids'] or []) != set(ids):
            raise RuntimeError('Existing run is not the approved recovered-ID selection')
        atomic_json(folder / 'application-size-fix-followup.json', {
            'status': 'waiting_for_existing_run', 'run_id': identifier, 'pid': os.getpid(),
            'reason': 'Preservation receipt is 1,417,255 bytes; bounded reader raised to 4 MiB.',
            'model_attempts_repeated': False})
        deadline = time.monotonic() + 12 * 3600
        while True:
            state = read_json(path / 'state.json')
            if state['phase'] == 'complete':
                break
            if state['status'] == 'blocked':
                from local_asset_library.overnight import remaining
                if ('Managed manifest exceeds its bounded size' not in (state.get('error') or '')
                        or remaining(c, identifier)):
                    raise RuntimeError('Existing run stopped for a different fault; no automatic retry')
                # Wait for the original coordinator/wrapper to release its lease.
                time.sleep(5)
                result = subprocess.run([str(ROOT / '.venv/Scripts/python.exe'),
                    str(ROOT / 'scripts/overnight-descriptions.py'), '--resume', identifier], cwd=ROOT, env=env)
                if result.returncode:
                    raise RuntimeError('Saved-run publication resume failed; no model retry requested')
                break
            if time.monotonic() > deadline:
                raise RuntimeError('Finalization wait expired; existing run and evidence preserved')
            time.sleep(2)
        latest = {'run_id': identifier}
    else:
        result = subprocess.run(command, cwd=ROOT, env=env)
        if result.returncode:
            raise RuntimeError('Description coordinator failed; inspect its saved state before resuming')
        latest = read_json(ROOT / 'data/overnight-descriptions/latest.json')
        path = run_path(c, latest['run_id'])
    plan = read_json(path / 'plan.json')
    if set(plan['plan']['asset_ids']) != set(ids):
        raise RuntimeError('Saved description selection does not match recovered assets')
    subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'scratch/verify-texture-repairs.py'),
                    'final-verification'], cwd=ROOT, env=env, check=True)
    subprocess.run([str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'scripts/storage-report.py'),
                    '--output', 'texture-repair-complete-20261014.json'], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    final_storage = read_json(ROOT / 'data/storage/texture-repair-complete-20261014.json')
    if (final_storage['status'] != 'passed' or final_storage['totals']['allocated_bytes'] > 10 * 1024**3
            or final_storage['totals']['allocated_bytes'] - before > 2 * 1024**3):
        raise RuntimeError('Final repair storage check failed; work preserved')
    report = read_json(folder / 'final-verification.json')
    summary = json.loads((path / 'summary.json').read_text(encoding='utf-8'))
    atomic_json(folder / 'completion.json', {'status': 'complete_with_retained_faults',
                 'run_id': latest['run_id'], 'generation': report['generation'],
                 'recovered': report['recovered'], 'retained_texture_faults': report['retained_faults'],
                 'description_results': summary['results'], 'checks': report['checks'],
                 'storage': final_storage['totals'], 'owner_accuracy_artistic_review': 'pending'})
    atomic_json(intent, {'status': 'complete', 'run_id': latest['run_id'], 'selected_assets': len(ids),
                         'completion_receipt': 'data/texture-repairs/20261014/completion.json'})
    print('Repair descriptions, indexing, publication and preservation verification completed.', flush=True)
except BaseException as exc:
    atomic_json(folder / 'description-finalization-fault.json', {'status': 'faulty', 'reason': str(exc),
                 'policy': 'Work preserved; no automatic retry of failed attempts.'})
    raise
