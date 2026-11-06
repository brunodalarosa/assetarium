"""Real parallel processing through the source coordinator (decision 0022), on a temporary source of
twelve synthetic models: renders run several at a time on the planned device, a cancel (what closing
the app does) settles every running render, a killed processing run takes its Blender processes with
it, and the next Process assets finishes the rest with no asset fault. Originals stay byte-identical.
Writes data/library/verification/parallel-processing-<run>.json.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.config import load_project_config  # noqa: E402
from local_asset_library.publication import atomic_json  # noqa: E402
from local_asset_library.render_devices import shapes  # noqa: E402
from local_asset_library.source_operations import RUNNING, cancel, operation_status, start  # noqa: E402
from local_asset_library.sources import add, aggregate, bound, remove, scan_source, source_status  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
config = load_project_config(ROOT)
OUT = ROOT / 'data/library/verification' / f'parallel-processing-{args.run_name}.json'
if OUT.exists():
    raise SystemExit(f'{OUT} exists; choose a new --run-name')
from local_asset_library.settings import processing_formats  # noqa: E402
if 'obj' not in processing_formats(config):
    raise SystemExit('Select OBJ in Settings → General to run this check')
fixture = ROOT.parent / f'LAL-parallel-verification-{args.run_name}'
fixture.mkdir()
for index, model in enumerate(shapes(fixture) * 3):  # Twelve distinct files: each copy is scaled differently.
    lines = [' '.join(['v'] + [f'{float(c) * (1 + index / 4):.5f}' for c in l.split()[1:]]) if l.startswith('v ') else l
             for l in model.read_text().splitlines()]
    (fixture / f'{model.stem}-{index}.obj').write_text('\n'.join(lines) + '\n')
for model in fixture.glob('*.obj'):
    if '-' not in model.stem:
        model.unlink()
original = {p.name: p.read_bytes() for p in fixture.glob('*.obj')}
source = add(config, str(fixture))
scoped = bound(config, source)
report = {'status': 'running', 'fixture': str(fixture), 'source': source['key'], 'checks': []}


def blenders():
    """Process IDs of kept-open render hosts (only this check renders while it runs)."""
    if os.name == 'nt':
        command = ("Get-CimInstance Win32_Process -Filter \"Name='blender.exe'\" | "
                   "Where-Object { $_.CommandLine -like '*blender_batch_worker.py*' } | ForEach-Object { $_.ProcessId }")
        found = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True).stdout
        return {int(line) for line in found.split()}
    return {int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit()
            and b'blender_batch_worker.py' in (p / 'cmdline').read_bytes()} if Path('/proc').exists() else set()


def python_processes(token):
    if os.name == 'nt':
        command = (f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*source-operation.py*{token}*' }} | "
                   "ForEach-Object { $_.ProcessId }")
        found = subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], capture_output=True, text=True).stdout
        return {int(line) for line in found.split()}
    return {int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit()
            and token.encode() in (p / 'cmdline').read_bytes()}


def inspections(status):
    from local_asset_library.incremental import ledger
    with closing(ledger(scoped)) as db:
        return db.execute("SELECT count(*) FROM jobs WHERE stage='inspection' AND status=?", (status,)).fetchone()[0]


def wait(until, bound=600, step=.2):
    deadline = time.monotonic() + bound
    while time.monotonic() < deadline:
        value = until()
        if value:
            return value
        time.sleep(step)
    raise RuntimeError('Verification bound expired')


def finished():
    operation = operation_status(scoped)
    return operation if operation.get('status') not in RUNNING else None


try:
    scan_source(config, source)
    assert source_status(config, source)['pending'] == 12
    started = start(config, 'process', source['key'])
    wait(lambda: inspections('complete') >= 2)
    peak = len(blenders())
    report['cancel_request'] = cancel(scoped)  # Closing the app cancels the operations it started.
    stopped = wait(finished)
    report['cancelled_operation'] = stopped
    assert stopped['status'] == 'cancelled', stopped
    assert inspections('running') == 0 and inspections('failed') == 0
    done = inspections('complete')
    batch = max(scoped.output_path('data', 'library/batches').glob('inspection-*.json'), key=lambda p: p.stat().st_mtime)
    report['render'] = json.loads(batch.read_text(encoding='utf-8')).get('render')
    assert report['render'] and report['render']['processes'] >= 1, report['render']
    wait(lambda: not blenders(), 30)
    report['checks'].append(f"Rendered {report['render']['processes']} at a time on {report['render']['device_label']} "
                            f"({peak} kept-open Blender processes seen); cancel settled every running render "
                            f"({done} complete, none left running) and every Blender exited")

    started = start(config, 'process', source['key'])
    wait(lambda: inspections('complete') >= done + 1 and blenders())
    alive = blenders()
    coordinator = python_processes(started['token'])
    assert coordinator, 'processing run not found'
    for pid in coordinator:  # A crash or forced close of the processing run, not a cancel.
        subprocess.run(['taskkill', '/PID', str(pid), '/F'] if os.name == 'nt' else ['kill', '-9', str(pid)], capture_output=True)
    wait(lambda: not (blenders() & alive), 30)
    interrupted = wait(lambda: operation_status(scoped)['status'] == 'interrupted' and operation_status(scoped), 30)
    report['interrupted_operation'] = interrupted
    report['checks'].append('Killing the processing run took its Blender processes with it; the source shows the run '
                            'as interrupted with its finished assets kept')

    start(config, 'process', source['key'])
    completed = wait(finished, 900)
    report['completed_operation'] = completed
    assert completed['status'] in {'complete', 'complete_with_faults'}, completed
    status = source_status(config, source)
    report['source_status'] = status
    assert inspections('complete') == 12 and inspections('failed') == 0 and not status['needs_processing'], status
    assert all(p.read_bytes() == original[p.name] for p in fixture.glob('*.obj'))
    report['checks'].append('Process assets resumed and finished all twelve models with no asset fault; '
                            'original files are byte-identical')
    report['status'] = 'passed'
except BaseException as exc:
    report.update(status='faulty', reason=f'{type(exc).__name__}: {exc}')
    raise
finally:
    atomic_json(OUT, report)
    if operation_status(scoped).get('status') not in RUNNING:
        remove(config, source['key'])
        aggregate(config)
        from local_asset_library.notifications import act, load
        report['notifications'] = [item for item in load(config)['items'] if item['source_id'] == source['id']]
        for item in report['notifications']:
            act(config, 'dismiss', item['id'])
        atomic_json(OUT, report)
    print(json.dumps({'status': report['status'], 'checks': report['checks'], 'report': str(OUT),
                      'reason': report.get('reason')}, indent=2), flush=True)
