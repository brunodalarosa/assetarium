"""Real WebView2 check of the loading language (Assetarium KnowledgeBase/Architecture/Desktop App/Desktop app design.md → Loading states).

Holds chosen bridge calls in the page so every loading state can be observed and captured:
ghost cards on the Collections tab, Home, a collection and Asset processing, ghost cover tiles
and thumbnails, the inspector ghost, the refresh sheen, the top-bar activity indicator (search
preparation, a source operation, its finished state), that quick loads never flash ghosts and
the reduced-motion rule. Small isolated synthetic sources; keyword-free, no model loads.
Writes data/gui/<run-name>/verification.json and light and dark screenshots.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir(exist_ok=False)
config, backend, one, two = managed.__wrapped__(fixture)
ready_source(config, backend, one)
ready_source(config, backend, two)


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True, 'owner_visual_approval': 'pending', 'real_model_load': False}
ui = Harness(window, OUT, report)
js = ui.js

# hold(name…) parks those bridge calls until release(name); override(name, fn) answers them itself.
HOLD = r"""window.overrides={};window.held={};
window.hold=(...names)=>{for(const n of names){held[n]=held[n]||[];
  overrides[n]=(...a)=>new Promise((res,rej)=>held[n].push(()=>Promise.resolve(fixtureApi[n](...a)).then(res,rej)))}return stubApi(overrides)};
window.release=n=>{delete overrides[n];stubApi(overrides);const q=held[n]||[];held[n]=[];q.forEach(f=>f());return q.length};
window.override=(n,fn)=>{overrides[n]=fn;return stubApi(overrides)};
window.restore=n=>{delete overrides[n];return stubApi(overrides)};
window.theme=t=>{document.documentElement.dataset.theme=t;return true};
window.count=sel=>document.querySelectorAll(sel).length;
window.shimmer=sel=>getComputedStyle(document.querySelector(sel),'::after').animationName;
true"""


def wait(expression, timeout=20):
    try:
        js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)
    except RuntimeError as exc:
        raise RuntimeError('UI condition timed out: ' + expression) from exc


def both(name):
    """Light and dark screenshots of the current state."""
    for theme in ('light', 'dark'):
        js(f"theme('{theme}')")
        ui.capture(f'{name}-{theme}.png', settle=.3)
    js("theme('light')")


def done(text):
    report['checks'].append(text)


def verify():
    try:
        ui.wait_ready()
        js(HOLD)
        ids = js("(async()=>(await lal.state.api.browse({},0,40)).items.map(x=>x.asset_id))()")
        assert len(ids) >= 4, ids
        js(f"(async()=>{{await lal.createCollection('Loading demo','',{json.dumps(ids[:4])});lal.state.toasts.forEach(t=>lal.dismissToast(t.id));return true}})()")

        # Collections tab, first load: ghost cards, never the empty state.
        js("hold('collections','thumbnail');lal.setState({collections:{items:[],total:0,loading:false,loaded:false,error:null,query:''}});lal.navigate({page:'collections'});true")
        wait("count('#collections-loading .collection-ghost')===6&&!$('collections-empty')")
        assert js("shimmer('#collections-loading .skeleton')") == 'skeleton-shimmer'
        assert js("count('.collection-card')") == 0
        both('01-collections-ghosts')
        done('Collections tab shows six shimmering ghost cards until its first answer, never "No collections yet"')
        js("release('collections')")
        wait("count('#collections-grid .collection-card')===1&&!$('collections-loading')")
        wait("count('#collections-grid .collection-card .skeleton')===4")
        both('02-collections-cover-ghosts')
        done('Cover tiles shimmer until their thumbnails arrive')
        js("release('thumbnail')")
        wait("count('#collections-grid .collection-card img.reveal-img')===4")
        assert js("getComputedStyle(document.querySelector('#collections-grid img')).animationName") == 'reveal-img'
        done('Cover thumbnails resolve from a blur')

        # Quick loads never flash ghosts.
        js("""window.flashed=0;window.watch=new MutationObserver(()=>{if(document.querySelector('.collection-ghost'))flashed++});
          watch.observe(document.body,{subtree:true,childList:true});hold('collections');
          lal.setState({collections:{items:[],total:0,loading:false,loaded:false,error:null,query:''}});lal.navigate({page:'home'});lal.navigate({page:'collections'});
          setTimeout(()=>release('collections'),60);true""")
        wait("count('#collections-grid .collection-card')===1")
        js("new Promise(r=>setTimeout(r,400))")
        assert js("watch.disconnect(),flashed") == 0
        done('A load answered within 60 ms shows no ghosts at all')

        # Home: ghost cards while browsing, ghost thumbnails, then dimmed cards and the sheen while replacing.
        js("hold('browse','thumbnail');lal.navigate({page:'home'});lal.browse();true")
        wait("count('#grid .card-ghost')===8&&$('grid').getAttribute('aria-busy')==='true'&&!$('empty')")
        both('03-home-ghosts')
        done('Home shows eight ghost cards while a page of the library loads, never "No assets match"')
        js("release('browse')")
        wait("count('#grid .card')>=4&&count('#grid .card-ghost')===0&&count('#grid .thumb-loading .skeleton')>=4")
        both('04-home-thumbnail-ghosts')
        done('Cards arrive with shimmering thumbnail ghosts; the loading text stays for screen readers')
        js("release('thumbnail')")
        wait("count('#grid img.reveal-img')>=4")
        js("override('search',()=>new Promise(()=>{}));lal.setQuery('crate');lal.submitSearch();true")
        wait("$('grid').classList.contains('refreshing')&&$('search-form').classList.contains('sheen')&&count('#grid .card')>=4")
        js("new Promise(r=>setTimeout(r,400))")  # The dimming is a short transition.
        assert float(js("getComputedStyle(document.querySelector('#grid .card')).opacity")) < .8
        assert js("getComputedStyle($('search-form'),'::after').animationName") == 'sheen'
        both('05-search-refreshing')
        done('A search keeps the earlier cards, dims them and sweeps a sheen across the search bar')
        js("lal.clearSearch();restore('search');true")

        # Inspector ghost.
        js(f"hold('asset');lal.navigate({{page:'home'}});lal.browse();true")
        wait("count('#grid .card')>=4")
        js(f"lal.setInspectorOpen(true);lal.selectAsset('library',{json.dumps(ids[0])});true")
        wait("count('#detail .skeleton')>=5&&$('detail').textContent.includes('Loading asset evidence…')")
        both('06-inspector-ghost')
        js("release('asset')")
        wait("!document.querySelector('#detail .skeleton')&&Boolean(document.querySelector('#detail h2'))")
        done('Inspection shows a ghost of its layout until the asset evidence arrives')
        js("lal.setInspectorOpen(false);true")

        # Activity indicator: search preparation, then a source operation, then the finished state.
        js("override('changes',async()=>({...(await fixtureApi.changes()),worker:'loading_libraries'}));true")
        wait("$('activity')?.textContent.includes('Preparing search')", 10)
        ui.capture('07-activity-search.png')
        source = js("lal.state.sources[0].key")
        js(f"""override('sources',async()=>{{const r=await fixtureApi.sources();return {{...r,sources:r.sources.map(s=>s.key==={json.dumps(source)}
          ?{{...s,operation:{{operation:'process',status:'processing',phase:'Rendering previews',progress:.42,completed:4,total:10}}}}:s)}}}});lal.loadSources();true""")
        wait("$('activity')?.textContent.includes('Processing')&&$('activity').textContent.includes('42%')&&$('activity').textContent.includes('+1')", 10)
        js("$('activity').click();true")
        wait("count('#activity-panel [data-activity]')===2&&Boolean(document.querySelector('#activity-panel button[data-activity]'))")
        assert js("(()=>{const p=$('activity-panel').getBoundingClientRect();return [...document.querySelectorAll('#activity-panel [data-activity] *:not(.activity-sweep)')].every(e=>e.getBoundingClientRect().right<=p.right+.5)})()"), 'Activity rows overflow the panel'
        both('08-activity-panel')
        done('The top-bar mark names the main task with its progress, counts the others and lists them on click')
        js("document.querySelector('#activity-panel button[data-activity]').click();true")
        wait(f"lal.state.history[lal.state.historyIndex].page==='processing'&&lal.state.history[lal.state.historyIndex].focus==={json.dumps(source)}")
        done('A source operation in the list opens Asset processing at that source')
        js("restore('sources');restore('changes');true")
        wait("Boolean($('activity')?.querySelector('.bg-success'))", 10)
        ui.capture('09-activity-finished.png', settle=.1)
        wait("!$('activity')", 10)
        done('When the work ends the mark turns into a check, then leaves')

        # Asset processing before the first sources answer.
        js("hold('sources');lal.setState({sourcesLoaded:false});lal.navigate({page:'home'});lal.navigate({page:'processing'});true")
        wait("count('#source-warnings-loading .skeleton')>0&&!document.querySelector('#processing-view [data-action=process]')&&!$('processing-view').textContent.includes('No asset sources yet')")
        both('10-processing-ghosts')
        js("release('sources')")
        wait("!$('source-warnings-loading')&&count('#source-warnings [data-source]')>=2")
        done('Asset processing shows ghost source cards before its first answer, never "No asset sources yet"')

        # Reduced motion: the bundled media rule stops shimmer, sheen and the activity orbit.
        reduced = js("""(async()=>{const rule=[...document.styleSheets].flatMap(s=>[...s.cssRules]).find(r=>r.conditionText?.includes('prefers-reduced-motion')&&r.cssText.includes('.skeleton::after'));
          if(!rule)return false;const style=document.createElement('style');style.textContent=[...rule.cssRules].map(r=>r.cssText).join('');document.head.append(style);
          hold('collections');lal.setState({collections:{items:[],total:0,loading:false,loaded:false,error:null,query:''}});lal.navigate({page:'collections'});
          await until(()=>document.querySelector('#collections-loading .skeleton'));
          const el=document.querySelector('#collections-loading .skeleton');const ok=getComputedStyle(el,'::after').display==='none'&&getComputedStyle(el.closest('.ghost-enter')).animationName==='none';
          release('collections');style.remove();return ok})()""")
        assert reduced
        done('Reduced motion keeps static ghosts with no shimmer or entrance animation (bundled rule applied in WebView2; OS preference unchanged)')

        assert not bridge._gateway.model_requested
        done('No model loaded')
        report.update(status='passed')
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        (OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)
