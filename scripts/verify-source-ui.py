"""Actual WebView2 source settings/cards check with isolated synthetic assets."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_sources import managed,ready_source,failed_caption
from local_asset_library.incremental import working,update_record
from local_asset_library.membership import records
from local_asset_library.source_operations import publish_source
from local_asset_library import sources
from local_asset_library.source_operations import state,cancel,cancelled
from local_asset_library.desktop import DesktopBridge,create_window,profile_path,record_profile_outcome
from ui_text import assert_ui_text

run=uuid.uuid4().hex[:10]
OUT=ROOT/'data/gui'/('source-settings-'+run);OUT.mkdir(parents=True)
fixture=ROOT/'scratch'/('source-ui-'+run);fixture.mkdir()
config,backend,one,two=managed.__wrapped__(fixture)
ready_source(config,backend,one);ready_source(config,backend,two)
(Path(one['path'])/'startup-added.obj').write_text('v 0 0 0\n',encoding='utf-8')
os.environ.update(PYTHONNET_RUNTIME='netfx',TEMP=str(ROOT/'scratch/tmp-mcp'),TMP=str(ROOT/'scratch/tmp-mcp'))


class FixtureBridge(DesktopBridge):
    def search(self,settings):
        if getattr(self,'_fail_next_search',False):
            self._fail_next_search=False
            return {'payload':{'status':'faulty','reason':'Fixture processing queue is busy'},'is_error':True}
        return super().search(settings)

    def _source_action(self,action,key,directory,enabled):
        if action=='scan':
            for source in sources.registry(config)['sources']:
                if source['enabled']:sources.scan_source(config,source)
            return {'status':'saved'}
        if action=='enabled':
            sources.set_enabled(config,key,enabled)
            if not enabled:self._fail_next_search=True
            if enabled:sources.scan_source(config,sources.get_source(config,key))
            return {'status':'saved'}
        if action=='process':
            source=sources.get_source(config,key);scoped=sources.bound(config,source);token=uuid.uuid4().hex
            state(scoped,status='processing',phase='Inspection',pid=os.getpid(),token=token,progress=.1)
            def complete():
                for step in range(1,5):
                    time.sleep(.35)
                    if cancelled(scoped,token):
                        state(scoped,status='cancelled',phase='Cancelled; completed assets saved')
                        return
                    state(scoped,status='processing',phase='Processing fixture assets',progress=.15*step)
                state(scoped,status='publishing',phase='Publishing',progress=.92)
                ready_source(config,backend,source)
                state(scoped,status='complete',phase='Up to date and published',progress=1)
            threading.Thread(target=complete,daemon=True).start()
            return {'status':'started'}
        return super()._source_action(action,key,directory,enabled)


bridge=FixtureBridge(config)
window=create_window(config,bridge)
profile=profile_path(config,bridge,window)
report={'status':'running','checks':[],'fixture':str(fixture),'renderer':'edgechromium','owner_approval':'pending'}


def wait(expression,timeout=35):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.1)
    raise RuntimeError('UI condition timed out: '+expression)


def js(script):
    if '.then(' not in script:
        return window.evaluate_js(script)
    done=threading.Event();result=[]
    window.evaluate_js(script,lambda value:(result.append(value),done.set()))
    if not done.wait(35):raise RuntimeError('UI action timed out')
    return result[0]


def capture(name):
    assert_ui_text(window, name, report)
    from System import Action
    from System.IO import MemoryStream
    from System.Threading.Tasks import Task
    from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
    form=window.gui.BrowserView.instances[window.uid];stream=MemoryStream();done=threading.Event();faults=[]
    def on_ui():
        task=form.browser.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)
        def finish(task):
            if task.IsFaulted:faults.append(str(task.Exception))
            done.set()
        task.ContinueWith(Action[Task](finish),form.browser.syncContextTaskScheduler)
    form.Invoke(Action(on_ui));assert done.wait(15) and not faults
    (OUT/name).write_bytes(bytes(stream.ToArray()));stream.Dispose()


def verify():
    try:
        wait("state.context&&state.context.pilot_count===6&&state.items.length===6")
        wait("document.querySelectorAll('.source-warning').length===1")
        assert not bridge._gateway.model_requested
        report['checks'].append('Startup scan detects a file added since the previous scan without model loading')
        assert window.evaluate_js("![...document.querySelectorAll('button')].some(x=>['Process pending','Publish ready work'].includes(x.textContent))")
        js("(()=>{$('query').value='item0';$('mode').value='keyword';return search().then(()=>true);})()")
        wait('state.items.length===2&&!state.browsing')
        js("$('open-settings').click();true")
        js("$('asset-sources-tab').click();true")
        wait("!$('settings-view').hidden&&document.querySelectorAll('.source-row').length===2")
        assert window.evaluate_js("$('asset-sources-tab').getAttribute('aria-selected')==='true'")
        capture('settings.png');report['checks'].append('Settings button, sidebar tab and both registered sources')
        js("document.querySelector('.source-enabled input').click();true")
        wait('state.context.pilot_count===3&&state.items.length===1&&!state.browsing')
        report['checks'].append('Disabled-source cached cards disappear even when the replacement search is busy')
        js("document.querySelector('.source-enabled input').click();true")
        wait('state.context.pilot_count===6&&state.items.length===2&&!state.browsing')
        assert window.evaluate_js("state.lastSettings.query==='item0'")
        report['checks'].append('Live checkbox reruns the active search, preserving the query, without restart or model loading')
        js("$('clear').click();true")
        wait('state.items.length===6&&state.browsing')
        # Each changed source receives its own card after a scan.
        for source in (one,two):(Path(source['path'])/'added.obj').write_text('v 0 0 0\n')
        js("sourceAction('scan').then(()=>true)")
        js("$('close-settings').click();true")
        wait("document.querySelectorAll('.source-warning').length===2")
        capture('pending-sources.png');report['checks'].append('One card per source after newly added files are scanned')
        js("document.querySelector('.source-warning .primary').click();true")
        wait("!document.querySelector('.source-warning progress').hidden")
        capture('processing.png')
        js("document.querySelector('.source-warning button[data-action=cancel]').click();true")
        wait("state.sources.some(x=>x.operation.status==='cancelled')")
        assert window.evaluate_js("document.querySelectorAll('.source-warning').length===2")
        report['checks'].append('Progress bar, cancel action and retained warning after cancellation')
        js("document.querySelector('.source-warning .primary').click();true")
        wait("document.querySelectorAll('.source-warning').length===1")
        wait('state.context.pilot_count===8')
        report['checks'].append('Card disappears only after processed results are published and scanned')
        window.resize(680,760);wait('innerWidth<761')
        js("$('open-settings').click();true")
        js("$('asset-sources-tab').click();true")
        wait("!$('settings-view').hidden")
        assert window.evaluate_js('document.documentElement.scrollWidth<=innerWidth')
        capture('settings-narrow.png');report['checks'].append('Narrow settings view has no horizontal overflow')
        # Failed attempts remain inspectable without presenting a futile action.
        work=working(sources.bound(config,one));record=records(work)[0]
        original=json.loads(json.dumps(record));failed_caption(work,record)
        publish_source(sources.bound(config,one));sources.aggregate(config);sources.scan_source(config,one)
        js("$('close-settings').click();true")
        wait("state.sources.some(x=>x.failed===1&&!x.needs_processing)&&document.querySelectorAll('.source-warning').length===1")
        report['checks'].append('A published retained failure creates no pending-import card; the other unfinished source keeps its card')
        js("$('open-import-failures').click();true")
        wait("!$('import-failures-view').hidden&&document.querySelectorAll('#import-failures-list li').length>0")
        expected=sources.importing_failures(config)['paths']
        assert window.evaluate_js("[...$('import-failures-list').children].map(x=>x.textContent)")==expected
        assert window.evaluate_js("getComputedStyle($('import-failures-list')).overflowY==='auto'&&document.documentElement.scrollWidth<=innerWidth")
        capture('import-failures-narrow.png')
        report['checks'].append('Failure report displays original paths as selectable text in a scrollable list without narrow-screen overflow')
        js("$('close-import-failures').click();true")
        wait("!$('library-view').hidden&&document.activeElement.id==='open-import-failures'")
        report['checks'].append('Back to library preserves the current library view and returns keyboard focus')
        update_record(work,original);sources.scan_source(config,one)
        js("$('open-import-failures').click();true")
        wait("!$('import-failures-empty').hidden&&$('import-failures-list').hidden")
        capture('import-failures-empty.png')
        report['checks'].append('Empty failure report has an explicit empty state')
        report['status']='passed'
    except BaseException as exc:
        report.update(status='faulty',reason=str(exc),traceback=traceback.format_exc())
    finally:
        (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        bridge._close();window.destroy()


try:
    import webview
    webview.start(verify,gui='edgechromium',debug=False,storage_path=str(profile),private_mode=True)
finally:
    bridge._close();record_profile_outcome(bridge,profile)
print(json.dumps({'status':report['status'],'report':str(OUT/'report.json'),'reason':report.get('reason')},indent=2))
sys.exit(report['status']!='passed')
