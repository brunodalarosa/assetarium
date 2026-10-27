"""Proof that a blender_worker.py edit keeps finished inspections valid (decision 0022).

Read only for sources and the library. It (1) checks that every finished 3D inspection keeps its
recorded fingerprint through ``EQUIVALENT_WORKERS``, and (2) renders a spread of finished assets
again with the current worker on the CPU in kept-open processes, into scratch, comparing status,
technical metadata, render settings and preview pixels with the library's results. With --gpu it
also renders them on the speed-tested GPU and reports the largest pixel difference (informative:
GPU renders are visually equal, not byte-equal). Writes data/evidence/render-stability/<run>.json.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from local_asset_library.config import Config, load_project_config  # noqa: E402


def line_hashes(data):
    lf = data.replace(b'\r\n', b'\n')
    return {hashlib.sha256(lf).hexdigest(), hashlib.sha256(lf.replace(b'\n', b'\r\n')).hexdigest()}


def fingerprints(config):
    from local_asset_library.incremental import inspection_input, ledger, working
    from local_asset_library.membership import records
    from local_asset_library.sources import bound, registry
    kept, changed, finished = 0, [], []
    for source in registry(config)['sources']:
        scoped = bound(config, source)
        work = working(scoped)
        with closing(ledger(scoped)) as db:
            rows = {r[0]: r[1:] for r in db.execute("SELECT asset_id, fingerprint, status FROM jobs WHERE stage='inspection'")}
        for record in records(work):
            old = rows.get(record['asset_id'])
            if not old or old[1] != 'complete' or record.get('asset_type') == 'image':
                continue
            if inspection_input(work, record, recorded=old[0])[3] == old[0]:
                kept += 1
                run = record.get('inspection_run') or {}
                if run.get('status') == 'complete' and run.get('result_path') and not record.get('texture_repair'):
                    finished.append((scoped, record, run['result_path']))
            else:
                changed.append(record['asset_id'])
    return kept, changed, finished


def compare(production, rendered, prefix):
    a, b = (json.loads((folder / 'result.json').read_text(encoding='utf-8')) for folder in (production, rendered))
    # The library ran with its source prefix; this run is unprefixed, so texture paths drop it.
    technical = json.loads(json.dumps(a['technical']).replace(f'"{prefix}/', '"'))
    differences = [name for name, same in (('status', a['status'] == b['status']), ('technical', technical == b['technical']))
                   if not same]
    largest = 0
    for left, right in zip(a.get('previews', []), b.get('previews', [])):
        x, y = (np.asarray(Image.open(folder / view['filename'])).astype(int)
                for folder, view in ((production, left), (rendered, right)))
        largest = max(largest, int(np.abs(x - y).max()) if x.shape == y.shape else 255)
        if left['quality'] != right['quality'] or left['camera_location'] != right['camera_location']:
            differences.append('preview ' + left['view_label'])
    return a, b, differences, largest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--assets', type=int, default=60)
    parser.add_argument('--baseline-rev', default='origin/develop', help='git revision holding the previous worker')
    parser.add_argument('--gpu', action='store_true')
    args = parser.parse_args()
    config = load_project_config(ROOT)
    report_path = config.output_path('data', f'evidence/render-stability/{args.run_name}.json')
    if report_path.exists():
        raise SystemExit(f'{report_path} exists; choose a new --run-name (existing outputs are evidence)')
    from local_asset_library import incremental, render_devices, render_pool
    worker = ROOT / 'src/local_asset_library/blender_worker.py'
    baseline = subprocess.run(['git', 'show', f'{args.baseline_rev}:src/local_asset_library/blender_worker.py'],
                              cwd=ROOT, capture_output=True, check=True).stdout
    table = {'baseline_hashes': sorted(line_hashes(baseline)), 'current_hashes': sorted(line_hashes(worker.read_bytes()))}
    table['mapped'] = all(incremental.EQUIVALENT_WORKERS.get(h) in table['baseline_hashes'] for h in table['current_hashes'])
    kept, changed, finished = fingerprints(config)
    by_format = {}
    for item in finished:  # Every inspected format in turn, evenly spread within each.
        by_format.setdefault((item[1].get('technical') or {}).get('inspected_format'), []).append(item)
    spread = [items[::max(1, len(items) * len(by_format) // args.assets)] for items in by_format.values()]
    chosen = []
    while len(chosen) < args.assets and any(spread):
        for group in spread:
            if group and len(chosen) < args.assets:
                chosen.append(group.pop(0))
    folder = config.output_path('scratch', f'render-stability/{args.run_name}')
    shutil.rmtree(folder, ignore_errors=True)
    blender = config.blender
    plan = render_pool.plan(config)
    devices = [None]
    if args.gpu and plan['device']:
        devices.append(plan['device'])
    runs = {}
    started = time.monotonic()
    for device in devices:
        name = render_devices.key(device).replace(':', '-')
        processes = plan['processes'] if device else max(1, min(4, plan['cores'] // 8))
        outcomes = []
        for scoped, record, result_path in chosen:
            production = scoped.output_path('data', result_path.removeprefix('data/')).parent
            job = json.loads((production / 'job.json').read_text(encoding='utf-8'))
            outcomes.append((scoped, record, production, job))
        probe = Config(folder / name, chosen[0][0].source_root if chosen else ROOT.parent, blender)

        def render(item):
            scoped, record, production, job = item
            output = probe.output_path('data', record['asset_id'])
            output.mkdir(parents=True, exist_ok=True)
            prefix = job.pop('source_prefix')
            job.pop('metadata_root', None)
            job.update(project_root=str(probe.project_root), output=str(output),
                       source_path=job['source_path'].removeprefix(prefix + '/'), source_root=str(scoped.source_root))
            if device:
                job['render_device'] = {'type': 'GPU', **device}
            task = output / 'job.json'
            task.write_text(json.dumps(job), encoding='utf-8')
            process = pool.run(blender, worker, task, 300)
            if not (output / 'result.json').exists():
                return {'asset_id': record['asset_id'], 'differences': ['no result'], 'log': process['output'][-500:]}
            a, b, differences, largest = compare(production, output, prefix)
            if device is None:
                differences += ['render settings'] if a['render_settings'] != b['render_settings'] else []
            return {'asset_id': record['asset_id'], 'format': job['format'], 'status': b['status'],
                    'differences': differences, 'largest_pixel_difference': largest}
        with render_pool.opened(probe, processes, max(1, plan['cores'] // processes), device) as pool, \
                ThreadPoolExecutor(processes) as executor:
            results = list(executor.map(render, outcomes))
        runs[render_devices.label(device)] = {
            'assets': len(results), 'identical': sum(not r['differences'] and r['largest_pixel_difference'] == 0 for r in results),
            'largest_pixel_difference': max((r.get('largest_pixel_difference', 255) for r in results), default=0),
            'formats': sorted({r.get('format', '?') for r in results}), 'results': results}
    shutil.rmtree(folder, ignore_errors=True)
    cpu = runs['CPU']
    report = {'run_name': args.run_name, 'worker_table': table, 'fingerprints': {'kept': kept, 'changed': changed},
              'runs': runs, 'elapsed_seconds': round(time.monotonic() - started, 1),
              'passed': table['mapped'] and not changed and cpu['identical'] == cpu['assets'] > 0}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for label, run in runs.items():
        print(f"{label}: {run['identical']}/{run['assets']} identical, largest pixel difference {run['largest_pixel_difference']}/255, "
              f"formats {', '.join(run['formats'])}")
    print(f"Fingerprints kept: {kept}, changed: {len(changed)}; equivalence table maps current to baseline: {table['mapped']}")
    print(('PASSED' if report['passed'] else 'FAILED') + f': {report_path.relative_to(ROOT)}')
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
