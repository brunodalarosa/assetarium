"""Verify General settings in the real WebView2 shell with synthetic sources."""
import json
import hashlib
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.publication import atomic_json
from local_asset_library.settings import GIB, general_settings, settings_path
from local_asset_library import sources
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)

name = 'general-settings-' + uuid.uuid4().hex[:10]
OUT = ROOT / 'data/gui' / name
OUT.mkdir()
fixture = ROOT / 'scratch' / name
fixture.mkdir()
config, backend, one, two = managed.__wrapped__(fixture)
ready_source(config, backend, one)
ready_source(config, backend, two)
source_root = Path(one['path'])
for extension, content in [('fbx', b'synthetic'), ('blend', b'synthetic'),
                           ('gltf', b'{"asset":{"version":"2.0"}}'), ('glb', b'synthetic')]:
    (source_root / ('extra.' + extension)).write_bytes(content)
sources.scan_source(config, one)
preserved = [p for source in (one, two) for p in Path(source['path']).iterdir() if p.is_file()]
for source in (one, two):
    scoped = sources.bound(config, source)
    preserved.extend(scoped.output_path('data', name) for name in ('catalog.sqlite', 'embeddings/index.sqlite'))
original_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved}
policy_path = config.project_root / 'docs/library-membership.json'
value = json.loads(policy_path.read_text())
value['budget'] = {'total_allocated_bytes': 10 * GIB, 'peak_additional_allocated_bytes': 3 * GIB}
atomic_json(policy_path, value)


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}


ui = Harness(window, OUT, report)


def wait(expression, timeout=30):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def capture(name):
    ui.capture(name)


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===2')
        ui.js("$('nav-settings').click()")
        wait("$('general-panel')&&!$('general-panel').hidden&&$('storage-budget')&&!$('storage-budget').disabled&&$('storage-budget').value==='10'")
        assert ui.js("$('asset-sources-panel').hidden&&$('general-tab').getAttribute('aria-selected')==='true'")
        assert not settings_path(config).exists()
        assert ui.js("[...$('processing-formats').querySelectorAll('[role=checkbox]')].every(box=>box.getAttribute('aria-checked')==='true')")
        assert ui.js("$('caption-batch-size').dataset.value==='8'&&!$('caption-batch-size').querySelector('[aria-haspopup=listbox]').disabled")
        report['checks'].append('General opens by default and shows the historical limit and default batch size 8 without writing them')
        ui.js("""(async()=>{type('storage-budget','24');$('processing-format-fbx').click();$('processing-format-obj').click();
          await frame();await pick('caption-batch-size','4');$('save-general-settings').click();return true})()""")
        wait("$('general-settings-message').textContent.startsWith('Saved.')")
        assert general_settings(config)['storage_budget_gib'] == 24
        assert general_settings(config)['processing_formats'] == ['gltf']
        assert general_settings(config)['caption_batch_size'] == 4
        assert ui.js("$('general-settings-message').textContent.includes('Description batch size: 4')")
        report['checks'].append('Save persists description batch size 4 and names it in the confirmation')
        wait("lal.state.sources.find(s=>s.key===" + json.dumps(one['key']) + ").pending===2")
        capture('01-general-saved.png')
        report['checks'].append('Save persists the budget and glTF-only selection; pending counts refresh immediately without processing')
        saved = settings_path(config).read_bytes()
        ui.js("(async()=>{type('storage-budget','0');await frame();$('save-general-settings').click();return true})()")
        assert not ui.js("$('storage-budget').checkValidity()")
        assert settings_path(config).read_bytes() == saved
        assert bridge.save_general_settings('invalid')['status'] == 'faulty'
        assert settings_path(config).read_bytes() == saved
        assert bridge.save_general_settings('24', ['gltf'], '3')['status'] == 'faulty'
        assert settings_path(config).read_bytes() == saved
        report['checks'].append('Browser and backend reject invalid values without replacing the saved limit')
        ui.js("(async()=>{$('nav-home').click();await until(()=>$('library-view'));$('nav-settings').click();return true})()")
        wait("$('storage-budget')&&$('storage-budget').value==='24'&&!$('storage-budget').disabled&&$('caption-batch-size').dataset.value==='4'")
        assert ui.js("['gltf','fbx','obj'].map(f=>$('processing-format-'+f).getAttribute('aria-checked')).join()==='true,false,false'")
        ui.js("(async()=>{$('processing-format-gltf').click();await frame();$('save-general-settings').click();return true})()")
        wait("$('general-settings-message').textContent.includes('Processing is paused')")
        wait("lal.state.sources.every(source=>source.processing_paused&&!source.needs_processing)")
        assert bridge.source_action('process', one['key'])['status'] == 'faulty'
        report['checks'].append('All unchecked saves a visible paused state, removes pending warnings and starts no source worker')
        ui.js("(async()=>{$('processing-format-gltf').click();await frame();$('save-general-settings').click();return true})()")
        wait("$('general-settings-message').textContent.startsWith('Saved.')&&!$('processing-formats').disabled")
        ui.js("(async()=>{$('general-tab').focus();$('general-tab').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));await until(()=>$('asset-sources-panel')&&!$('asset-sources-panel').hidden);await frame();return true})()")
        assert ui.js("$('general-panel').hidden&&!$('asset-sources-panel').hidden&&document.activeElement===$('asset-sources-tab')&&$('general-tab').tabIndex===-1")
        wait("[...document.querySelectorAll('.source-format-counts')].some(row=>row.textContent==='FBX: 1 · glTF / GLB: 2 · OBJ: 3 · BLEND: 1')")
        capture('02-asset-sources.png')
        report['checks'].append('Asset Sources shows every inventoried format, including disabled FBX/OBJ and unsupported BLEND')
        ui.js("(async()=>{$('asset-sources-tab').dispatchEvent(new KeyboardEvent('keydown',{key:'Home',bubbles:true}));await until(()=>!$('general-panel').hidden);await frame();return true})()")
        assert ui.js("!$('general-panel').hidden&&document.activeElement===$('general-tab')")
        report['checks'].append('Reopening reloads the saved value; keyboard navigation and selected tab state work')
        window.resize(680, 800)
        wait('innerWidth<761')
        assert ui.js("$('settings-view').scrollWidth<=$('settings-view').clientWidth+1")
        capture('03-general-narrow.png')
        ui.js("(async()=>{$('asset-sources-tab').click();await until(()=>!$('asset-sources-panel').hidden);await frame();return true})()")
        assert ui.js("$('settings-view').scrollWidth<=$('settings-view').clientWidth+1")
        capture('04-sources-narrow.png')
        assert not bridge._gateway.model_requested
        assert original_hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved}
        report['checks'].append('Originals, published catalogs and published vectors are byte-identical; no model or real source processing ran')
        report['checks'].append('Narrow layout has no horizontal overflow; no inference worker was loaded')
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
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
