"""Actual WebView2 live 3D preview checks with tiny synthetic model sources."""
import argparse
import base64
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_retrieval import indexed
from test_mcp_assets import update
from local_asset_library.captions import file_hash
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from PIL import Image, ImageChops
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
parser.add_argument('--real-assets', action='store_true', help='Read-only representative library checks; no processing or retries')
args = parser.parse_args()
if not args.run_name.replace('-','').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
if not args.real_assets:
    fixture = ROOT / 'scratch' / args.run_name
    fixture.mkdir(parents=True, exist_ok=False)
    config, backend, records = indexed.__wrapped__(fixture)
    record = deepcopy(records[0])
    record['display_name'] = 'Café — carré ◇ 工具'
    record['pack_id'] = 'kenney_even'
    source = config.source_file(record['files'][0]['path'])
    source.write_text('mtllib preview.mtl\nv -1 0 -1\nv 1 0 -1\nv 0 2 0\nv 0 0 1\n'
        'vt 0 0\nvt 1 0\nvt 0.5 1\nusemtl Red\nf 1/1 3/3 2/2\nf 1/1 2/2 4/3\nf 2/1 3/3 4/2\nf 3/1 1/2 4/3\n')
    material = source.with_name('preview.mtl')
    material.write_text('newmtl Red\nKd 1 1 1\nmap_Kd preview.png\n')
    texture = source.with_name('preview.png')
    Image.new('RGBA',(4,4),'#d64536').save(texture)
    record['files'][0]['sha256'] = file_hash(source)
    record['technical']['inspected_sha256'] = file_hash(source)
    record['dependencies'] = [
        {'path': material.relative_to(config.source_root).as_posix(), 'from':record['files'][0]['path'],
         'sha256':file_hash(material), 'status':'available','role':'material'},
        {'path': texture.relative_to(config.source_root).as_posix(), 'from':material.relative_to(config.source_root).as_posix(),
         'sha256':file_hash(texture), 'status':'available','role':'texture'}]
    positions = struct.pack('<12f',-1,0,-1,1,0,-1,0,2,0,0,0,1)
    indices = struct.pack('<12H',0,2,1,0,1,3,1,2,3,2,0,3)
    buffer = positions + indices
    gltf = {'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],
            'nodes':[{'mesh':0}], 'buffers':[{'byteLength':len(buffer)}],
            'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':len(positions),'target':34962},
                           {'buffer':0,'byteOffset':len(positions),'byteLength':len(indices),'target':34963}],
            'accessors':[{'bufferView':0,'componentType':5126,'count':4,'type':'VEC3','min':[-1,0,-1],'max':[1,2,1]},
                         {'bufferView':1,'componentType':5123,'count':12,'type':'SCALAR'}],
            'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1,'material':0}]}],
            'materials':[{'pbrMetallicRoughness':{'baseColorFactor':[0.2,0.65,0.4,1],'metallicFactor':0,'roughnessFactor':0.7}}]}
    json_bytes = json.dumps(gltf).encode()
    json_bytes += b' ' * (-len(json_bytes) % 4)
    glb_bytes = struct.pack('<III',0x46546c67,2,12+8+len(json_bytes)+8+len(buffer))
    glb_bytes += struct.pack('<II',len(json_bytes),0x4e4f534a)+json_bytes
    glb_bytes += struct.pack('<II',len(buffer),0x004e4942)+buffer
    glb = source.with_suffix('.glb')
    glb.write_bytes(glb_bytes)
    record['files'].append({'path':glb.relative_to(config.source_root).as_posix(),'format':'glb',
                            'sha256':file_hash(glb),'availability':'available'})
    png = config.output_path('data',record['asset_id']+'-preview.png')
    Image.new('RGB',(64,64),'#c5daca').save(png)
    record['previews'] = [{'path':'data/'+png.name,'sha256':file_hash(png),'view_label':'three_quarter'}]
    update(config,record)
    image = base64.b64encode(png.read_bytes()).decode()
    # A BLEND-only asset: the viewer cannot open it, so the panel shows renders and says why.
    blend = deepcopy(records[4])
    blend_file = config.source_file(blend['files'][0]['path']).with_suffix('.blend')
    blend_file.write_bytes(b'BLENDER-v300 synthetic; never opened by the viewer')
    blend['files'] = [{'path':blend_file.relative_to(config.source_root).as_posix(),'format':'blend',
                       'sha256':file_hash(blend_file),'availability':'available'}]
    blend['dependencies'] = []
    update(config,blend)
    # A valid OBJ padded past the 16 MiB auto-load cap with comment lines.
    large = deepcopy(records[3])
    large_file = config.source_file(large['files'][0]['path'])
    with large_file.open('w') as stream:
        stream.write('v -1 0 -1\nv 1 0 -1\nv 0 2 0\nv 0 0 1\nf 1 3 2\nf 1 2 4\nf 2 3 4\nf 3 1 4\n')
        line = '#' + 'x' * 1022 + '\n'
        for _ in range(17 * 1024):
            stream.write(line)
    large['files'] = [dict(large['files'][0],sha256=file_hash(large_file))]
    large['dependencies'] = []
    large['technical']['inspected_sha256'] = file_hash(large_file)
    update(config,large)
else:
    from local_asset_library.config import load_project_config
    from local_asset_library.membership import records as library_records
    from local_asset_library.settings import interface_settings
    config = load_project_config(ROOT)
    records = library_records(config)
    image = None
    hint_before = interface_settings(config)['preview_hint_seen']



class FixtureBridge(DesktopBridge):
    delay = False
    unblock = threading.Event()
    def thumbnail(self, identifier, version=None):
        if args.real_assets:
            return super().thumbnail(identifier,version)
        return {'image':image,'payload':{}}
    def context(self):
        result=super().context()
        result['managed_sources']=False  # Verification never starts source scans or processing.
        return result
    def sources(self):
        from local_asset_library.sources import revision
        return {'status':'ready','sources':[],'revision':revision(self._config)}
    def preview_prepare(self, asset_id, source_format, expected_version):
        if self.delay:
            self.unblock.wait(15)
        return super().preview_prepare(asset_id,source_format,expected_version)


os.environ.update(PYTHONNET_RUNTIME='netfx',TEMP=str(ROOT/'scratch/tmp-mcp'),TMP=str(ROOT/'scratch/tmp-mcp'))
bridge = FixtureBridge(config)
import webview
window = create_window(config,bridge)
profile = profile_path(config,bridge,window)
report = {'status':'running','checks':[],'synthetic_only':not args.real_assets,'owner_usability_approval':'pending'}


ui = Harness(window, OUT, report)
js = ui.js


def wait(expression, timeout=30):
    try:
        ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)
    except RuntimeError as exc:
        detail = window.evaluate_js("({error:lal.state.search.error,status:LALPreview.current?.status.textContent,warning:LALPreview.current?.warning.textContent,loading:LALPreview.current?.loadingText})")
        raise RuntimeError('UI condition timed out: '+expression+' '+json.dumps(detail)) from exc


def capture(name):
    ui.capture(name, settle=.2)
    return OUT / name


def select(identifier, fmt=None):
    """Select through the store, then wait until the inspector has mounted that asset's preview."""
    target = json.dumps(identifier)
    js(f"(async()=>{{await lal.selectAsset('library',{target},{json.dumps(fmt)});return true;}})()")
    wait(f"lal.state.library.detail&&!lal.state.library.detail.loading&&LALPreview.current?.item.assetId==={target}"
         + (f"&&LALPreview.current.item.sourceFormat==={json.dumps(fmt)}" if fmt else ''))

def check(name):
    report['checks'].append(name)


def browser_input(method, parameters):
    """Dispatch actual WebView2 input, including into the opaque-origin frame."""
    from System import Action
    from System.Threading.Tasks import Task
    form = window.gui.BrowserView.instances[window.uid]
    done, errors = threading.Event(), []
    def start():
        task = form.browser.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(method,json.dumps(parameters))
        def finish(task):
            if task.IsFaulted: errors.append(str(task.Exception))
            done.set()
        task.ContinueWith(Action[Task](finish),form.browser.syncContextTaskScheduler)
    form.Invoke(Action(start))
    assert done.wait(15) and not errors, errors


def key(name, code, vk, modifiers=0):
    browser_input('Input.dispatchKeyEvent',dict(type='keyDown',key=name,code=code,windowsVirtualKeyCode=vk,modifiers=modifiers))
    browser_input('Input.dispatchKeyEvent',dict(type='keyUp',key=name,code=code,windowsVirtualKeyCode=vk))


def stats():
    return window.evaluate_js('({...LALPreview.stats})')


def changed_pixels(before,after):
    rect=window.evaluate_js('(()=>{const r=LALPreview.current.viewport.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,dpr:devicePixelRatio};})()')
    # Native captures use device pixels; WebView2 input coordinates use CSS pixels.
    box=tuple(round(value*rect['dpr']) for value in (rect['x']+5,rect['y']+5,rect['x']+rect['w']-5,rect['y']+rect['h']-5))
    diff=ImageChops.difference(Image.open(before).convert('RGB').crop(box),Image.open(after).convert('RGB').crop(box))
    return sum(1 for r,g,b in diff.get_flattened_data() if max(r,g,b)>25)


SETTLED = 'Boolean(LALPreview.current?.ready || LALPreview.current?.retainedFault || (LALPreview.current && !LALPreview.current.loadingText && !LALPreview.current.status.hidden))'


def verify():
    if args.real_assets:
        return verify_real()
    try:
        ui.wait_ready()
        # The fixture has no registered sources, so setup opens; it owns the window until closed.
        js("(async()=>{if(lal.state.setup.open)lal.closeSetup();await until(()=>!lal.state.setup.open);return true})()")
        js("(async()=>{await lal.submitSearch();await until(()=>lal.state.library.items.length===40);lal.closeDetail('library');lal.setInspectorOpen(true);await until(()=>$('detail'));return true})()")
        assert js("$('page-info').textContent") == '1–40 of 40'
        assert js("$('detail').querySelector('.detail-empty h2').textContent") == 'No asset selected'
        assert ' · ' in js('lal.state.coverage')
        capture('00-library-text.png')
        identifier=json.dumps(record['asset_id'])
        # The still shows at once and the live view loads by itself, without a click.
        bridge.unblock.clear(); bridge.delay=True
        select(record['asset_id'])
        assert js("$('detail').querySelector('.detail-header h2').textContent") == record['display_name']
        assert js("$('detail').querySelector('.pack').textContent") == 'Kenney · even'
        assert window.evaluate_js("Boolean(LALPreview.current.still.src) && !LALPreview.current.stage.classList.contains('live')")
        assert not window.evaluate_js("[...document.querySelectorAll('#detail button')].some(b=>/interactive 3D|Back to image/.test(b.textContent))")
        assert not window.evaluate_js("Boolean($('detail-view'))")
        wait("Boolean(LALPreview.current.loadingText)")
        capture('01-still-then-loading.png')
        bridge.delay=False; bridge.unblock.set()
        wait('Boolean(LALPreview.current?.ready)',60)
        wait("getComputedStyle(LALPreview.current.viewport).opacity==='1'")
        assert window.evaluate_js('LALPreview.current.summary.triangles')==4
        assert window.evaluate_js('LALPreview.current.fileReads')==3
        assert window.evaluate_js('LALPreview.current.warning.hidden')
        report['live_ms_obj_with_held_prepare']=window.evaluate_js('LALPreview.current.liveMs')
        report['inline_frame']=window.evaluate_js("({sandbox:LALPreview.current.frame.getAttribute('sandbox'),source:LALPreview.current.manifest.source_name})")
        assert report['inline_frame']['sandbox']=='allow-scripts'
        assert not window.evaluate_js('LALPreview.current.hint.hidden')
        capture('02-live-inline.png')
        check('Selecting shows the still at once, then the live OBJ (MTL + texture) crossfades in without a click')
        check('The first live view shows the controls hint')
        # View buttons move the live camera; nothing reloads.
        window.evaluate_js('window.originalPreviewFrame=LALPreview.current.frame;window.originalSession=LALPreview.current.session')
        before=capture('02a-before-top.png')
        window.evaluate_js("LALPreview.current.viewButtons[3].click()")
        wait("LALPreview.current.viewButtons[3].getAttribute('aria-pressed')==='true'")
        top=capture('02b-top.png')
        report['top_changed_pixels']=changed_pixels(before,top)
        assert report['top_changed_pixels']>300
        assert window.evaluate_js('originalPreviewFrame===LALPreview.current.frame && LALPreview.current.fileReads===3')
        assert window.evaluate_js("lal.state.library.detail.view")=='three_quarter'
        check('View buttons move the live camera without reloading the model or the inspection')
        window.evaluate_js("LALPreview.current.more.click()")
        assert window.evaluate_js("!LALPreview.current.menu.hidden && document.activeElement===LALPreview.current.menuControls[0]")
        capture('02c-menu.png')
        key('Escape','Escape',27)
        assert window.evaluate_js("LALPreview.current.menu.hidden && document.activeElement===LALPreview.current.more")
        assert window.evaluate_js('lal.state.inspector.open')
        check('The canvas menu opens on its first control and Escape closes it without hiding the inspector')
        js('(async()=>{await LALPreview.current.enterFullscreen();return true;})()')
        wait('LALPreview.current.fullscreen')
        assert window.evaluate_js('originalPreviewFrame===LALPreview.current.frame && originalSession===LALPreview.current.session')
        assert window.evaluate_js('LALPreview.current.fileReads')==3
        assert window.evaluate_js('LALPreview.current.dialog.getBoundingClientRect().width>=innerWidth-2')
        window.evaluate_js("LALPreview.current.viewButtons[0].click()")
        time.sleep(.3)
        full_image=capture('03-fullscreen.png')
        # A real rendered red model must occupy pixels, beyond DOM/loader success.
        rendered=Image.open(full_image).convert('RGB')
        red=sum(1 for r,g,b in rendered.get_flattened_data() if r>g*1.4 and r>b*1.3 and r>80)
        assert red>500, ('No visible textured model',red)
        report['rendered_model_pixels']=red
        check('Fullscreen preserves the same renderer, source reads and camera session')
        rect=window.evaluate_js('(()=>{const r=LALPreview.current.frame.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()')
        browser_input('Input.dispatchMouseEvent',dict(type='mousePressed',**rect,button='left',buttons=1,clickCount=1))
        moved={'x':rect['x']+110,'y':rect['y']+40}
        browser_input('Input.dispatchMouseEvent',dict(type='mouseMoved',**moved,button='left',buttons=1))
        browser_input('Input.dispatchMouseEvent',dict(type='mouseReleased',**moved,button='left',buttons=0,clickCount=1))
        rotated=capture('03a-rotated.png')
        report['rotation_changed_pixels']=changed_pixels(full_image,rotated)
        assert report['rotation_changed_pixels']>1000
        wait('LALPreview.current.hint.hidden')
        assert bridge.interface_settings()['preview_hint_seen'] is True
        check('The hint retires (first gesture or 8 s) and is remembered app-wide')
        browser_input('Input.dispatchMouseEvent',dict(type='mouseWheel',**rect,deltaY=-180,deltaX=0))
        zoomed=capture('03b-zoomed.png')
        report['zoom_changed_pixels']=changed_pixels(rotated,zoomed)
        assert report['zoom_changed_pixels']>1000
        key('ArrowLeft','ArrowLeft',37)
        keyboard=capture('03c-keyboard-orbit.png')
        report['keyboard_changed_pixels']=changed_pixels(zoomed,keyboard)
        assert report['keyboard_changed_pixels']>500
        check('Native mouse drag, wheel zoom and keyboard orbit change the rendered model')
        window.evaluate_js('LALPreview.current.full.focus()')
        for _ in range(12):
            key('Tab','Tab',9)
            # Wrapping past the modal's last control leaves the document briefly (body); it never reaches inert content.
            assert window.evaluate_js('LALPreview.current.dialog.contains(document.activeElement)||document.activeElement===document.body'), window.evaluate_js(
                "(()=>{const a=document.activeElement;return a?a.tagName+'#'+a.id+'.'+a.className+' '+(a.getAttribute('aria-label')||a.textContent.slice(0,40)):'none'})()")
        browser_input('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
        assert window.evaluate_js("getComputedStyle(LALPreview.current.viewport).transitionDuration==='0s'")
        browser_input('Emulation.setEmulatedMedia',{'features':[]})
        check('Fullscreen contains keyboard focus and the crossfade respects reduced motion')
        for action,value in [('view','front'),('projection','orthographic'),('edges',True),('background','dark'),('up','Z'),('navigation','free'),('fit',None),('reset',None)]:
            js(f"(async()=>{{await LALPreview.current.command({json.dumps(action)},{json.dumps(value)});return true;}})()")
            assert window.evaluate_js('LALPreview.current.ready && !LALPreview.current.retainedFault')
        capture('04-display-options.png')
        check('View, projection, edges, background, up-axis, navigation, fit and reset respond')
        window.resize(720,820)
        wait('innerWidth<740')
        wait('LALPreview.current.viewport.clientWidth>650')
        capture('05-narrow-fullscreen.png')
        assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+1')
        window.evaluate_js("LALPreview.current.dialog.dispatchEvent(new Event('cancel',{cancelable:true}))")
        wait('!LALPreview.current.fullscreen')
        assert window.evaluate_js('originalPreviewFrame===LALPreview.current.frame && LALPreview.current.ready')
        assert window.evaluate_js('document.activeElement===LALPreview.current.full')
        check('Escape leaves fullscreen and returns focus without reimporting')
        js("(async()=>{await LALPreview.current.acknowledge('focus');return true;})()")
        key('f','KeyF',70,2)
        wait("document.activeElement===$('query')")
        assert window.evaluate_js('originalPreviewFrame===LALPreview.current.frame && LALPreview.current.ready')
        check('Ctrl+F returns from the inline canvas to search without reloading the model')
        window.evaluate_js('LALPreview.pause()')
        wait('!document.querySelector(".model-viewport iframe")')
        assert not bridge._interactive_preview.tickets
        assert 'paused' in window.evaluate_js('LALPreview.current.status.textContent')
        check('Pausing (page change, hidden panel) releases the frame and file ticket and says so')
        # A different selected export must load that source, never silently reuse OBJ.
        select(record['asset_id'],'glb')
        wait('Boolean(LALPreview.current?.ready)',60)
        assert window.evaluate_js('LALPreview.current.manifest.format')=='glb'
        assert window.evaluate_js('LALPreview.current.fileReads')==1
        report['live_ms_glb']=window.evaluate_js('LALPreview.current.liveMs')
        capture('06-glb.png')
        check('GLB source selection loads offline with the bundled decoder and environment')
        select(record['asset_id'],'obj')
        wait('Boolean(LALPreview.current?.ready)',60)
        report['live_ms_obj']=window.evaluate_js('LALPreview.current.liveMs')
        bridge.unblock.clear(); bridge.delay=True
        select(record['asset_id'],'glb')
        wait('Boolean(LALPreview.current.loadingText)')
        js('(async()=>{await LALPreview.current.enterFullscreen();return true;})()')
        capture('07-fullscreen-loading.png')
        js(f"(async()=>{{await lal.selectAsset('library',{json.dumps(records[1]['asset_id'])});return true;}})()")
        bridge.delay=False; bridge.unblock.set()
        wait('LALPreview.current.item.assetId!=='+identifier)
        time.sleep(.3)
        assert not window.evaluate_js('Boolean(document.querySelector("dialog:modal"))')
        assert all(v['asset_id']!=record['asset_id'] for v in bridge._interactive_preview.tickets.values())
        check('Leaving during a delayed fullscreen load ignores obsolete results')
        select(records[2]['asset_id'])
        wait('Boolean(LALPreview.current.retainedFault)',45)
        assert window.evaluate_js("LALPreview.current.status.classList.contains('fault') && !LALPreview.current.status.hidden")
        report['fault_status']=window.evaluate_js('LALPreview.current.status.textContent')
        capture('08-retained-fault.png')
        faults_before=bridge._interactive_preview.fault_path.read_text()
        select(records[1]['asset_id'])
        select(records[2]['asset_id'])
        wait('Boolean(LALPreview.current.retainedFault)')
        assert not window.evaluate_js('Boolean(LALPreview.current.frame)')
        assert bridge._interactive_preview.fault_path.read_text()==faults_before
        check('A load fault shows its reason over the still and is recorded once, never retried')
        # A format the viewer cannot open shows renders and says so; the view buttons switch stills.
        before=stats()
        select(blend['asset_id'])
        time.sleep(.5)
        assert 'isn’t available for .blend' in window.evaluate_js('LALPreview.current.status.textContent')
        assert window.evaluate_js('LALPreview.current.viewButtons[3].disabled && LALPreview.current.more.disabled')
        assert stats()==before
        capture('09-blend-renders.png')
        window.evaluate_js("LALPreview.current.viewButtons[1].click()")
        wait("lal.state.library.detail.view==='front' && LALPreview.current?.item.view==='front'")
        assert window.evaluate_js("LALPreview.current.viewButtons[1].getAttribute('aria-pressed')")=='true'
        check('BLEND shows renders with a visible reason; view buttons switch the stills; no viewer is loaded')
        # Over the auto-load cap: nothing is read until the owner clicks.
        select(large['asset_id'])
        wait("LALPreview.current.status.textContent.includes('Large model')")
        assert not window.evaluate_js('Boolean(LALPreview.current.frame)') and window.evaluate_js('LALPreview.current.fileReads')==0
        assert all(v['asset_id']!=large['asset_id'] for v in bridge._interactive_preview.tickets.values())
        capture('10-large-model.png')
        window.evaluate_js("LALPreview.current.status.querySelector('button').click()")
        wait('Boolean(LALPreview.current?.ready)',90)
        report['live_ms_large_after_click']=window.evaluate_js('LALPreview.current.liveMs')
        report['large_bytes']=window.evaluate_js('LALPreview.current.manifest.total_bytes')
        check('A model over the 16 MiB cap shows "Large model · click to load" and loads on click')
        # Fast arrow-key browsing selects each card yet loads no viewer for the ones it passes.
        select(records[5]['asset_id'])
        wait(SETTLED,60)
        plan=window.evaluate_js("(()=>{const cards=[...document.querySelectorAll('.card')];const i=Math.min(cards.findIndex(c=>c.dataset.id===%s),cards.length-9);cards[i].focus();return {start:i,count:cards.length,target:cards[i+8].dataset.id};})()" % json.dumps(records[5]['asset_id']))
        plan['selected_before']=window.evaluate_js('lal.state.library.selected')
        plan['focused']=window.evaluate_js('document.activeElement?.dataset?.id||document.activeElement?.tagName')
        report['browse_plan']=plan
        before=stats()
        # A mutation observer, not a timer: timers are throttled while the verify window is in the background.
        js("(()=>{window.browseSeen=new Set();window.browseWatch=new MutationObserver(()=>{const c=document.querySelector('.card[aria-pressed=true]');if(c)browseSeen.add(c.dataset.id)});browseWatch.observe(document.body,{subtree:true,attributes:true,attributeFilter:['aria-pressed']});return true})()")
        started=time.monotonic()
        for _ in range(8):
            key('ArrowRight','ArrowRight',39)
        report['browse_seconds_for_8_keys']=round(time.monotonic()-started,3)
        wait('lal.state.library.selected===%s && LALPreview.current?.item.assetId===%s' % (json.dumps(plan['target']),json.dumps(plan['target'])))
        wait(SETTLED,60)
        report['browse_selected_distinct']=window.evaluate_js('(browseWatch.disconnect(),browseSeen.size)')
        after=stats()
        report['browse_viewers']={'prepared':after['prepared']-before['prepared'],'frames':after['frames']-before['frames']}
        report['live_ms_after_browse']=window.evaluate_js('LALPreview.current.liveMs')
        assert report['browse_selected_distinct']>=6, report['browse_selected_distinct']
        assert report['browse_viewers']['prepared']<=1 and report['browse_viewers']['frames']<=1, report['browse_viewers']
        capture('11-after-browse.png')
        check('Fast arrow presses select each card yet load at most one viewer, where browsing rests')
        report['status']='passed'
    except Exception as exc:
        report.update(status='faulty',reason=str(exc),traceback=traceback.format_exc())
        try: capture('failure.png')
        except Exception: pass
    finally:
        bridge.unblock.set()
        (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
        bridge._close()
        window.destroy()


def verify_real():
    try:
        ui.wait_ready(45)
        js("(async()=>{await lal.submitSearch();await until(()=>lal.state.library.items.length>0);return true})()")
        # One asset per viewer format in whatever library is configured, plus its biggest package.
        targets=[]
        for fmt in ('glb','gltf','fbx','obj','dae','stl'):
            item=next((r for r in records if r.get('availability')=='available'
                       and any(f['format']==fmt for f in r['files'])),None)
            if item: targets.append((item,fmt))
        def size(item,fmt):
            entry=next(f for f in item['files'] if f['format']==fmt)
            paths=[entry['path']]+[d['path'] for d in item.get('dependencies',[]) if d.get('path')]
            return sum(config.source_file(p).stat().st_size for p in paths if config.source_file(p).exists())
        candidates=[(r,f['format']) for r in records if r.get('availability')=='available'
                    for f in r['files'][:1] if f['format'] in ('glb','gltf','fbx','obj','dae','stl')]
        if candidates: targets.append(max(candidates,key=lambda pair:size(*pair)))
        protected={}
        for item,fmt in targets:
            for entry in item['files']+item.get('dependencies',[]):
                if entry.get('path') and entry.get('status',entry.get('availability'))=='available':
                    path=config.source_file(entry['path'])
                    protected[str(path)]=file_hash(path)
        report['assets']=[]
        for index,(item,fmt) in enumerate(targets):
            select(item['asset_id'],fmt)
            wait(SETTLED,60)
            result=window.evaluate_js("({ready:LALPreview.current.ready,fault:LALPreview.current.retainedFault,status:LALPreview.current.status.textContent,summary:LALPreview.current.summary,source:LALPreview.current.manifest?.source_name,files:LALPreview.current.fileReads,live_ms:LALPreview.current.liveMs})")
            result.update(asset_id=item['asset_id'],name=item['display_name'],pack=item['pack_id'],format=fmt)
            report['assets'].append(result)
            capture(f'real-{index+1:02}-{fmt}.png')
        changed=[path for path,before in protected.items() if file_hash(Path(path))!=before]
        assert not changed, changed
        report['unchanged_original_files']=len(protected)
        report['checks'].append('Representative GLB, OBJ, FBX, DAE and STL viewed without source processing or model inference')
        report['checks'].append('Selected original files and known dependencies remain hash-identical')
        report['status']='passed' if all(r['ready'] and not r['fault'] for r in report['assets']) else 'complete_with_asset_faults'
    except Exception as exc:
        report.update(status='faulty',reason=str(exc),traceback=traceback.format_exc())
    finally:
        # The run may retire the first-use hint; the owner's own preference is put back.
        from local_asset_library.settings import save_interface_settings
        save_interface_settings(config, preview_hint_seen=hint_before)
        (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify,daemon=True).start()
webview.start(gui='edgechromium',debug=False,private_mode=True,storage_path=str(profile))
record_profile_outcome(bridge,profile)
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['status']=='passed' else 1)
