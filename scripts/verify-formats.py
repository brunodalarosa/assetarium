"""Verify Formats Assetarium uses (decision 0031) in the real WebView2 shell with a synthetic library.

A library folder holds an OBJ, an FBX-only model, a PNG image and a JPEG image. Settings → General shows the 3D and
image toggles with the texture note; turning FBX and JPEG off and saving hides those assets from the Library (one
quiet line links back to the formats), turning them on brings them back. Checks untouched originals and that no
model loads. Writes data/gui/<run-name>/verification.json.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed  # noqa: E402
from local_asset_library import sources  # noqa: E402
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from local_asset_library.publication import atomic_json  # noqa: E402
from local_asset_library.settings import general_settings  # noqa: E402
from gui_harness import Harness, isolate_hash_cache  # noqa: E402
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir()
config, _, one, two = managed.__wrapped__(fixture)
root = fixture / 'library'
kit = root / 'Kit_1.0'
kit.mkdir(parents=True)
(kit / 'Crate.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
(kit / 'Barrel.fbx').write_bytes(b'Kaydara FBX Binary  \x00synthetic')
(kit / 'License.txt').write_text('CC0')
from PIL import Image  # noqa: E402
art = root / 'Art'  # Standalone 2D assets live apart from models; images beside models can be their textures.
art.mkdir()
Image.new('RGB', (64, 64), (200, 40, 40)).save(art / 'Icon.png')
Image.new('RGB', (64, 64), (40, 40, 200)).save(art / 'Photo.jpg')
added = sources.add(config, str(root))
sources.scan_source(config, added)
KEY = added['key']
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config, prestart_worker=False)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)
NAMES = "[...document.querySelectorAll('#grid .card-name, #grid [data-asset-name]')].map(e=>e.textContent.trim())"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def library_names():
    return ui.js("lal.state.source.items.filter(i=>!i.file).map(i=>i.name).sort().join(',')")


def open_library():
    ui.js(f"(async()=>{{lal.openSources({json.dumps(KEY)}, '');await until(()=>$('sources-view')&&$('folder-header'));"
          "await until(()=>lal.state.source.items.length>0);await frame();return true})()")


def verify():
    try:
        ui.wait_ready(extra="lal.state.sources.length===3")
        open_library()
        before = library_names()
        assert before == 'Barrel,Crate,Icon,Photo', before
        report['checks'].append('With every format on, the Library lists the OBJ, the FBX, the PNG and the JPEG')
        ui.js("(async()=>{lal.navigate({page:'settings',tab:'general'});await until(()=>$('formats-card')&&$('image-format-png'));"
              "$('formats-card').scrollIntoView({block:'start'});await frame();return true})()")
        assert ui.js("$('formats-card').textContent.includes('Textures used by 3D models are always read')"
                     "&&document.querySelectorAll('#image-format [role=checkbox], #image-format input[type=checkbox]').length===9")
        ui.capture('01-formats-card.png')
        report['checks'].append('Settings → General shows "Formats Assetarium uses" with 3 model and 9 image toggles and the texture note')
        ui.js("(async()=>{$('processing-format-fbx').click();$('image-format-jpeg').click();await frame();"
              "document.querySelector('#general-settings-form [type=submit]').click();"
              "await until(()=>!lal.state.general.busy&&lal.state.general.values.image_formats.indexOf('jpeg')<0);return true})()")
        saved = general_settings(config)
        assert saved['processing_formats'] == ['gltf', 'obj'] and 'jpeg' not in saved['image_formats'], saved
        open_library()
        wait("$('hidden-formats')", 30)
        after = library_names()
        assert after == 'Crate,Icon', after
        assert ui.js("$('hidden-formats').textContent.includes('2 files in formats you don’t use')")
        ui.capture('02-library-hides-off-formats.png')
        report['checks'].append('Turning FBX and JPEG off hides those assets from the Library at once; one line says so and links to the formats')
        ui.js("$('hidden-formats').click()")
        wait("$('formats-card')&&lal.state.history[lal.state.historyIndex].page==='settings'", 20)
        report['checks'].append('The line opens Settings at the formats')
        # The form fills from the saved values first; toggling before that would be overwritten.
        wait("lal.state.general.values&&!lal.state.general.loading&&$('image-format-jpeg')&&!$('image-format-jpeg').disabled", 20)
        ui.js("(async()=>{await new Promise(r=>setTimeout(r,300));$('processing-format-fbx').click();$('image-format-jpeg').click();await frame();"
              "document.querySelector('#general-settings-form [type=submit]').click();"
              "await until(()=>!lal.state.general.busy&&lal.state.general.values.image_formats.indexOf('jpeg')>=0);return true})()")
        open_library()
        wait("!$('hidden-formats')", 30)
        assert library_names() == before
        report['checks'].append('Turning them back on brings the same assets back; nothing was deleted or scanned again')
        assert not bridge._gateway.model_requested
        now = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        assert now == originals
        report['checks'].append('Original files are byte-identical; no model was loaded')
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
