"""Focused actual WebView2 search lifecycle verification; synthetic assets only."""
import argparse
from io import BytesIO
import base64
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_retrieval import indexed
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.mcp_assets import AssetService
from PIL import Image
from ui_text import assert_ui_text

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir(parents=True, exist_ok=False)
config, backend, records = indexed.__wrapped__(fixture)
stream = BytesIO()
Image.new('RGB', (24, 24), '#789abc').save(stream, format='PNG')
image = base64.b64encode(stream.getvalue()).decode('ascii')


class FixtureBridge(DesktopBridge):
    def thumbnail(self, identifier, version=None):
        return {'image': image, 'payload': {}}


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
bridge = FixtureBridge(config)
import webview
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True,
          'owner_windows_validation': 'pending', 'real_model_load': False}


def js(script):
    done, values = threading.Event(), []
    def callback(value):
        values.append(value)
        done.set()
    window.evaluate_js(script, callback)
    if not done.wait(30):
        raise RuntimeError('UI check completion timeout')
    return values[0]


def capture(name):
    assert_ui_text(window, name, report)
    from System import Action
    from System.IO import MemoryStream
    from System.Threading.Tasks import Task
    from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
    form = window.gui.BrowserView.instances[window.uid]
    stream, done, faults = MemoryStream(), threading.Event(), []
    def capture_on_ui():
        task = form.browser.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)
        def finished(task):
            if task.IsFaulted:
                faults.append(str(task.Exception))
            done.set()
        task.ContinueWith(Action[Task](finished), form.browser.syncContextTaskScheduler)
    form.Invoke(Action(capture_on_ui))
    assert done.wait(15) and not faults
    (OUT / name).write_bytes(bytes(stream.ToArray()))
    stream.Dispose()


def verify():
    try:
        deadline = time.perf_counter() + 25
        while not window.evaluate_js('Boolean(state.context && state.items.length===40)'):
            if time.perf_counter() > deadline:
                raise RuntimeError('Startup timeout')
            time.sleep(.1)
        assert window.gui.renderer == 'edgechromium'
        startup = window.evaluate_js("({mode:$('mode').value,limit:$('limit').value,choices:[...$('limit').options].map(x=>x.value)})")
        assert startup == {'mode': 'combined', 'limit': '20', 'choices': ['5', '10', '20', '30', '40']}
        report['startup'] = startup
        # Actual shared bridge paths, with synthetic query inference and unchanged published generation.
        async def semantic(name, arguments):
            payload, image, evidence = AssetService(config, backend=backend).execute(name, arguments)
            return dict(payload=payload, image=image, evidence=evidence, is_error=False)
        bridge._gateway.semantic = semantic
        agreement = js("""(async()=>{$('query').value='obj';await search();const original=structuredClone(state.lastSettings);
          $('query').value='unsent edit';return {settings:original,ids:state.items.map(x=>x.asset_id),saved:state.lastSettings};})()""")
        assert agreement['settings'] == agreement['saved'] == {'query': 'obj', 'mode': 'combined', 'limit': 20, 'filters': {}}
        replay, _, _ = AssetService(config, backend=backend).execute('search_assets', agreement['settings'])
        assert agreement['ids'] == [r['asset_id'] for r in replay['results']] and len(agreement['ids']) == 20
        report['copied_settings_reproduction'] = agreement
        # Defer resolution to observe the real packaged UI before model-load/search completion.
        window.evaluate_js("""window.fixtureApi=state.api;window.pending=[];window.busyChecks={};
          state.api={...fixtureApi,search:args=>new Promise((resolve,reject)=>pending.push({args,resolve,reject}))};
          $('query').value='slow';window.firstSearch=search();
          busyChecks.immediate=!$('search-busy').hidden&&$('submit').disabled&&$('grid').getAttribute('aria-busy')==='true';
          busyChecks.preserved=state.items.length===20;
          busyChecks.announcement=$('search-busy').getAttribute('role')==='status'&&$('search-busy').textContent.includes('Searching');
          search();busyChecks.duplicate=pending.length===1;
        """)
        time.sleep(.3)
        capture('searching.png')
        assert window.evaluate_js("getComputedStyle(document.querySelector('.search-spinner')).animationName") == 'search-spin'
        outcomes = js("""(async()=>{const assert=(value,name)=>{busyChecks[name]=Boolean(value);if(!value)throw Error(name)};
          const finish=(job,results=[])=>job.resolve({arguments:job.args,elapsed_seconds:.3,payload:{generation:state.context.generation,results,fault_count:0,truncated:false}});
          // A new request supersedes the first; old completion must not clear the new busy state.
          $('query').value='new';const newer=search();finish(pending[0]);await firstSearch;
          assert(!$('search-busy').hidden&&$('submit').disabled,'old_completion_keeps_new_busy');
          finish(pending[1]);await newer;assert($('search-busy').hidden&&!$('submit').disabled&&state.items.length===0,'empty_completion');
          $('query').value='failed';const failed=search();pending[2].reject(Error('Synthetic search failure'));await failed;
          assert($('search-busy').hidden&&!$('submit').disabled&&$('error').textContent.includes('Synthetic search failure'),'error_completion');
          $('query').value='clear race';const clearing=search();$('clear').click();finish(pending[3]);await clearing;
          await new Promise(resolve=>setTimeout(resolve,300));assert($('search-busy').hidden&&$('mode').value==='combined'&&$('limit').value==='20','clear_reset');
          $('query').value='refresh race';const refreshing=search();const reload=refreshContext(true);finish(pending[4]);await refreshing;
          // Refresh replays an active search against the current publication.
          // Resolve that new request too; leaving it pending deadlocks the harness.
          while(pending.length<6)await new Promise(resolve=>setTimeout(resolve,10));
          finish(pending[5]);await reload;
          assert($('search-busy').hidden&&!$('submit').disabled&&state.lastSettings.query==='refresh race','refresh_supersedes');
          $('query').value='success';const successful=search();finish(pending[6],[{asset_id:'fixture',name:'fixture',pack:'synthetic',caption_owner_review:'pending'}]);await successful;
          assert($('search-busy').hidden&&!$('submit').disabled&&state.items[0].asset_id==='fixture','success_completion');
          return busyChecks;})()""")
        assert all(outcomes.values()), outcomes
        report['lifecycle'] = outcomes
        # Apply the exact bundled reduced-motion rule to inspect its renderer behavior.
        reduced = window.evaluate_js("""(()=>{const rule=[...document.styleSheets[0].cssRules].find(r=>r.conditionText?.includes('prefers-reduced-motion')&&[...(r.cssRules||[])].some(x=>x.selectorText==='.search-spinner'));
          if(!rule)return false;const style=document.createElement('style');style.textContent=[...rule.cssRules].map(r=>r.cssText).join('');document.head.append(style);searchBusy(999);
          return getComputedStyle(document.querySelector('.search-spinner')).animationName==='none'&&!$('search-busy').hidden;})()""")
        assert reduced
        report['reduced_motion'] = 'Bundled media rule verified statically and applied in WebView2; OS preference not changed'
        capture('static-busy.png')
        window.evaluate_js('searchBusy(null);state.api=fixtureApi')
        assert not bridge._gateway.model_requested
        report['checks'] = ['Actual packaged WebView2 startup/reset options', 'Shared bridge copied settings reproduce 20 results',
            'Slow busy display and preserved cards', 'Duplicate suppression and responsive JavaScript',
            'Success/empty/error/clear/new search/refresh lifecycle', 'Accessible live status and static reduced-motion indicator']
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
    finally:
        (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        window.destroy()


try:
    webview.start(verify, gui='edgechromium', private_mode=True, storage_path=str(profile))
finally:
    bridge._close()
    record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2))
sys.exit(0 if report['status'] == 'passed' else 1)
