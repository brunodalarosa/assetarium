"""Actual WebView2 preview/navigation checks with tiny synthetic model sources."""
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
    record['display_name'] = 'Caf\u00e9 \u2014 carr\u00e9 \u25c7 \u5de5\u5177'
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
else:
    from local_asset_library.config import load_project_config
    from local_asset_library.membership import records as library_records
    config = load_project_config(ROOT)
    records = library_records(config)
    image = None



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
        detail = window.evaluate_js("({error:lal.state.search.error,warning:LALPreview.current?.warning.textContent,loading:LALPreview.current?.loadingText})")
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


def changed_pixels(before,after):
    rect=window.evaluate_js('(()=>{const r=LALPreview.current.viewport.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,dpr:devicePixelRatio};})()')
    # Native captures use device pixels; WebView2 input coordinates use CSS pixels.
    box=tuple(round(value*rect['dpr']) for value in (rect['x']+5,rect['y']+5,rect['x']+rect['w']-5,rect['y']+rect['h']-5))
    diff=ImageChops.difference(Image.open(before).convert('RGB').crop(box),Image.open(after).convert('RGB').crop(box))
    return sum(1 for r,g,b in diff.get_flattened_data() if max(r,g,b)>25)


def verify():
    if args.real_assets:
        return verify_real()
    try:
        ui.wait_ready()
        js("(async()=>{await lal.submitSearch();await until(()=>lal.state.library.items.length===40);lal.closeDetail('library');lal.setInspectorOpen(true);await until(()=>$('detail'));return true})()")
        assert js("$('page-info').textContent") == '1\u201340 of 40'
        assert js("$('detail').querySelector('.detail-empty h2').textContent") == 'No asset selected'
        assert ' \u00b7 ' in js('lal.state.coverage')
        capture('00-library-text.png')
        identifier=json.dumps(record['asset_id'])
        select(record['asset_id'])
        assert js("$('detail').querySelector('.detail-header h2').textContent") == record['display_name']
        assert js("document.querySelector('#inspector .close-detail').getAttribute('aria-label')") == 'Hide asset inspection'
        assert js("$('detail').querySelector('.pack').textContent") == 'Kenney \u00b7 even'
        window.evaluate_js("LALPreview.current.launch.click()")
        wait("Boolean(LALPreview.current.loadingText)")
        capture('01-loading.png')
        wait('Boolean(LALPreview.current?.ready)',60)
        assert '4 triangles' in window.evaluate_js('LALPreview.current.summary.textContent')
        assert window.evaluate_js('LALPreview.current.fileReads')==3
        assert not window.evaluate_js('LALPreview.current.warning.hidden===false')
        report['inline_frame']=window.evaluate_js("({sandbox:LALPreview.current.frame.getAttribute('sandbox'),source:LALPreview.current.manifest.source_name,summary:LALPreview.current.summary.textContent})")
        assert report['inline_frame']['sandbox']=='allow-scripts'
        capture('02-inline.png')
        check('Inline textured OBJ loads with MTL and texture dependencies')
        window.evaluate_js('window.originalPreviewFrame=LALPreview.current.frame;window.originalSession=LALPreview.current.session')
        js('(async()=>{await LALPreview.current.enterFullscreen();return true;})()')
        wait('LALPreview.current.fullscreen && !LALPreview.current.loadingText')
        assert window.evaluate_js('originalPreviewFrame===LALPreview.current.frame && originalSession===LALPreview.current.session')
        assert window.evaluate_js('LALPreview.current.fileReads')==3
        assert window.evaluate_js('LALPreview.current.dialog.getBoundingClientRect().width>=innerWidth-2')
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
        browser_input('Input.dispatchMouseEvent',dict(type='mouseWheel',**rect,deltaY=-180,deltaX=0))
        zoomed=capture('03b-zoomed.png')
        report['zoom_changed_pixels']=changed_pixels(rotated,zoomed)
        assert report['zoom_changed_pixels']>1000
        browser_input('Input.dispatchKeyEvent',dict(type='keyDown',key='ArrowLeft',code='ArrowLeft',windowsVirtualKeyCode=37))
        browser_input('Input.dispatchKeyEvent',dict(type='keyUp',key='ArrowLeft',code='ArrowLeft',windowsVirtualKeyCode=37))
        keyboard=capture('03c-keyboard-orbit.png')
        report['keyboard_changed_pixels']=changed_pixels(zoomed,keyboard)
        assert report['keyboard_changed_pixels']>500
        check('Native mouse drag, wheel zoom and keyboard orbit change the rendered model')
        window.evaluate_js('LALPreview.current.full.focus()')
        for _ in range(12):
            browser_input('Input.dispatchKeyEvent',dict(type='keyDown',key='Tab',code='Tab',windowsVirtualKeyCode=9))
            browser_input('Input.dispatchKeyEvent',dict(type='keyUp',key='Tab',code='Tab',windowsVirtualKeyCode=9))
            assert window.evaluate_js('LALPreview.current.dialog.contains(document.activeElement)'), window.evaluate_js(
                "(()=>{const a=document.activeElement;return a?a.tagName+'#'+a.id+'.'+a.className+' '+(a.getAttribute('aria-label')||a.textContent.slice(0,40)):'none'})()")
        browser_input('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
        assert window.evaluate_js("getComputedStyle(LALPreview.current.spinner).animationName==='none'")
        browser_input('Emulation.setEmulatedMedia',{'features':[]})
        check('Fullscreen contains keyboard focus and the loading indicator respects reduced motion')
        for action,value in [('view','front'),('projection','orthographic'),('edges',True),('background','dark'),('up','Z'),('navigation','free')]:
            js(f"(async()=>{{await LALPreview.current.command({json.dumps(action)},{json.dumps(value)});return true;}})()")
            assert window.evaluate_js('LALPreview.current.ready && !LALPreview.current.loadingText')
        capture('04-display-options.png')
        check('Upstream view, projection, edges, background, up-axis and navigation controls respond')
        window.resize(720,820)
        wait('innerWidth<740')
        wait('LALPreview.current.viewport.clientWidth>650')
        capture('05-narrow-fullscreen.png')
        assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+1')
        js('(async()=>{await LALPreview.current.exitFullscreen();return true;})()')
        assert window.evaluate_js('originalPreviewFrame===LALPreview.current.frame && LALPreview.current.ready')
        assert window.evaluate_js('document.activeElement===LALPreview.current.full')
        check('Narrow fullscreen layout and return focus work without reimporting')
        js("(async()=>{await LALPreview.current.acknowledge('focus');return true;})()")
        browser_input('Input.dispatchKeyEvent',dict(type='keyDown',key='f',code='KeyF',windowsVirtualKeyCode=70,modifiers=2))
        browser_input('Input.dispatchKeyEvent',dict(type='keyUp',key='f',code='KeyF',windowsVirtualKeyCode=70))
        wait("document.activeElement===$('query')")
        assert window.evaluate_js('originalPreviewFrame===LALPreview.current.frame && LALPreview.current.ready')
        check('Ctrl+F returns from the inline canvas to search without reloading the model')
        js('(async()=>{await LALPreview.current.enterFullscreen();return true;})()')
        window.evaluate_js("LALPreview.current.dialog.dispatchEvent(new Event('cancel',{cancelable:true}))")
        wait('!LALPreview.current.fullscreen && !LALPreview.current.loadingText')
        window.evaluate_js('LALPreview.current.back.click()')
        wait('!document.querySelector(".model-viewport iframe")')
        assert not bridge._interactive_preview.tickets
        check('Escape exits fullscreen; Back to image releases the frame and file ticket')
        # A different selected export must load that source, never silently reuse OBJ.
        select(record['asset_id'],'glb')
        window.evaluate_js('LALPreview.current.launchFull.click()')
        wait('Boolean(LALPreview.current?.ready)',60)
        assert window.evaluate_js('LALPreview.current.manifest.format')=='glb'
        assert window.evaluate_js('LALPreview.current.fileReads')==1
        capture('06-glb.png')
        check('GLB source selection loads offline with the bundled decoder and environment')
        window.evaluate_js('LALPreview.current.back.click()')
        bridge.delay=True
        window.evaluate_js('LALPreview.current.launchFull.click()')
        wait('LALPreview.current.fullscreen && Boolean(LALPreview.current.loadingText)')
        capture('07-fullscreen-loading.png')
        js(f"(async()=>{{await lal.selectAsset('library',{json.dumps(records[1]['asset_id'])});return true;}})()")
        bridge.unblock.set()
        wait('LALPreview.current.item.assetId!=='+identifier)
        time.sleep(.3)
        assert not window.evaluate_js('Boolean(document.querySelector(".model-viewport iframe"))')
        assert not window.evaluate_js('Boolean(document.querySelector("dialog:modal"))')
        check('Leaving during a delayed fullscreen load ignores obsolete results')
        bridge.delay=False
        select(records[2]['asset_id'])
        window.evaluate_js('LALPreview.current.launch.click()')
        wait('Boolean(LALPreview.current.retainedFault)',45)
        assert 'meshes' in window.evaluate_js('LALPreview.current.warning.textContent').lower()
        assert window.evaluate_js('LALPreview.current.full.disabled && !LALPreview.current.overlay.hidden')
        capture('08-retained-fault.png')
        faults_before=bridge._interactive_preview.fault_path.read_text()
        bad_id=json.dumps(records[2]['asset_id'])
        select(records[2]['asset_id'])
        window.evaluate_js('LALPreview.current.launch.click()')
        wait('Boolean(LALPreview.current.retainedFault)')
        assert not window.evaluate_js('Boolean(LALPreview.current.frame)')
        assert bridge._interactive_preview.fault_path.read_text()==faults_before
        check('Unusable geometry records a separate fault while keeping asset detail available')
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
        targets=[]
        def choose(pack=None,name=None,fmt='glb',repair=False):
            item=next(r for r in records if (not pack or r['pack_id']==pack)
                and (not name or r['display_name']==name)
                and (not repair or r.get('texture_repair'))
                and any(f['format']==fmt for f in r['files']))
            targets.append((item,fmt))
        choose('City_Kit_Commercial','building-d','glb')
        choose('kenney_food-kit','apple','obj')
        choose('craftpix-free-packs',fmt='fbx',repair=True)
        choose('synty-part1',fmt='fbx',repair=True)
        choose(fmt='dae')
        choose(fmt='stl')
        protected={}
        for item,fmt in targets:
            for entry in item['files']+item.get('dependencies',[]):
                if entry.get('path') and entry.get('status',entry.get('availability'))=='available':
                    path=config.source_file(entry['path'])
                    protected[str(path)]=file_hash(path)
        report['assets']=[]
        for index,(item,fmt) in enumerate(targets):
            select(item['asset_id'],fmt)
            window.evaluate_js('LALPreview.current.launchFull.click()')
            wait('Boolean(LALPreview.current?.ready || LALPreview.current?.retainedFault)',60)
            result=window.evaluate_js("({ready:LALPreview.current.ready,fault:LALPreview.current.retainedFault,summary:LALPreview.current.summary.textContent,source:LALPreview.current.manifest?.source_name,files:LALPreview.current.fileReads})")
            result.update(asset_id=item['asset_id'],name=item['display_name'],pack=item['pack_id'],format=fmt)
            report['assets'].append(result)
            capture(f'real-{index+1:02}-{fmt}.png')
            window.evaluate_js('LALPreview.current.back.click()')
        changed=[path for path,before in protected.items() if file_hash(Path(path))!=before]
        assert not changed, changed
        report['unchanged_original_files']=len(protected)
        report['checks'].append('Representative GLB, OBJ, FBX, DAE and STL viewed without source processing or model inference')
        report['checks'].append('Selected original files and known dependencies remain hash-identical')
        report['status']='passed' if all(r['ready'] and not r['fault'] for r in report['assets']) else 'complete_with_asset_faults'
    except Exception as exc:
        report.update(status='faulty',reason=str(exc),traceback=traceback.format_exc())
    finally:
        (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify,daemon=True).start()
webview.start(gui='edgechromium',debug=False,private_mode=True,storage_path=str(profile))
record_profile_outcome(bridge,profile)
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['status']=='passed' else 1)
