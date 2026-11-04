"""Real WebView2 check of the Format off state (design principle P5, No silent states).

A synthetic model has an FBX it was inspected from and an OBJ; with FBX off it stays listed. Its Library card shows
Format off with the reason, the inspector says why and offers Turn FBX on, and that action brings it back to Ready.
Small isolated synthetic sources; no model or Blender run. Writes data/gui/<run-name>/verification.json.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source
from local_asset_library import library_view, sources
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.incremental import update_record, working
from local_asset_library.settings import processing_formats, save_general_settings
from local_asset_library.source_operations import publish_source
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir(exist_ok=False)
config, backend, one, two = managed.__wrapped__(fixture)
ready_source(config, backend, one)
work = working(sources.bound(config, one))
record = sources.read_records(work)[0]
obj = record['files'][0]
fbx = dict(obj, path=obj['path'][:-4] + '.fbx', format='fbx')
name = obj['path'].rsplit('/', 1)[-1]
(Path(one['path']) / name[:-4]).with_suffix('.fbx').write_bytes((Path(one['path']) / name).read_bytes())  # Same bytes, same hash.
record['files'] = [fbx, obj]
record['primary_inspection_path'] = fbx['path']
record['technical'] = dict(record['technical'], inspected_path=fbx['path'], inspected_format='fbx')
update_record(work, record)
publish_source(sources.bound(config, one))
sources.aggregate(config)
save_general_settings(config, 24, ['obj'])
library_view.blockers = lambda config: {}  # No Blender or search runtime here; nothing is processed.
ASSET = record['asset_id']


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': {}, 'synthetic_only': True, 'owner_visual_approval': 'pending'}
ui = Harness(window, OUT, report)
js = ui.js
card = f"document.querySelector('[data-id=\"{ASSET}\"]')"


def verify():
    try:
        ui.wait_ready()
        js(f"lal.openSources({json.dumps(one['key'])},'',{json.dumps(ASSET)});true")
        ui.check('card_says_format_off', f"""until(()=>{card}?.querySelector('.state-strip[data-state="format_off"]')).then(()=>({{
          label: [...{card}.querySelectorAll('.state-strip [role=img]')].some(e=>e.getAttribute('aria-label').startsWith('Format off: Previews were made from'))}}))""")
        js("lal.setInspectorOpen(true);true")
        ui.check('inspector_says_why', """until(()=>document.querySelector('.format-off')).then(()=>({
          reason: document.querySelector('.format-off').textContent.includes('and FBX is off, so descriptions and search by meaning leave it out'),
          action: [...document.querySelectorAll('.format-off button')].some(b=>b.textContent==='Turn FBX on')}))""")
        ui.capture('01-format-off.png')
        js("[...document.querySelectorAll('.format-off button')].find(b=>b.textContent==='Turn FBX on').click();true")
        ui.check('turning_it_on_resolves_it', f"""until(()=>!document.querySelector('.format-off')&&!{card}?.querySelector('.state-strip[data-state="format_off"]'),20000).then(()=>({{
          toast: lal.state.toasts.some(t=>t.title==='FBX is on')}}))""")
        assert processing_formats(config) == ['fbx', 'obj']
        ui.capture('02-format-on.png')
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        (OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
        bridge._allow_close = True
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
bridge._close()
record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)
