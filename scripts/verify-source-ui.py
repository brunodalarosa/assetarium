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
from test_sources import managed,ready_source,failed_previews
from local_asset_library.incremental import working,update_record
from local_asset_library.membership import records
from local_asset_library.source_operations import publish_source
from local_asset_library import sources
from local_asset_library.source_operations import state,cancel,cancelled
from local_asset_library.desktop import DesktopBridge,create_window,profile_path,record_profile_outcome
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)

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


ui=Harness(window,OUT,report)


def wait(expression,timeout=35):
    ui.js('until(()=>(%s),%d)'%(expression,timeout*1000),timeout+5)


js=ui.js
capture=ui.capture
PROCESS="document.querySelectorAll('#processing-view [data-action=process]').length"


def verify():
    try:
        ui.wait_ready(extra='lal.state.context.pilot_count===6')
        js("$('nav-processing').click()")
        wait(PROCESS+"===1")
        assert js("$('nav-processing').getAttribute('aria-label').includes('needs attention')")
        assert not bridge._gateway.model_requested
        report['checks'].append('Startup scan detects a file added since the previous scan without model loading; Asset processing offers it')
        assert js("![...document.querySelectorAll('button')].some(x=>['Process pending','Publish ready work'].includes(x.textContent))")
        js("(async()=>{lal.setState({filters:{...lal.state.filters,mode:'keyword'}});lal.setQuery('item0');await lal.submitSearch();return true})()")
        wait("lal.state.library.items.length===2&&lal.state.search.phase==='search'")
        js("$('nav-settings').click()")
        js("(async()=>{await until(()=>$('asset-sources-tab'));$('asset-sources-tab').click();return true})()")
        wait("$('settings-view')&&document.querySelectorAll('.source-row').length===2")
        assert js("$('asset-sources-tab').getAttribute('aria-selected')==='true'")
        capture('settings.png');report['checks'].append('Settings button, sources tab and both registered sources')
        js("document.querySelector('.source-enabled [role=switch]').click()")
        wait("lal.state.context.pilot_count===3&&lal.state.library.items.length===1&&lal.state.search.phase==='search'")
        report['checks'].append('Disabled-source cached cards disappear even when the replacement search is busy')
        js("document.querySelector('.source-enabled [role=switch]').click()")
        wait("lal.state.context.pilot_count===6&&lal.state.library.items.length===2&&lal.state.search.phase==='search'")
        assert js("lal.state.search.lastSettings.query==='item0'")
        report['checks'].append('Live switch reruns the active search, preserving the query, without restart or model loading')
        js("(async()=>{lal.clearSearch();await lal.submitSearch();return true})()")
        wait("lal.state.library.items.length===6&&lal.state.search.phase==='browse'")
        # Each changed source is offered for processing after a scan.
        for source in (one,two):(Path(source['path'])/'added.obj').write_text('v 0 0 0\n')
        js("lal.sourceAction('scan').then(()=>true)")
        js("$('nav-processing').click()")
        wait(PROCESS+"===2")
        capture('pending-sources.png');report['checks'].append('Each source with newly scanned files offers Process assets')
        js("document.querySelector('#processing-view [data-action=process]').click()")
        wait("document.querySelector('#processing-view article [role=progressbar]')")
        capture('processing.png')
        js("document.querySelector('#processing-view [data-action=cancel]').click()")
        wait("lal.state.sources.some(x=>x.operation.status==='cancelled')")
        wait(PROCESS+"===2")
        report['checks'].append('Progress bar, cancel action and retained pending work after cancellation')
        js("document.querySelector('#processing-view [data-action=process]').click()")
        wait(PROCESS+"===1")
        wait('lal.state.context.pilot_count===8')
        report['checks'].append('Pending work disappears only after processed results are published and scanned')
        window.resize(680,760);wait('innerWidth<761')
        js("$('nav-settings').click()")
        js("(async()=>{await until(()=>$('asset-sources-tab'));$('asset-sources-tab').click();await frame();return true})()")
        wait("$('settings-view')&&!$('asset-sources-panel').hidden")
        assert js("$('settings-view').scrollWidth<=$('settings-view').clientWidth+1")
        capture('settings-narrow.png');report['checks'].append('Narrow settings view has no horizontal overflow')
        # Failed attempts remain inspectable without presenting a futile action.
        work=working(sources.bound(config,one));record=records(work)[0]
        original=json.loads(json.dumps(record));failed_previews(work,record)
        publish_source(sources.bound(config,one));sources.aggregate(config);sources.scan_source(config,one)
        js("$('nav-processing').click()")
        wait("lal.state.sources.some(x=>x.failed===1&&!x.needs_processing)&&"+PROCESS+"===1")
        report['checks'].append('A published retained failure offers no futile processing action; the other unfinished source keeps its action')
        wait("$('import-failures-summary').textContent.includes('1 asset with recorded failures')")
        js("[...document.querySelectorAll('#processing-view button')].find(b=>b.textContent.startsWith('Show ')).click()")
        wait("document.querySelectorAll('#import-failures-list li').length>0")
        expected=sources.importing_failures(config)['paths']
        assert js("[...$('import-failures-list').children].map(x=>x.textContent)")==expected
        assert js("getComputedStyle($('import-failures-list')).overflowY==='auto'&&$('processing-view').scrollWidth<=$('processing-view').clientWidth+1")
        capture('import-failures-narrow.png')
        report['checks'].append('Failure report displays original paths as selectable text in a scrollable list without narrow-screen overflow')
        js("lal.goBack()")
        wait("$('settings-view')")
        assert js("!document.querySelector('[aria-label=Forward]').disabled")
        report['checks'].append('Back returns to the previous view; Forward is available again')
        update_record(work,original);sources.scan_source(config,one)
        js("lal.goForward()")
        wait("$('import-failures-empty')&&!$('import-failures-list')")
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
