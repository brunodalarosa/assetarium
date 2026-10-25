"""Installed-library startup/Settings check; no asset processing or model load."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from local_asset_library.config import load_project_config
from local_asset_library.desktop import DesktopBridge,create_window,profile_path,record_profile_outcome
from local_asset_library.source_operations import operation_status,RUNNING
from local_asset_library.publication import atomic_json
os.environ.update(PYTHONNET_RUNTIME='netfx',TEMP=str(ROOT/'scratch/tmp-mcp'),TMP=str(ROOT/'scratch/tmp-mcp'))
config=load_project_config(ROOT)
OUT=ROOT/'data/gui'/('source-installed-'+uuid.uuid4().hex[:10]);OUT.mkdir()
bridge=DesktopBridge(config);window=create_window(config,bridge);profile=profile_path(config,bridge,window)
report={'status':'running','owner_approval':'pending'}
from gui_harness import Harness
ui=Harness(window,OUT,report)
js=ui.js
def wait(expression,timeout=90):
    ui.js('until(()=>(%s),%d)'%(expression,timeout*1000),timeout+5)
def capture(name):
    ui.capture(name)
def verify():
    try:
        from local_asset_library.retrieval import pilot_records
        from local_asset_library.sources import importing_failures,registry,source_status
        members,registered=len(pilot_records(config)),registry(config)['sources']
        ui.wait_ready(90,f'lal.state.context.pilot_count==={members}&&lal.state.sources.length==={len(registered)}')
        js("(async()=>{await lal.submitSearch();return true})()")
        wait(f"lal.state.library.items.length===Math.min(40,{members})")
        wait("document.querySelectorAll('#grid .thumb img').length>0")
        deadline=time.monotonic()+90
        while operation_status(config).get('status') in RUNNING and time.monotonic()<deadline:time.sleep(.2)
        assert operation_status(config)['status']=='complete'
        assert not bridge._gateway.model_requested
        attention="lal.state.sources.filter(s=>s.needs_processing||s.scan_fault).length"
        report['library']=js("({assets:lal.state.context.pilot_count,sources:lal.state.sources.length,attention:"+attention+",cards:lal.state.library.items.length})")
        expected=importing_failures(config)
        assert expected['assets']>0 and not expected['unavailable']
        statuses=[source_status(config,source) for source in registry(config)['sources']]
        warnings=sum(bool(s.get('needs_processing') or s.get('scan_fault')) for s in statuses)
        wait(f"{attention}==={warnings}")
        report['library']['attention']=js(attention)
        capture('library.png')
        js("$('nav-processing').click()")
        wait(f"document.querySelectorAll('#processing-view [data-action=process]').length==={warnings}&&$('import-failures-summary').textContent.includes('with recorded failures')")
        js("[...document.querySelectorAll('#processing-view button')].find(b=>b.textContent.startsWith('Show ')).click()")
        wait("document.querySelectorAll('#import-failures-list li').length>0")
        assert js("[...$('import-failures-list').children].map(x=>x.textContent)")==expected['paths']
        assert js("$('import-failures-list').scrollHeight>$('import-failures-list').clientHeight")
        report['failures']={'assets':expected['assets'],'paths':len(expected['paths']),'scrollable':True,'pending_actions':warnings}
        capture('import-failures.png')
        js("(async()=>{$('nav-settings').click();await until(()=>$('asset-sources-tab'));$('asset-sources-tab').click();return true})()")
        wait(f"document.querySelectorAll('.source-row').length==={len(registered)}")
        assert js("[...document.querySelectorAll('.source-enabled [role=switch]')].map(x=>x.getAttribute('aria-checked')==='true')")==[s['enabled'] for s in registered]
        # Startup cost receipt: summary loads and their duration from the bridge audit.
        calls=[json.loads(line) for line in (bridge._gateway.audit_root/'desktop.jsonl').read_text(encoding='utf-8').splitlines()]
        report['startup_calls']={name:{'count':sum(c['operation']==name for c in calls),
            'seconds':round(sum(c['elapsed_seconds'] for c in calls if c['operation']==name),3)} for name in ('context','browse','thumbnail','_sources','_changes')}
        assert not js("[...document.querySelectorAll('button')].some(b=>['Scan','Status'].includes(b.textContent))")
        assert js("$('settings-view').scrollWidth<=$('settings-view').clientWidth+1")
        capture('settings.png')
        report.update(status='passed',startup_scan='complete',model_loaded=False)
    except BaseException as exc:
        import traceback;report.update(status='faulty',reason=str(exc),traceback=traceback.format_exc())
    finally:
        atomic_json(OUT/'report.json',report);bridge._close();window.destroy()
try:
    import webview
    webview.start(verify,gui='edgechromium',debug=False,storage_path=str(profile),private_mode=True)
finally:
    bridge._close();record_profile_outcome(bridge,profile)
print(json.dumps({'status':report['status'],'report':str(OUT/'report.json'),'reason':report.get('reason')},indent=2))
sys.exit(report['status']!='passed')
