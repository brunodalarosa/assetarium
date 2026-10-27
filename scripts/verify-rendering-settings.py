"""Verify Settings → General → Rendering (decision 0022) in the real WebView2 shell with synthetic sources.

Checks that the card explains what renders now and why, lists the saved speed test, saves the
device, renders-at-a-time and memory limits with the form (and keeps them after reopening), shows
a running speed test with Cancel test, and keeps the narrow layout. Nothing renders and no model
loads. Writes data/gui/<run-name>/verification.json.
"""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source  # noqa: E402
from local_asset_library import render_devices, render_pool, search_speed  # noqa: E402
from local_asset_library.engines import cpu_threads  # noqa: E402
from local_asset_library.settings import save_general_settings, search_threads  # noqa: E402
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from local_asset_library.inspection import blender_candidates  # noqa: E402
from local_asset_library.publication import atomic_json  # noqa: E402
from gui_harness import Harness, isolate_hash_cache  # noqa: E402
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir()
config, backend, one, two = managed.__wrapped__(fixture)
found = blender_candidates(config)
if not found:
    raise SystemExit('Install Blender to run this check (it is only located, never started)')
config = replace(config, blender=found[0])
ready_source(config, backend, one)
preserved = [p for p in Path(one['path']).iterdir() if p.is_file()]
original_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved}
GIB = render_pool.GIB
gpu = {'backend': 'HIP', 'id': 'synthetic-gpu', 'name': 'Synthetic GPU'}
atomic_json(render_devices.probe_path(config), {
    'schema_version': 1, 'blender': render_devices.blender_identity(config), 'devices': [gpu], 'cores': 32,
    'chosen': 'HIP:synthetic-gpu', 'utc': '2026-10-26T12:00:00+00:00', 'elapsed_seconds': 130, 'cancelled': False,
    'results': [
        {'key': 'cpu', 'label': 'CPU', 'device': None, 'stopped': 'no gain', 'steps': [],
         'best': {'processes': 2, 'seconds_per_asset': 3.51, 'peak_process_bytes': GIB}},
        {'key': 'HIP:synthetic-gpu', 'label': 'Synthetic GPU (HIP)', 'device': gpu, 'stopped': 'memory', 'steps': [],
         'best': {'processes': 2, 'seconds_per_asset': 1.68, 'peak_process_bytes': 2 * GIB}}]})
save_general_settings(config, 10, None, None, None, None, None, 'cpu')  # Search on the CPU shows its thread choice.
LOGICAL = cpu_threads()
TESTED = max(1, LOGICAL * 3 // 4)
atomic_json(search_speed.probe_path(config), {
    'schema_version': 1, 'identity': search_speed.identity(config), 'chosen': TESTED, 'cancelled': False,
    'utc': '2026-10-26T12:00:00+00:00', 'elapsed_seconds': 35,
    'results': [{'threads': max(1, LOGICAL // 2), 'seconds_per_image': 1.14, 'passes': [1.14, 1.14]},
                {'threads': TESTED, 'seconds_per_image': 0.89, 'passes': [0.89, 0.89]},
                {'threads': LOGICAL, 'seconds_per_image': 0.9, 'passes': [0.9, 0.9]}]})


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def _start_source_operation(self, operation, key):
        # The speed test itself is covered by tests and the real-processing check; here only its UI.
        return {'status': 'faulty', 'reason': 'Synthetic check: the speed test is not started'}


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)


def wait(expression, timeout=30):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def text(element):
    return ui.js(f"$('{element}').textContent")


def choose(field, value):
    ui.js(f"(async()=>{{await pick('{field}','{value}');return true}})()")
    wait(f"$('{field}').dataset.value==='{value}'")


def verify():
    try:
        ui.wait_ready()
        ui.js("$('nav-settings').click()")
        wait("$('render-now')&&$('render-device')")
        now = text('render-now')
        assert now.startswith('Now: Synthetic GPU (HIP), ') and 'at a time' in now, now
        lines = text('render-test')
        assert 'Synthetic GPU (HIP): 1.68 s per test asset, 2 at a time' in lines and '· fastest' in lines, lines
        assert 'CPU: 3.51 s per test asset, 2 at a time (more at a time did not help)' in lines, lines
        assert ui.js("$('render-test-start').textContent.trim()==='Test again'")
        ui.js("$('rendering-card').scrollIntoView()")
        ui.capture('01-rendering-tested.png')
        report['checks'].append('Rendering card says what renders now and why; the Speed test card lists each tested device with its speed')
        choose('render-device', 'cpu')
        choose('render-processes', '1')
        ui.js("(async()=>{const f=$('render-memory');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;"
              "set.call(f,'6');f.dispatchEvent(new Event('input',{bubbles:true}));await frame();$('save-general-settings').click();return true})()")
        wait("$('general-settings-message').textContent.startsWith('Saved.')")
        assert render_pool.saved(config) == {'device': 'cpu', 'processes': 1, 'memory_gib': 6}, render_pool.saved(config)
        wait("$('render-now').textContent.startsWith('Now: CPU, 1 render at a time, limited by your limit')")
        report['checks'].append('Saving the form saves device CPU, 1 render at a time and 6 GiB; the card says the limit applies')
        ui.js("(async()=>{$('nav-home').click();await until(()=>$('library-view'));$('nav-settings').click();return true})()")
        wait("$('render-memory')&&$('render-memory').value==='6'&&$('render-device').dataset.value==='cpu'"
             "&&$('render-processes').dataset.value==='1'")
        report['checks'].append('Reopening Settings keeps the saved rendering limits')
        choose('render-device', 'auto')
        choose('render-processes', 'auto')
        ui.js("(async()=>{const f=$('render-memory');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;"
              "set.call(f,'');f.dispatchEvent(new Event('input',{bubbles:true}));await frame();$('save-general-settings').click();return true})()")
        wait("$('render-now').textContent.includes('(fastest in the speed test)')")
        assert render_pool.saved(config) == {'device': None, 'processes': None, 'memory_gib': None}
        report['checks'].append('Automatic again: the fastest tested device and count are used')
        wait(f"$('search-threads-now')&&$('search-threads-now').textContent.startsWith('Now: {TESTED} of {LOGICAL} threads (fastest in the speed test)')")
        assert ui.js(f"$('search-threads').textContent.includes('Automatic ({TESTED})')")
        assert ui.js(f"$('search-test').textContent.includes('{TESTED} threads 0.89 s')&&$('search-test').textContent.includes('{TESTED} threads chosen')")
        ui.js("$('search-card').scrollIntoView()")
        ui.capture('04-search-threads-tested.png')
        ui.js("$('search-card').querySelector('.speed-test-link').click()")
        wait("(r=>r.top>=0&&r.top<innerHeight/2)($('speed-test-card').getBoundingClientRect())")
        assert ui.js("$('speed-test-card').textContent.includes('Rendering')&&$('speed-test-card').textContent.includes('Search data')"
                     "&&!!$('speed-test-card').querySelector('#render-test-start')&&!$('rendering-card').querySelector('#render-test-start')")
        ui.capture('05-speed-test-card.png')
        report['checks'].append('The Speed test card holds Test again and both results (rendering and search data); '
                                'See the speed test in the Search card scrolls to it')
        pinned = max(1, LOGICAL - 4)
        choose('search-threads', str(pinned))
        ui.js("(async()=>{$('save-general-settings').click();return true})()")
        for _ in range(100):  # The form message may still read Saved. from the earlier save.
            if search_threads(config) == pinned:
                break
            threading.Event().wait(.1)
        assert search_threads(config) == pinned, search_threads(config)
        wait(f"$('search-threads-now').textContent.startsWith('Now: {pinned} of {LOGICAL} threads (your setting)')")
        choose('search-threads', 'auto')
        ui.js("(async()=>{$('save-general-settings').click();return true})()")
        wait(f"$('search-threads-now').textContent.startsWith('Now: {TESTED} of {LOGICAL}')")
        for _ in range(100):
            if search_threads(config) is None:
                break
            threading.Event().wait(.1)
        assert search_threads(config) is None
        report['checks'].append('Search card: CPU threads show the speed test choice and each tested count; '
                                'a chosen number saves and applies, Automatic returns to the tested choice')
        token = 'synthetic-render-test'
        atomic_json(config.output_path('data', 'library/source-operation.json'), {
            'token': token, 'pid': os.getpid(), 'status': 'processing', 'operation': 'render-test', 'key': None,
            'phase': 'Testing render speed: Synthetic GPU (HIP), 2 at a time', 'progress': .4})
        wait("$('render-test-cancel')&&$('render-test-message').textContent.includes('Synthetic GPU (HIP), 2 at a time')")
        assert ui.js("$('rendering-card').querySelector('.speed-test-link').textContent.includes('Speed test running')")
        ui.js("$('speed-test-card').scrollIntoView()")
        ui.capture('02-speed-test-running.png')
        ui.js("$('render-test-cancel').click()")
        cancel = config.output_path('data', 'library/source-cancel.json')
        for _ in range(50):
            if cancel.exists():
                break
            threading.Event().wait(.1)
        assert cancel.exists() and json.loads(cancel.read_text())['token'] == token
        atomic_json(config.output_path('data', 'library/source-operation.json'), {
            'token': token, 'pid': os.getpid(), 'status': 'cancelled', 'operation': 'render-test', 'key': None,
            'phase': 'Speed test cancelled; the previous result is kept', 'progress': 1})
        wait("$('render-test-start')&&$('render-test-message').textContent.includes('previous result is kept')")
        report['checks'].append('A running speed test shows its phase and Cancel test; cancelling keeps the previous result')
        window.resize(680, 900)
        wait('innerWidth<761')
        ui.js("$('rendering-card').scrollIntoView()")
        assert ui.js("$('settings-view').scrollWidth<=$('settings-view').clientWidth+1")
        ui.capture('03-rendering-narrow.png')
        report['checks'].append('Narrow layout has no horizontal overflow')
        assert not bridge._gateway.model_requested
        assert original_hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved}
        report['checks'].append('Originals are byte-identical; nothing rendered and no model was loaded')
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        atomic_json(OUT / 'verification.json', report)
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(dict(report, report=str(OUT / 'verification.json')), indent=2))
raise SystemExit(report['status'] != 'passed')
