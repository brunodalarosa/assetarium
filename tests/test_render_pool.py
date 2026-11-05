"""Parallel kept-open Blender renders: planning limits, slot faults, parallel processing (decision 0022)."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path

import subprocess
import sys
import threading
import time

import numpy as np
from PIL import Image
import pytest

from local_asset_library import incremental, inspection, render_pool
from local_asset_library.config import ConfigError
from local_asset_library.incremental import ledger, process, working
from local_asset_library.result_store import result_path
from local_asset_library.membership import records
from test_blender_integration import BLENDER, small_fixture  # noqa: F401 -- real-Blender fixture
from test_incremental import library  # noqa: F401 -- shared synthetic library fixture

GIB = render_pool.GIB


def test_plan_follows_cores_and_limits_only_lower_it(library):
    config, _ = library
    auto = render_pool.plan(config, available=64 * GIB, count=32)
    assert (auto['processes'], auto['threads'], auto['reason']) == (4, 8, 'automatic for this processor')
    assert render_pool.plan(config, available=64 * GIB, count=8)['processes'] == 1
    assert render_pool.plan(config, available=None, count=32)['processes'] == 4
    render_pool.save(config, 2, None)
    assert render_pool.plan(config, available=64 * GIB, count=32)['processes'] == 2
    assert render_pool.plan(config, available=64 * GIB, count=32)['reason'] == 'your limit'
    render_pool.save(config, 8, None)  # A higher limit never passes the best count.
    assert render_pool.plan(config, available=64 * GIB, count=32)['processes'] == 4


def test_plan_memory_allowance_never_passes_free_memory(library):
    config, _ = library
    low = render_pool.plan(config, available=2 * GIB, count=32)
    assert (low['processes'], low['reason']) == (1, 'memory free now')
    render_pool.save(config, None, 2)
    owner = render_pool.plan(config, available=64 * GIB, count=32)
    assert (owner['processes'], owner['reason']) == (2, 'your memory allowance')
    render_pool.save(config, None, 32)  # Overnight allowance above what is free stays within free memory.
    capped = render_pool.plan(config, available=3 * GIB, count=32)
    assert (capped['processes'], capped['reason'], capped['allowance_bytes']) == (2, 'memory free now', 2 * GIB)


@pytest.mark.parametrize('processes,memory', [(0, None), (9, None), (True, None), ('2', None), (None, 0), (None, 1.5)])
def test_invalid_limits_are_refused(library, processes, memory):
    config, _ = library
    with pytest.raises(ConfigError):
        render_pool.save(config, processes, memory)
    assert render_pool.saved(config) == {'device': None, 'processes': None, 'memory_gib': None}


FAKE_HOST = """
import os, sys, time
for line in sys.stdin:
    job = line.strip()
    name = os.path.basename(job)
    print('starting', name, flush=True)
    open(job + '.started', 'w').write(str(os.getpid()))
    if name == 'hang':
        time.sleep(60)
    if name == 'crash':
        os._exit(3)
    open(job + '.pid', 'w').write(str(os.getpid()))
    print('LAL_JOB_DONE', flush=True)
"""


@pytest.fixture
def fake_blender(library, monkeypatch, tmp_path):
    config, _ = library
    host = tmp_path / 'host.py'
    host.write_text(FAKE_HOST)
    monkeypatch.setattr(inspection, 'blender_command', lambda blender, *args: [sys.executable, '-u', str(host)])
    worker = config.project_root / 'src/local_asset_library/blender_worker.py'
    return config, worker, tmp_path


def test_slot_keeps_blender_open_and_isolates_timeouts_and_crashes(fake_blender, monkeypatch):
    config, worker, folder = fake_blender
    pid = lambda name: (folder / (name + '.pid')).read_text()
    with render_pool.opened(config, 1, 32) as pool:
        first = pool.run('blender', worker, folder / 'a', 10)
        assert first['returncode'] == 0 and not first['timed_out'] and 'starting a' in first['output']
        assert pool.run('blender', worker, folder / 'b', 10)['returncode'] == 0
        assert pid('a') == pid('b')  # One Blender served both jobs.
        hung = pool.run('blender', worker, folder / 'hang', 1)
        assert hung['timed_out'] and 'starting hang' in hung['output']
        assert pool.run('blender', worker, folder / 'c', 10)['returncode'] == 0 and pid('c') != pid('b')
        crashed = pool.run('blender', worker, folder / 'crash', 10)
        assert crashed['returncode'] == 3 and not crashed['timed_out'] and 'Blender exited' in crashed['output']
        assert pool.run('blender', worker, folder / 'd', 10)['returncode'] == 0 and pid('d') != pid('c')
        monkeypatch.setattr(render_pool, 'RECYCLE_AFTER', 1)
        pool.run('blender', worker, folder / 'e', 10)
        assert pid('e') != pid('d')
    assert all(slot.process is None for slot in pool.slots)


def test_repair_workers_run_one_blender_per_job_with_thread_share(fake_blender, monkeypatch):
    config, worker, folder = fake_blender
    commands = []
    monkeypatch.setattr(inspection, 'blender_command', lambda blender, *args: ['blender', *args])
    monkeypatch.setattr(inspection, 'run_process', lambda command, *a: commands.append(command) or {'returncode': 0})
    with render_pool.opened(config, 2, 16) as pool:
        pool.run('blender', worker.with_name('blender_repair_worker.py'), folder / 'job.json', 10)
    assert commands and commands[0][1:3] == ['--threads', '16'] and 'blender_repair_worker.py' in commands[0][-3]


def test_without_an_open_pool_each_job_gets_its_own_blender(fake_blender, monkeypatch):
    config, worker, folder = fake_blender
    commands = []
    monkeypatch.setattr(inspection, 'run_process', lambda command, *a: commands.append(command) or {'returncode': 0})
    render_pool.run(config, 'blender', worker, folder / 'job.json', 10)
    assert len(commands) == 1


@pytest.fixture
def parallel(library, monkeypatch):
    config, _ = library
    monkeypatch.setattr(render_pool, 'cores', lambda: 32)
    monkeypatch.setattr(render_pool, 'available_memory', lambda: 64 * GIB)
    render_pool.save(config, 3, None)
    return config


def test_parallel_inspection_runs_up_to_the_planned_processes(parallel, monkeypatch):
    config = parallel
    active, peak, lock = [0], [0], threading.Lock()

    def inspect(work, record, fp, resolution=640, formats=None):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(.2)
        with lock:
            active[0] -= 1
        if record['display_name'] == 'item1' and record['pack_id'].endswith('one'):
            raise RuntimeError('synthetic geometry fault')
        return {'status': 'complete'}
    monkeypatch.setattr(incremental, 'run_inspection', inspect)
    report = process(config, 'inspection', 6)
    assert report['render'] == {'processes': 3, 'threads': 10, 'reason': 'your limit', 'device_label': 'CPU'}
    assert peak[0] == 3 and len(report['outcomes']) == 6
    assert (report['complete'], report['failed']) == (5, 1)  # One asset's fault never touches the others.
    with closing(ledger(config)) as db:
        rows = dict(db.execute("SELECT status, count(*) FROM jobs WHERE stage='inspection' GROUP BY status").fetchall())
    assert rows == {'complete': 5, 'failed': 1}


def test_parallel_cancel_finishes_running_renders_and_starts_no_more(parallel, monkeypatch):
    config = parallel
    started, stop = [], [False]

    def inspect(work, record, fp, resolution=640, formats=None):
        started.append(record['asset_id'])
        time.sleep(.2)
        return {'status': 'complete'}

    def progress(identifier, completed, total):
        if identifier is None and completed >= 1:
            stop[0] = True
    monkeypatch.setattr(incremental, 'run_inspection', inspect)
    report = process(config, 'inspection', 6, cancelled=lambda: stop[0], progress=progress)
    assert report['cancelled'] and 1 <= len(started) < 6
    assert len(report['outcomes']) == len(started)  # Every running render was settled before stopping.
    with closing(ledger(config)) as db:
        assert db.execute("SELECT count(*) FROM jobs WHERE status='complete'").fetchone()[0] == len(started)
    monkeypatch.setattr(incremental, 'run_inspection', lambda *a, **k: {'status': 'complete'})
    resumed = process(config, 'inspection', 6)
    assert len(resumed['outcomes']) == 6 - len(started) and resumed['retained'] == {'complete': len(started)}


def test_interrupted_parallel_run_resumes_unsettled_assets(parallel, monkeypatch):
    config = parallel
    calls = []

    def inspect(work, record, fp, resolution=640, formats=None):
        calls.append(record['asset_id'])
        if len(calls) == 2:
            raise KeyboardInterrupt('app closed')
        return {'status': 'complete'}
    monkeypatch.setattr(incremental, 'run_inspection', inspect)
    with pytest.raises(KeyboardInterrupt):
        process(config, 'inspection', 6)
    monkeypatch.setattr(incremental, 'run_inspection', lambda *a, **k: {'status': 'complete'})
    resumed = process(config, 'inspection', 6)
    with closing(ledger(config)) as db:
        assert db.execute("SELECT count(*) FROM jobs WHERE status='complete'").fetchone()[0] == 6
    assert resumed['failed'] == 0


def test_result_cut_off_by_an_interruption_is_rendered_again(library, monkeypatch):
    config, _ = library
    work = working(config)
    record = records(work)[0]
    fp = incremental.inspection_input(work, record)[3]
    output = work.output_path('data', result_path('inspection', fp))
    output.mkdir(parents=True)
    (output / 'result.json').write_text('{"status": "comp')
    monkeypatch.setattr(incremental, '_blender_runtime', {})
    monkeypatch.setattr(incremental, 'discover_blender', lambda c: (Path('blender'), {'version_output': 'Blender'}))
    monkeypatch.setattr(render_pool, 'run', lambda *a: (_ for _ in ()).throw(RuntimeError('rendered again')))
    with pytest.raises(RuntimeError, match='rendered again'):
        incremental.run_inspection(work, record, fp)
    assert not (output / 'result.json').exists() and len(list(output.glob('result.interrupted-*.json'))) == 1


CUBE = "\n".join(["v -1 -1 -1", "v 1 -1 -1", "v 1 1 -1", "v -1 1 -1", "v -1 -1 1", "v 1 -1 1", "v 1 1 1", "v -1 1 1",
                  "f 1 2 3 4", "f 5 8 7 6", "f 1 5 6 2", "f 2 6 7 3", "f 3 7 8 4", "f 5 1 4 8"]) + "\n"
WEDGE = "v 0 0 0\nv 2 0 0\nv 0 1 0\nv 0 0 3\nf 1 3 2\nf 1 2 4\nf 1 4 3\nf 2 3 4\n"


def test_kept_open_blender_matches_one_blender_per_asset(small_fixture):
    config = small_fixture
    (config.source_root / 'cube.obj').write_text(CUBE)
    (config.source_root / 'wedge.obj').write_text(WEDGE)

    def job(name, run):
        source = config.source_root / f'{name}.obj'
        output = config.output_path('data', f'{run}/{name}')
        task = output / 'job.json'
        output.mkdir(parents=True)
        task.write_text(json.dumps({"asset_id": name, "project_root": str(config.project_root),
            "source_root": str(config.source_root), "source_path": f'{name}.obj', "format": "obj",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "output": str(output), "resolution": 320}))
        return task, output

    worker = Path(render_pool.__file__).with_name('blender_worker.py')
    single = {}
    for name in ('cube', 'wedge'):
        task, output = job(name, 'single')
        assert render_pool.run(config, BLENDER, worker, task, 120)['returncode'] == 0
        single[name] = output
    with render_pool.opened(config, 1, 8) as pool:  # One kept-open Blender renders both, in order.
        kept = {}
        for name in ('cube', 'wedge'):
            task, output = job(name, 'kept')
            process = pool.run(BLENDER, worker, task, 120)
            assert process['returncode'] == 0, process['output']
            kept[name] = output
    for name in ('cube', 'wedge'):
        a, b = (json.loads((folder[name] / 'result.json').read_text()) for folder in (single, kept))
        assert a['status'] == b['status'] == 'complete', (a['errors'], b['errors'])
        assert a['technical'] == b['technical'] and a['render_settings'] == b['render_settings']
        for left, right in zip(a['previews'], b['previews']):
            pixels = [np.asarray(Image.open(folder[name] / view['filename'])) for folder, view in
                      ((single, left), (kept, right))]
            assert np.array_equal(*pixels), (name, left['view_label'])


def test_pool_waits_for_a_running_render_when_memory_runs_low(fake_blender, monkeypatch):
    config, worker, folder = fake_blender
    memory = [64 * GIB]
    monkeypatch.setattr(render_pool, 'available_memory', lambda: memory[0])
    with render_pool.opened(config, 2, 16) as pool:
        pool.busy = 1  # Another render is running and memory is nearly gone.
        memory[0] = render_pool.HEADROOM // 2
        waiter = threading.Thread(target=pool.run, args=('blender', worker, folder / 'late', 10))
        waiter.start()
        time.sleep(1)
        assert not (folder / 'late.pid').exists()
        pool.busy = 0  # The running render finished: the waiting job starts, even with little memory.
        waiter.join(10)
        assert (folder / 'late.pid').exists()


PARENT = """
import sys, threading, time
sys.path.insert(0, sys.argv[1])
from local_asset_library import inspection, render_pool
from local_asset_library.config import Config
from pathlib import Path
inspection.blender_command = lambda blender, *args: [sys.executable, '-u', sys.argv[2]]
config = Config(Path(sys.argv[3]), Path(sys.argv[6]), None)
with render_pool.opened(config, 1, 8) as pool:
    threading.Thread(target=pool.run, args=('blender', Path(sys.argv[4]), sys.argv[5], 600), daemon=True).start()
    time.sleep(600)
"""


def test_blender_dies_with_the_processing_run(fake_blender):
    """Closing or killing the processing run never leaves a Blender writing for the resumed run."""
    config, worker, folder = fake_blender
    parent = folder / 'parent.py'
    parent.write_text(PARENT)
    job = folder / 'hang'
    run = subprocess.Popen([sys.executable, str(parent), str(Path(render_pool.__file__).parents[1]), str(folder / 'host.py'),
                            str(config.project_root), str(worker), str(job), str(config.source_root)])
    try:
        for _ in range(100):
            if (folder / 'hang.started').exists():
                break
            time.sleep(.1)
        child = int((folder / 'hang.started').read_text())
    finally:
        run.kill()
        run.wait()
    from local_asset_library.gpu_queue import process_alive
    for _ in range(50):
        if not process_alive(child):
            break
        time.sleep(.1)
    assert not process_alive(child)


def saved_speed_test(config, chosen='HIP:gpu0', gpu_best=2, peak=2 * GIB):
    """A saved speed test for this configuration's Blender."""
    from local_asset_library import render_devices
    gpu = {'backend': 'HIP', 'id': 'gpu0', 'name': 'Test GPU'}
    value = {'schema_version': 1, 'blender': render_devices.blender_identity(config), 'devices': [gpu], 'cores': 32,
             'chosen': chosen, 'utc': '2026-10-26T12:00:00+00:00', 'elapsed_seconds': 120, 'cancelled': False, 'results': [
                 {'key': 'cpu', 'label': 'CPU', 'device': None, 'stopped': 'no gain',
                  'best': {'processes': 3, 'seconds_per_asset': 3.5, 'peak_process_bytes': GIB}, 'steps': []},
                 {'key': 'HIP:gpu0', 'label': 'Test GPU (HIP)', 'device': gpu, 'stopped': 'memory',
                  'best': {'processes': gpu_best, 'seconds_per_asset': 1.7, 'peak_process_bytes': peak}, 'steps': []}]}
    render_devices.probe_path(config).parent.mkdir(parents=True, exist_ok=True)
    render_devices.probe_path(config).write_text(json.dumps(value))
    return gpu


def test_plan_uses_the_speed_test_and_the_owners_device_choice(library):
    from local_asset_library import render_devices
    config, _ = library
    gpu = saved_speed_test(config)
    auto = render_pool.plan(config, available=64 * GIB, count=32)
    assert (auto['device'], auto['processes'], auto['reason']) == (gpu, 2, 'fastest in the speed test')
    assert auto['process_bytes'] == int(2 * GIB * 1.25)
    render_pool.save(config, None, None, 'cpu')
    cpu = render_pool.plan(config, available=64 * GIB, count=32)
    assert (cpu['device'], cpu['processes'], cpu['device_label']) == (None, 3, 'CPU')
    render_pool.save(config, 8, 4, 'HIP:gpu0')  # A limit above the tested best and a small memory allowance.
    small = render_pool.plan(config, available=64 * GIB, count=32)
    assert (small['processes'], small['reason']) == (1, 'your memory allowance')
    test = json.loads(render_devices.probe_path(config).read_text())
    render_devices.probe_path(config).write_text(json.dumps(dict(test, blender={'blender': 'other', 'mtime': 1})))
    assert render_devices.saved(config) is None  # A test made with another Blender is not used.
    render_pool.save(config, None, None, 'HIP:gpu0')
    untested = render_pool.plan(config, available=64 * GIB, count=32)
    assert (untested['processes'], untested['reason']) == (1, 'not speed-tested yet')


def test_gpu_jobs_name_the_device_and_take_the_gpu_lease(library, monkeypatch):
    config, _ = library
    gpu = saved_speed_test(config)
    monkeypatch.setattr(render_pool, 'available_memory', lambda: 64 * GIB)
    seen = []
    monkeypatch.setattr(incremental, 'run_inspection',
                        lambda work, *a, **k: seen.append(render_pool.job_device(work)) or {'status': 'complete'})
    report = process(config, 'inspection', 6)
    assert report['render']['device_label'] == 'Test GPU (HIP)' and seen == [{'type': 'GPU', **gpu}] * 6
    from local_asset_library.gpu_queue import lease
    work = working(config)
    record = records(work)[0]
    with closing(ledger(config)) as db, db:
        db.execute("DELETE FROM jobs WHERE asset_id=?", (record['asset_id'],))
    monkeypatch.setattr(incremental, 'run_inspection', lambda *a, **k: pytest.fail('GPU busy: nothing may render'))
    monkeypatch.setattr(incremental, 'GPU_WAIT', 1)
    with lease(config, 'search-test', timeout=1):
        with pytest.raises(render_pool.DeviceUnavailable, match='GPU is busy'):
            process(config, 'inspection', 6)


def test_a_missing_chosen_gpu_stops_the_run_and_leaves_assets_pending(library, monkeypatch):
    config, _ = library
    saved_speed_test(config)
    render_pool.save(config, None, None, 'HIP:gone')
    monkeypatch.setattr(incremental, 'run_inspection', lambda *a, **k: pytest.fail('nothing may render'))
    with pytest.raises(render_pool.DeviceUnavailable, match='was not found'):
        process(config, 'inspection', 6)
    assert process(config, 'inspection', 6, dry_run=True)['pending'] == 6


def test_a_device_failure_in_the_worker_is_a_machine_fault_not_an_asset_fault(library, monkeypatch):
    config, _ = library
    work = working(config)
    record = records(work)[0]
    fp = incremental.inspection_input(work, record)[3]
    output = work.output_path('data', result_path('inspection', fp))
    monkeypatch.setattr(incremental, '_blender_runtime', {})
    monkeypatch.setattr(incremental, 'discover_blender', lambda c: (Path('blender'), {'version_output': 'Blender'}))

    def device_gone(config, blender, worker, task, timeout):
        job = json.loads(Path(task).read_text())
        (output / 'result.json').write_text(json.dumps({'status': 'failed', 'asset_id': job['asset_id'],
            'source_path': job['source_path'], 'format': job['format'], 'errors': ['Render device unavailable: Test GPU']}))
        return {'returncode': 0, 'timed_out': False, 'output': ''}
    monkeypatch.setattr(render_pool, 'run', device_gone)
    with pytest.raises(render_pool.DeviceUnavailable, match='Test GPU'):
        incremental.run_inspection(work, record, fp)
    assert not (output / 'result.json').exists() and list(output.glob('result.device-unavailable-*.json'))


def test_equivalent_worker_hashes_keep_recorded_fingerprints(library, monkeypatch):
    from local_asset_library.publication import line_ending_hashes
    config, _ = library
    work = working(config)
    record = records(work)[0]
    old = incremental.inspection_input(work, record)[3]
    worker = config.project_root / 'src/local_asset_library/blender_worker.py'
    before = line_ending_hashes(worker)
    worker.write_text('proven-equivalent edit')
    assert incremental.inspection_input(work, record, recorded=old)[3] != old  # An unproven edit re-queues...
    after = line_ending_hashes(worker)
    monkeypatch.setattr(incremental, 'EQUIVALENT_WORKERS', dict(zip(after, before)))
    assert incremental.inspection_input(work, record, recorded=old)[3] == old  # ...a proven one keeps it.


def test_render_test_needs_blender_and_reports_through_the_operation(library, monkeypatch):
    from local_asset_library import render_devices, source_operations
    config, _ = library
    with pytest.raises(ConfigError, match='Set up Blender'):
        source_operations.start(config, 'render-test')
    phases = []
    monkeypatch.setattr(source_operations, 'state', lambda c, **kw: phases.append(kw))
    monkeypatch.setattr(render_devices, 'run', lambda c, progress, cancelled: progress('Testing render speed: CPU, 1 at a time') or {
        'cancelled': False, 'chosen': 'cpu', 'results': [{'key': 'cpu', 'label': 'CPU', 'best': {'processes': 2}}]})
    source_operations.render_test(config, 'token')
    assert phases[-1]['status'] == 'complete' and phases[-1]['phase'] == 'Speed test finished: CPU, 2 at a time'
    monkeypatch.undo()
    saved_speed_test(config)
    summary = render_devices.summary(config)
    assert summary['plan']['device'] == 'Test GPU (HIP)' and [d['key'] for d in summary['devices']] == ['cpu', 'HIP:gpu0']
    assert summary['test']['chosen'] == 'HIP:gpu0' and summary['operation'] is None


def test_speed_test_keeps_the_fastest_step_and_stops_when_more_does_not_help(monkeypatch):
    from local_asset_library import render_devices
    speeds = {1: 3.0, 2: 2.0, 4: 1.9}
    monkeypatch.setattr(render_devices, 'measure', lambda probe, worker, models, device, processes, threads, limit=None:
                        {'processes': processes, 'seconds_per_asset': speeds[processes], 'peak_process_bytes': GIB})
    plan = {'cores': 32, 'allowance_bytes': 64 * GIB}
    result = render_devices.test_device(None, None, [], None, plan)
    assert (result['best']['processes'], result['stopped']) == (4, 'no gain') and len(result['steps']) == 3
    plan['allowance_bytes'] = 3 * GIB  # 2 x 1 GiB x 1.25 fits; 4 does not.
    result = render_devices.test_device(None, None, [], None, plan)
    assert (result['best']['processes'], result['stopped']) == (2, 'memory')
    monkeypatch.setattr(render_devices, 'measure', lambda *a, limit=None, **k: {'processes': 1, 'error': 'slower', 'slower': True})
    behind = render_devices.test_device(None, None, [], {'backend': 'HIP', 'id': 'igpu', 'name': 'iGPU'}, plan, rival=1.0)
    assert behind['best'] is None and behind['stopped'] == 'much slower than another device'


def test_synthetic_shapes_are_valid_obj_models(tmp_path):
    from local_asset_library import render_devices
    models = render_devices.shapes(tmp_path)
    assert [m.stem for m in models] == ['blocks', 'sphere', 'torus', 'vase']
    for model in models:
        lines = model.read_text().splitlines()
        vertices = sum(line.startswith('v ') for line in lines)
        assert vertices and all(0 < int(i) <= vertices for line in lines if line.startswith('f ') for i in line.split()[1:])
