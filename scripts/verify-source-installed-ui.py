"""Installed-library startup/Settings check; no asset processing or model load."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_project_config
from local_asset_library.desktop import DesktopBridge,create_window,profile_path,record_profile_outcome
from local_asset_library.source_operations import operation_status,RUNNING
from local_asset_library.publication import atomic_json
os.environ.update(PYTHONNET_RUNTIME='netfx',TEMP=str(ROOT/'scratch/tmp-mcp'),TMP=str(ROOT/'scratch/tmp-mcp'))
config=load_project_config(ROOT)
OUT=ROOT/'data/gui'/('source-installed-'+uuid.uuid4().hex[:10]);OUT.mkdir()
bridge=DesktopBridge(config);window=create_window(config,bridge);profile=profile_path(config,bridge,window)
report={'status':'running','owner_approval':'pending'}
def wait(expression,timeout=90):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.15)
    raise RuntimeError('Installed UI condition timed out: '+expression)
def capture(name):
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
        from local_asset_library.retrieval import pilot_records
        from local_asset_library.sources import importing_failures,registry,source_status
        members,registered=len(pilot_records(config)),registry(config)['sources']
        wait(f'state.context&&state.context.pilot_count==={members}&&state.sources.length==={len(registered)}&&state.items.length===Math.min(40,{members})')
        wait("document.querySelectorAll('.thumb img').length>0")
        deadline=time.monotonic()+90
        while operation_status(config).get('status') in RUNNING and time.monotonic()<deadline:time.sleep(.2)
        assert operation_status(config)['status']=='complete'
        assert bridge._gateway.worker is None
        report['library']=window.evaluate_js("({assets:state.context.pilot_count,sources:state.sources.length,warnings:document.querySelectorAll('.source-warning').length,cards:state.items.length})")
        expected=importing_failures(config)
        assert expected['assets']>0 and not expected['unavailable']
        statuses=[source_status(config,source) for source in registry(config)['sources']]
        warnings=sum(bool(s.get('needs_processing') or s.get('scan_fault')) for s in statuses)
        wait(f"document.querySelectorAll('.source-warning').length==={warnings}")
        report['library']['warnings']=window.evaluate_js("document.querySelectorAll('.source-warning').length")
        capture('library.png')
        window.evaluate_js("$('open-import-failures').click()")
        wait("!$('import-failures-view').hidden&&!state.loadingFailures&&document.querySelectorAll('#import-failures-list li').length>0")
        assert window.evaluate_js("[...$('import-failures-list').children].map(x=>x.textContent)")==expected['paths']
        assert window.evaluate_js("$('import-failures-list').scrollHeight>$('import-failures-list').clientHeight")
        report['failures']={'assets':expected['assets'],'paths':len(expected['paths']),'scrollable':True,'pending_cards':0}
        capture('import-failures.png')
        window.evaluate_js("$('close-import-failures').click()")
        window.evaluate_js("$('open-settings').click()")
        window.evaluate_js("$('asset-sources-tab').click()")
        wait(f"document.querySelectorAll('.source-row').length==={len(registered)}")
        assert window.evaluate_js("[...document.querySelectorAll('.source-enabled input')].map(x=>x.checked)")==[s['enabled'] for s in registered]
        # Startup cost receipt: summary loads and their duration from the bridge audit.
        calls=[json.loads(line) for line in (bridge._gateway.audit_root/'desktop.jsonl').read_text(encoding='utf-8').splitlines()]
        report['startup_calls']={name:{'count':sum(c['operation']==name for c in calls),
            'seconds':round(sum(c['elapsed_seconds'] for c in calls if c['operation']==name),3)} for name in ('context','browse','thumbnail','_sources','_changes')}
        assert not window.evaluate_js("[...document.querySelectorAll('.library-operations button')].some(b=>['Scan','Status'].includes(b.textContent))")
        assert window.evaluate_js('document.documentElement.scrollWidth<=innerWidth')
        capture('settings.png')
        report.update(status='passed',startup_scan='complete',model_loaded=False)
    except BaseException as exc:
        report.update(status='faulty',reason=str(exc))
    finally:
        atomic_json(OUT/'report.json',report);bridge._close();window.destroy()
try:
    import webview
    webview.start(verify,gui='edgechromium',debug=False,storage_path=str(profile),private_mode=True)
finally:
    bridge._close();record_profile_outcome(bridge,profile)
print(json.dumps({'status':report['status'],'report':str(OUT/'report.json'),'reason':report.get('reason')},indent=2))
sys.exit(report['status']!='passed')
