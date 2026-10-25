"""Focused actual WebView2 search lifecycle verification; synthetic assets only."""
import argparse
from io import BytesIO
import base64
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_retrieval import indexed
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.mcp_assets import AssetService
from PIL import Image
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
report = {'status': 'running', 'synthetic_only': True, 'owner_windows_validation': 'pending', 'real_model_load': False}
ui = Harness(window, OUT, report)


def verify():
    try:
        ui.wait_ready()
        report['startup'] = ui.check('startup_defaults', """(async()=>{$('open-filters').click();await until(()=>$('limit'));
          $('limit').querySelector('[aria-haspopup=listbox]').click();await frame();
          const choices=[...$('limit').querySelectorAll('[role=option]')].map(o=>o.dataset.listboxId);lal.setFiltersOpen(false);
          return {mode:lal.state.filters.mode==='combined',limit:lal.state.filters.limit==='20',choices:choices.join()==='5,10,20,30,40'}})()""")
        # Actual shared bridge paths, with synthetic query inference and unchanged published generation.
        async def semantic(name, arguments):
            payload, image, evidence = AssetService(config, backend=backend).execute(name, arguments)
            return dict(payload=payload, image=image, evidence=evidence, is_error=False)
        bridge._gateway.semantic = semantic
        agreement = ui.js("""(async()=>{lal.setQuery('obj');await lal.submitSearch();const original=structuredClone(lal.state.search.lastSettings);
          lal.setQuery('unsent edit');return {settings:original,ids:lal.state.library.items.map(x=>x.asset_id),saved:lal.state.search.lastSettings};})()""")
        assert agreement['settings'] == agreement['saved'] == {'query': 'obj', 'mode': 'combined', 'limit': 20, 'filters': {}}
        replay, _, _ = AssetService(config, backend=backend).execute('search_assets', agreement['settings'])
        assert agreement['ids'] == [r['asset_id'] for r in replay['results']] and len(agreement['ids']) == 20
        report['copied_settings_reproduction'] = agreement
        # Defer resolution to observe the real packaged UI before model-load/search completion.
        ui.js("""(async()=>{window.pending=[];window.busyChecks={};
          stubApi({search:args=>new Promise((resolve,reject)=>pending.push({args,resolve,reject}))});
          lal.setQuery('slow');window.firstSearch=lal.search();await frame();
          busyChecks.immediate=!$('search-busy').hidden&&$('submit').disabled&&$('grid').getAttribute('aria-busy')==='true';
          busyChecks.preserved=lal.state.library.items.length===20&&document.querySelectorAll('#grid .card').length===20;
          busyChecks.announcement=$('search-busy').getAttribute('role')==='status'&&$('search-busy').textContent.includes('Searching');
          lal.search();busyChecks.duplicate=pending.length===1;return true})()""")
        ui.capture('searching.png', settle=.3)
        assert ui.js("getComputedStyle(document.querySelector('#search-busy .search-spinner')).animationName") == 'search-spin'
        outcomes = ui.js("""(async()=>{const assert=(value,name)=>{busyChecks[name]=Boolean(value);if(!value)throw Error(name)};
          const finish=(job,results=[])=>job.resolve({arguments:job.args,elapsed_seconds:.3,payload:{generation:lal.state.context.generation,results,fault_count:0,truncated:false}});
          const idle=()=>$('search-busy').hidden&&!$('submit').disabled;
          // A new request supersedes the first; old completion must not clear the new busy state.
          lal.setQuery('new');const newer=lal.search();finish(pending[0]);await firstSearch;await frame();
          assert(!$('search-busy').hidden&&$('submit').disabled,'old_completion_keeps_new_busy');
          finish(pending[1]);await newer;await frame();assert(idle()&&lal.state.library.items.length===0&&$('empty'),'empty_completion');
          lal.setQuery('failed');const failed=lal.search();pending[2].reject(Error('Synthetic search failure'));await failed;await frame();
          assert(idle()&&$('error').textContent.includes('Synthetic search failure'),'error_completion');
          // Clearing returns Home to its idle search and keeps the chosen filters.
          lal.setQuery('clear race');const clearing=lal.search();await frame();$('clear').click();finish(pending[3]);await clearing;
          await new Promise(resolve=>setTimeout(resolve,300));
          assert(idle()&&lal.state.search.phase==='idle'&&!$('grid')&&lal.state.filters.mode==='combined'&&lal.state.filters.limit==='20','clear_reset');
          lal.setQuery('refresh race');const refreshing=lal.search();const reload=lal.refreshContext(true);finish(pending[4]);await refreshing;
          // Refresh replays an active search against the current publication.
          // Resolve that new request too; leaving it pending deadlocks the harness.
          while(pending.length<6)await new Promise(resolve=>setTimeout(resolve,10));
          finish(pending[5]);await reload;await frame();
          assert(idle()&&lal.state.search.lastSettings.query==='refresh race','refresh_supersedes');
          lal.setQuery('success');const successful=lal.search();finish(pending[6],[{asset_id:'fixture',name:'fixture',pack:'synthetic',caption_owner_review:'pending'}]);await successful;await frame();
          assert(idle()&&lal.state.library.items[0].asset_id==='fixture'&&document.querySelector('#grid .card')?.dataset.id==='fixture','success_completion');
          return busyChecks;})()""")
        assert all(outcomes.values()), outcomes
        report['lifecycle'] = outcomes
        # Apply the exact bundled reduced-motion rule to inspect its renderer behavior.
        reduced = ui.js("""(async()=>{const rule=[...document.styleSheets].flatMap(s=>[...s.cssRules]).find(r=>r.conditionText?.includes('prefers-reduced-motion')&&[...(r.cssRules||[])].some(x=>x.selectorText==='.search-spinner'));
          if(!rule)return false;const style=document.createElement('style');style.textContent=[...rule.cssRules].map(r=>r.cssText).join('');document.head.append(style);
          lal.setQuery('static');const pendingSearch=lal.search();await frame();
          return getComputedStyle(document.querySelector('#search-busy .search-spinner')).animationName==='none'&&!$('search-busy').hidden;})()""")
        assert reduced
        report['reduced_motion'] = 'Bundled media rule verified statically and applied in WebView2; OS preference not changed'
        ui.capture('static-busy.png')
        ui.js("pending.at(-1).resolve({arguments:pending.at(-1).args,elapsed_seconds:.1,payload:{generation:lal.state.context.generation,results:[],fault_count:0,truncated:false}});lal.setState({api:fixtureApi});true")
        assert not bridge._gateway.model_requested
        report['checks_summary'] = ['Actual packaged WebView2 startup/default options', 'Shared bridge copied settings reproduce 20 results',
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
print(json.dumps({k: report[k] for k in ('status', 'reason') if k in report}, indent=2))
sys.exit(0 if report['status'] == 'passed' else 1)
