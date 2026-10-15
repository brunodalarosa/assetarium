"""Installed-library startup/Settings check; no asset processing or model load."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_config
from local_asset_library.desktop import DesktopBridge,create_window,profile_path,record_profile_outcome
from local_asset_library.source_operations import operation_status,RUNNING
from local_asset_library.publication import atomic_json
os.environ.update(PYTHONNET_RUNTIME='netfx',TEMP=str(ROOT/'scratch/tmp-mcp'),TMP=str(ROOT/'scratch/tmp-mcp'))
config=load_config(ROOT/'config.example.toml',ROOT)
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
        wait('state.context&&state.context.pilot_count===1901&&state.sources.length===13&&state.items.length===40')
        wait("document.querySelectorAll('.thumb img').length>0")
        deadline=time.monotonic()+90
        while operation_status(config).get('status') in RUNNING and time.monotonic()<deadline:time.sleep(.2)
        assert operation_status(config)['status']=='complete'
        assert bridge._gateway.worker is None
        report['library']=window.evaluate_js("({assets:state.context.pilot_count,sources:state.sources.length,warnings:document.querySelectorAll('.source-warning').length,cards:state.items.length})")
        from local_asset_library.sources import importing_failures,registry,source_status
        expected=importing_failures(config)
        assert expected['assets']>0 and not expected['unavailable']
        assert all(not source_status(config,source)['needs_processing'] for source in registry(config)['sources'])
        wait("document.querySelectorAll('.source-warning').length===0")
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
        wait("document.querySelectorAll('.source-row').length===13")
        assert window.evaluate_js("[...document.querySelectorAll('.source-enabled input')].every(x=>x.checked)")
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
