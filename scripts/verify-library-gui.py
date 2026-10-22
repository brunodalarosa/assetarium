"""Actual WebView2 checks on a larger synthetic collection or published originals."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
parser=argparse.ArgumentParser()
parser.add_argument('--run-name',required=True)
parser.add_argument('--synthetic',action='store_true')
args=parser.parse_args()
if not args.run_name.replace('-','').isalnum():raise ValueError('Invalid run name')
OUT=ROOT/'data/gui'/args.run_name
OUT.mkdir(parents=True,exist_ok=False)
from local_asset_library.config import load_config
from local_asset_library.desktop import DesktopBridge,create_window,profile_path,record_profile_outcome
from local_asset_library.publication import generation
if args.synthetic:
    sys.path.insert(0,str(ROOT/'tests'))
    from test_incremental import library,ready
    from local_asset_library.incremental import refresh,publish,working,update_record
    from local_asset_library.library_index import index_library
    from local_asset_library.membership import records
    fixture=OUT/'fixture';fixture.mkdir()
    config,backend=library.__wrapped__(fixture)
    for i in range(310):
        (config.source_root/'one'/f'extra{i}.obj').write_text('v 0 0 0\n')
    refresh(config);work=ready(config);index_library(work,backend,limit=2000);publish(config)
else:
    config=load_config(ROOT/'config.example.toml',ROOT)
bridge=DesktopBridge(config)
window=create_window(config,bridge)
profile=profile_path(config,bridge,window)
report={'status':'running','synthetic':args.synthetic,'checks':[],'faults':[],'owner_approval':'pending'}

def save():
    (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
from gui_harness import Harness
ui=Harness(window,OUT,report)
js=ui.js
def wait(expression,timeout=30):
    ui.js('until(()=>(%s),%d)'%(expression,timeout*1000),timeout+5)
def capture(name):
    ui.capture(name)
def verify():
    wire=None
    try:
        ui.wait_ready()
        js("(async()=>{await lal.submitSearch();return true})()")
        wait("lal.state.library.items.length===40&&$('grid').getAttribute('aria-busy')==='false'")
        wait("document.querySelectorAll('#grid .thumb img').length>0")
        assert not bridge._gateway.model_requested
        initial=js("({count:lal.state.context.pilot_count,cards:lal.state.library.items.length,images:document.querySelectorAll('#grid .thumb img').length,workers:lal.thumbnailWorkers(),offset:lal.state.library.offset})")
        assert initial['count']>300 and initial['cards']==40 and initial['images']<40 and initial['workers']<=3
        report['initial']=initial
        report['checks'].append('Bounded 40-card page, visible-only thumbnails, <=3 thumbnail requests, no model load on startup')
        capture('browse.png')
        started=time.perf_counter();js("(async()=>{await lal.pageBrowse(1);return lal.state.library.items.map(x=>x.asset_id);})()")
        report['page_seconds']=time.perf_counter()-started
        assert js('lal.state.library.offset===40 && lal.state.library.items.length===40')
        keyboard=js("(async()=>{await frame();const cards=[...$('grid').querySelectorAll('.card')];cards[0].focus();cards[0].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));return document.activeElement===cards[1];})()")
        assert keyboard
        js("lal.selectAsset('library',lal.state.library.items[0].asset_id,null,'three_quarter').then(()=>true)")
        selected=js('lal.state.library.selected')
        wait("Boolean($('detail').querySelector('h2'))")
        js("lal.browse(false).then(()=>true)")
        assert js('lal.state.library.selected')==selected
        report['checks'].append('Next page, stable selection, arrow keyboard handler, responsive detail')
        capture('detail.png')
        window.resize(680,760);wait('innerWidth<761')
        assert js("$('library-view').scrollWidth<=$('library-view').clientWidth+1")
        capture('narrow.png')
        report['checks'].append('Actual native resize and narrow layout without horizontal overflow')
        if args.synthetic:
            from library_test_wire import FixtureWire
            wire=FixtureWire(ROOT,config,OUT/'fixture-mcp-stderr.log')
            comparisons=[]
            for filters in ({},{'pack':'one','format':'obj','max_triangles':1,'rigged':False}):
                request={'query':'extra','mode':'keyword','filters':filters,'limit':5}
                before=bridge.search(request)['payload']
                assert wire.search(request)==before
                comparisons.append({'arguments':request,'before_ids':[r['asset_id'] for r in before['results']],'before_generation':before['generation']})
            old=js('lal.state.context.generation')
            item=records(work)[0];item['display_name']='Published update fixture';update_record(work,item)
            fresh=publish(config)
            js('lal.refreshContext().then(()=>true)')
            assert js('lal.state.context.generation')==fresh['generation']!=old
            assert js('lal.state.library.selected')==selected
            assert bridge.asset(selected,None,'three_quarter',old)['status']=='stale'
            for comparison in comparisons:
                after=bridge.search(comparison['arguments'])['payload']
                assert wire.search(comparison['arguments'])==after
                assert after['generation']==fresh['generation']
                assert len(after['results'])<=5 and after['serialized_characters']<=6000
                comparison['after_ids']=[r['asset_id'] for r in after['results']]
                comparison['after_generation']=after['generation']
            report['actual_stdio_updates']=comparisons
            wire.close();wire=None
            report['checks'].append('Open native app detects transactional publication, retains selected ID, rejects old-version thumbnail/detail')
            report['checks'].append('Same live STDIO connection and GUI agree on candidate IDs/order/verified filters/cap before and after publication')
        args_search={'query':'item' if args.synthetic else 'apple','mode':'keyword','filters':{},'limit':5}
        from local_asset_library.mcp_assets import AssetService
        shared=AssetService(config).execute('search_assets',args_search)[0]
        gui=bridge.search(args_search)
        assert gui['payload']==shared
        report['checks'].append('Actual GUI bridge agrees with shared service candidate IDs/order/filter/cap/version')
        report['search']=gui
        assert not bridge._gateway.model_requested
        report['checks'].append('All browsing/keyword/detail operations completed without installing, downloading or loading a model')
        report['status']='passed'
    except BaseException as exc:
        try:
            report['ui_failure_state']=window.evaluate_js("({error:lal.state.search.error,status:lal.state.search.status,items:lal.state.library.items.length})")
            capture('fault.png')
        except Exception as capture_error:
            report['capture_error']=str(capture_error)
        report['status']='faulty';report['faults'].append({'type':type(exc).__name__,'reason':str(exc),'traceback':traceback.format_exc()})
    finally:
        if wire is not None:
            wire.close()
        save();window.destroy()

os.environ.update(PYTHONNET_RUNTIME='netfx',TEMP=str(ROOT/'scratch/tmp-mcp'),TMP=str(ROOT/'scratch/tmp-mcp'))
import webview
save()
try:
    webview.start(verify,gui='edgechromium',private_mode=True,storage_path=str(profile))
finally:
    bridge._close();record_profile_outcome(bridge,profile)
    report['closed']=not bridge._thread.is_alive();save()
print(json.dumps({'status':report['status'],'checks':report['checks'],'faults':report['faults']}))
sys.exit(report['status']!='passed')
