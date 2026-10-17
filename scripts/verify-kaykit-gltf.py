"""Read-only real KayKit source/detail/3D checks in the bundled desktop shell."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from local_asset_library.config import load_config
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from ui_text import assert_ui_text

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
out = ROOT / 'data/gui' / args.run_name
out.mkdir(parents=True, exist_ok=False)
config = load_config(ROOT / 'config.example.toml', ROOT)


class ReadOnlyBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # No startup scan or model processing.
        return result

    def operation(self, *args):
        raise RuntimeError('This verification window is read only')

    def source_action(self, *args):
        raise RuntimeError('This verification window is read only')


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = ReadOnlyBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'real_source': 'KayKit_Free_pack', 'owner_visual_approval': 'pending'}


def wait(expression, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if window.evaluate_js(expression):
            return
        time.sleep(.1)
    raise RuntimeError('UI condition timed out: ' + expression)


def js(script):
    done, values = threading.Event(), []
    window.evaluate_js(script, lambda value: (values.append(value), done.set()))
    if not done.wait(90):
        raise RuntimeError('UI action timed out')
    return values[0]


def capture(name):
    assert_ui_text(window, name, report)
    from System import Action
    from System.IO import MemoryStream
    from System.Threading.Tasks import Task
    from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
    form = window.gui.BrowserView.instances[window.uid]
    stream, done, faults = MemoryStream(), threading.Event(), []
    def start():
        task = form.browser.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)
        def finish(task):
            if task.IsFaulted:
                faults.append(str(task.Exception))
            done.set()
        task.ContinueWith(Action[Task](finish), form.browser.syncContextTaskScheduler)
    form.Invoke(Action(start))
    assert done.wait(20) and not faults
    (out / name).write_bytes(bytes(stream.ToArray()))
    stream.Dispose()


def verify():
    try:
        wait('Boolean(state.context&&state.sources?.length)')
        js("(async()=>{await openSourceBrowser('KayKit_Free_pack');return true;})()")
        wait('state.sourceBrowse?.total===1492&&!state.sourceBrowse.loading')
        wait("document.querySelectorAll('#source-grid .thumb img').length>=8")
        assert window.evaluate_js("state.sourceBrowse.items.every(item=>item.formats.every(format=>['gltf','glb'].includes(format)))")
        assert window.evaluate_js("state.sourceBrowse.items.filter(item=>item.name==='arch_blue').length===1")
        capture('01-gltf-source-grid.png')
        report['checks'].append('Source reports 1492 glTF/GLB imports with one arch_blue entry in its first page')
        js("(async()=>{const item=state.sourceBrowse.items.find(item=>item.name==='arch_blue');await selectAsset(item.asset_id,null,'three_quarter',true,state.sourceBrowse);return true;})()")
        wait('Boolean(LALPreview.current?.item.image&&!LALPreview.current.launch.disabled)')
        assert window.evaluate_js("LALPreview.current.item.sourceFormat==='gltf'&&!$('source-detail').textContent.includes('deterministic cap')&&!$('source-detail').textContent.includes('No verified source')")
        capture('02-arch-blue-detail.png')
        report['checks'].append('arch_blue has an image, verified glTF path and enabled 3D controls without a metadata-cap error')
        js('(async()=>{await LALPreview.current.start(false);return true;})()')
        wait('Boolean(LALPreview.current?.ready)', 90)
        assert window.evaluate_js("LALPreview.current.summary.textContent.includes('triangles')")
        capture('03-arch-blue-3d.png')
        report['checks'].append('Actual glTF geometry, materials and dependency files load in the bundled 3D viewer')
        assert bridge._gateway.worker is None
        report.update(status='passed', semantic_model_loaded=False)
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
        except Exception:
            pass
    finally:
        (out / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)
