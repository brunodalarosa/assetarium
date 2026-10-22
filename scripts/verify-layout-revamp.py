"""Real WebView2 check of the Assetarium layout: shell, history, search, filters, inspection, notifications, themes.

Synthetic assets only. Sources and notifications on the processing screens are synthetic bridge
answers, so no scan, processing or model run starts. Writes data/gui/<run-name>/report.json and screenshots.
"""
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
from local_asset_library.settings import save_general_settings
save_general_settings(config, 40)  # Fixture-local settings.json, so Settings → General has saved values.
stream = BytesIO()
Image.new('RGB', (64, 48), '#c98a4b').save(stream, format='PNG')
image = base64.b64encode(stream.getvalue()).decode('ascii')


class FixtureBridge(DesktopBridge):
    def thumbnail(self, identifier, version=None):
        return {'image': image, 'payload': {'card': {'format': 'glb', 'triangles': 1248}}}


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
bridge = FixtureBridge(config)
import webview
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': {}, 'screenshots': [], 'synthetic_only': True,
          'owner_visual_review': 'pending', 'real_model_load': False}

JS_HELPERS = """window.until=async(fn,ms=10000)=>{const end=Date.now()+ms;while(Date.now()<end){try{if(fn())return true}catch(e){}
  await new Promise(r=>setTimeout(r,40))}throw Error('Timed out: '+fn)};
window.frame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
window.$=id=>document.getElementById(id);true"""


def js(script, timeout=60):
    done, values = threading.Event(), []
    def callback(value):
        values.append(value)
        done.set()
    # pywebview reports through the callback only when the script yields a promise.
    window.evaluate_js('(async()=>{try{const value=await eval(%s);return value===undefined?null:value}'
                       'catch(error){return {__error:String(error&&error.stack||error)}}})()' % json.dumps(script), callback)
    if not done.wait(timeout):
        raise RuntimeError('UI check completion timeout')
    if isinstance(values[0], dict) and '__error' in values[0]:
        raise RuntimeError('UI script fault: ' + values[0]['__error'])
    return values[0]


def check(name, script):
    value = js(script)
    report['checks'][name] = value
    assert value is True or (isinstance(value, dict) and all(value.values())), {name: value}


def capture(name):
    time.sleep(.45)  # Let spring transitions settle before the screenshot.
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
    report['screenshots'].append(name)


SYNTHETIC_SOURCES = {'status': 'ready', 'revision': 'synthetic', 'scan': {}, 'sources': [
    {'key': 'village', 'name': 'Village kit', 'path': 'D:/Assets/Village kit', 'enabled': True, 'scanned': True,
     'needs_processing': True, 'pending': 12, 'format_counts': {'gltf': 64, 'fbx': 12}, 'import_types': ['model_3d'],
     'descriptions': {'complete': 20, 'missing': 24, 'failed': 0}, 'operation': {}},
    {'key': 'props', 'name': 'Dungeon props', 'path': 'D:/Assets/Dungeon props', 'enabled': True, 'scanned': True,
     'needs_processing': False, 'failed': 3, 'format_counts': {'obj': 31}, 'import_types': ['model_3d', 'image'],
     'descriptions': {'complete': 28, 'missing': 0, 'failed': 3},
     'operation': {'operation': 'describe', 'status': 'faulty', 'reason': 'Not enough GPU memory.'}}],
    'notifications': [
        {'id': 'ready-village', 'kind': 'descriptions_ready', 'source_key': 'village', 'source_name': 'Village kit',
         'missing': 24, 'read': False, 'created_utc': '2026-10-21T10:00:00Z'},
        {'id': 'report-a', 'kind': 'descriptions_report', 'source_key': 'village', 'source_name': 'Village kit',
         'outcome': 'complete', 'written': 20, 'read': True, 'created_utc': '2026-10-21T09:48:00Z'},
        {'id': 'report-b', 'kind': 'descriptions_report', 'source_key': 'props', 'source_name': 'Dungeon props',
         'outcome': 'stopped', 'reason': 'Not enough GPU memory.', 'written': 28, 'remaining': 3, 'read': True,
         'created_utc': '2026-10-20T18:00:00Z'}]}


def verify():
    try:
        deadline = time.perf_counter() + 30
        while not window.evaluate_js('Boolean(window.lal && lal.state.ready && lal.state.context)'):
            if time.perf_counter() > deadline:
                raise RuntimeError('Startup timeout')
            time.sleep(.1)
        assert window.gui.renderer == 'edgechromium'
        js(JS_HELPERS)
        async def semantic(name, arguments):
            payload, image_data, evidence = AssetService(config, backend=backend).execute(name, arguments)
            return dict(payload=payload, image=image_data, evidence=evidence, is_error=False)
        bridge._gateway.semantic = semantic

        check('startup_home_idle', """(()=>({home:lal.state.history[0].page==='home',idle:lal.state.search.phase==='idle',
          noGrid:!$('grid'),query:!!$('query'),theme:['light','dark'].includes(document.documentElement.dataset.theme),
          font:getComputedStyle(document.body).fontFamily.includes('Geist'),noChips:!document.querySelector('[data-chip]'),
          rail:['nav-home','nav-library','nav-collections','nav-processing','nav-settings'].every(id=>$(id)),
          backDisabled:document.querySelector('[aria-label=Back]').disabled}))()""")
        js("lal.setAppearance('light')")
        capture('01-home-light.png')

        check('filters_open', """(async()=>{$('open-filters').click();await until(()=>$('filters-panel'));await frame();
          const ids=['asset-type','pack','format','triangles','rigged','transparent','size-class','mode','limit'];
          return {nine:ids.every(id=>$(id)),mode:$('mode').dataset.value==='combined',limit:$('limit').dataset.value==='20',
            focus:document.activeElement?.id==='filters-title'}})()""")
        capture('02-filters-open.png')
        check('limit_choices', """(async()=>{$('limit').querySelector('button').click();await frame();
          const options=[...$('limit').querySelectorAll('[role=option]')].map(o=>o.textContent);
          document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));
          return options.join(',')==='5,10,20,30,40'})()""")
        check('filters_close', """(async()=>{window.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
          await until(()=>!$('filters-panel'));return true})()""")

        check('search_results', """(async()=>{lal.setQuery('obj');await lal.submitSearch();await until(()=>document.querySelectorAll('#grid .card').length===20);
          return {phase:lal.state.search.phase==='search',settings:(s=>s.query==='obj'&&s.mode==='combined'&&s.limit===20&&JSON.stringify(s.filters)==='{}')(lal.state.search.lastSettings),
            header:$('results-title').textContent==='20 results',compact:!!$('query')}})()""")
        js("until(()=>document.querySelectorAll('#grid .thumb img').length>=6)")
        capture('03-search-results.png')

        check('inspection_empty', """(async()=>{$('toggle-inspector').click();await until(()=>$('inspector'));await frame();
          return {empty:!!document.querySelector('.detail-empty'),pressed:$('toggle-inspector').getAttribute('aria-pressed')==='true'}})()""")
        capture('04-inspection-empty.png')

        check('inspection_selected', """(async()=>{document.querySelector('#grid .card').click();await until(()=>document.querySelector('.detail-header h2'));
          await until(()=>!lal.state.library.detail.loading);await frame();
          return {heading:document.activeElement===document.querySelector('.detail-header h2'),
            pressed:document.querySelector('#grid .card').getAttribute('aria-pressed')==='true',
            tabs:[...document.querySelectorAll('#inspector [role=tab]')].map(t=>t.id).join(',')==='inspector-tab-overview,inspector-tab-sources,inspector-tab-evidence',
            preview:!!document.querySelector('#inspector .preview-still')}})()""")
        capture('05-inspection-selected.png')
        check('inspection_resize', """(async()=>{lal.setInspectorWidth(600);await frame();const w=$('inspector').getBoundingClientRect().width;
          const sep=document.querySelector('[role=separator]');return {width:Math.abs(w-624)<2,separator:sep.getAttribute('aria-valuenow')==='600'}})()""")
        capture('06-inspection-wider.png')
        js("lal.setInspectorWidth(440)")
        check('evidence_tab', """(async()=>{$('inspector-tab-evidence').click();await frame();
          return {panel:!$('inspector-panel-evidence').hidden,faults:!!document.querySelector('#inspector .fault-list'),review:$('inspector-panel-evidence').textContent.includes('Owner review')}})()""")
        capture('10-inspection-evidence.png')
        check('hide_keeps_selection', """(async()=>{const id=lal.state.library.selected;$('toggle-inspector').click();await until(()=>!$('inspector'));
          const kept=lal.state.library.selected===id;$('toggle-inspector').click();await until(()=>$('inspector-panel-evidence'));
          return {kept,tab:!$('inspector-panel-evidence').hidden,highlight:document.querySelector('#grid .card[aria-pressed=true]')?.dataset.id===id}})()""")
        js("$('toggle-inspector').click()")
        capture('07-inspection-hidden-selection-retained.png')
        js("$('toggle-inspector').click()")
        js("$('inspector-tab-overview').click()")

        js("""window.fixtureApi=lal.state.api;const synthetic=%s;
          lal.setState({api:Object.assign(Object.create(fixtureApi),{sources:async()=>structuredClone(synthetic),importing_failures:async()=>({status:'ready',assets:2,paths:['D:/Assets/Dungeon props/broken_door.obj','D:/Assets/Dungeon props/torn_banner.png']}),
            notification_action:async()=>({status:'saved',notifications:structuredClone(synthetic.notifications)})})});""" % json.dumps(SYNTHETIC_SOURCES))
        js("lal.loadSources()")
        check('notifications_panel', """(async()=>{await until(()=>lal.state.notifications.length===3);$('open-notifications').click();await until(()=>$('notifications-panel'));await frame();
          return {items:document.querySelectorAll('#notifications-list .notification').length===3,focus:document.activeElement?.id==='notifications-title',
            generate:!!document.querySelector('[data-action=generate]'),report:!!document.querySelector('[data-action=report]')}})()""")
        capture('09-notifications-over-inspection.png')
        check('notification_opens_processing', """(async()=>{document.querySelector('[data-action=report]').click();await until(()=>$('processing-view'));
          await until(()=>lal.state.runReport);await until(()=>!$('notifications-panel'));await frame();return {page:lal.state.history[lal.state.historyIndex].page==='processing',
            focus:lal.state.history[lal.state.historyIndex].focus==='props',report:document.querySelector('dialog[open]')?.textContent.includes('batch size')===true,
            panelClosed:!$('notifications-panel')}})()""")
        capture('13-run-report.png')
        js("lal.setState({runReport:null})")
        check('processing_page', """(async()=>{await until(()=>$('import-failures-summary').textContent.includes('2 assets'));
          return {process:!!document.querySelector('[data-action=process][data-source=village]'),describe:!!document.querySelector('[data-action=describe][data-source=village]'),
            describeBlocked:document.querySelector('[data-action=describe][data-source=props]').disabled,attentionDot:$('nav-processing').getAttribute('aria-label').includes('attention')}})()""")
        capture('14-asset-processing.png')

        check('history', """(async()=>{lal.goBack();await until(()=>$('library-view'));const back=!!document.querySelector('#grid .card');
          const fwd=!document.querySelector('[aria-label=Forward]').disabled;lal.goForward();await until(()=>$('processing-view'));
          lal.navigate({page:'library'});await until(()=>$('library-view'));lal.navigate({page:'collections'});await until(()=>$('collections-view'));
          lal.goBack();lal.goBack();await until(()=>$('processing-view'));return {back,fwd,forwardAfter:!document.querySelector('[aria-label=Forward]').disabled}})()""")
        js("lal.navigate({page:'home'})")
        js("until(()=>$('library-view'))")
        js("lal.clearSearch()")
        capture('12-home-forward-history.png')
        check('settings_general', """(async()=>{lal.navigate({page:'settings',tab:'general'});await until(()=>$('settings-view')&&lal.state.general.values);await frame();
          return {appearance:$('appearance-light').getAttribute('aria-checked')==='true',budget:!!$('storage-budget').value,formats:!!$('processing-format-fbx')}})()""")
        capture('15-settings-general.png')
        js("$('asset-sources-tab').click()")
        js("until(()=>document.querySelectorAll('.source-row').length===2)")
        capture('16-settings-asset-sources.png')

        # Smallest supported desktop window: inspection floats over the results instead of squeezing them.
        window.resize(700, 520)
        time.sleep(1)
        check('narrow_window', """(async()=>{lal.navigate({page:'home'});await until(()=>$('library-view'));await frame();
          const panel=$('inspector');return {overlay:!panel||getComputedStyle(panel).position==='absolute',
            noHorizontalScroll:$('library-view').scrollWidth<=$('library-view').clientWidth+1}})()""")
        capture('17-narrow-window.png')
        window.resize(1280, 860)
        time.sleep(1)

        # Dark theme across the same key screens.
        check('dark_theme', """(async()=>{await lal.setAppearance('dark');await frame();return document.documentElement.dataset.theme==='dark'&&
          getComputedStyle(document.body).backgroundColor==='rgb(16, 21, 30)'})()""")
        capture('d15-settings-general.png')
        js("lal.navigate({page:'home'})")
        js("until(()=>$('library-view'))")
        capture('d01-home.png')
        js("(async()=>{$('open-filters').click();await until(()=>$('filters-panel'))})()")
        capture('d02-filters-open.png')
        js("lal.setFiltersOpen(false)")
        # Thumbnails load only for visible cards; the open inspector leaves two columns here.
        check('lazy_thumbnails', """(async()=>{lal.setQuery('obj');await lal.submitSearch();await until(()=>document.querySelectorAll('#grid .thumb img').length>=4);
          await new Promise(r=>setTimeout(r,800));return {visibleOnly:Object.keys(lal.state.library.thumbs).length<lal.state.library.items.length}})()""")
        js("(async()=>{document.querySelector('#grid .card').click();await until(()=>lal.state.library.detail&&!lal.state.library.detail.loading)})()")
        capture('d05-inspection-selected.png')
        js("(async()=>{$('open-notifications').click();await until(()=>$('notifications-panel'))})()")
        capture('d09-notifications-over-inspection.png')
        js("lal.setNotificationsOpen(false)")
        js("lal.navigate({page:'processing'})")
        js("until(()=>$('processing-view'))")
        capture('d14-asset-processing.png')
        check('appearance_saved', "(async()=>{const r=await fixtureApi.interface_settings();return r.appearance==='dark'})()")
        js("lal.setAppearance('system')")
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
