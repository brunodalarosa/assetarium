"""Exercise 2D image browsing in real WebView2 with isolated synthetic images.

Covers type/transparency/size filters, pixel-art thumbnails, the zoomable image
viewer (fit, 1:1, zoom, backgrounds, hard pixel edges), SVG re-rendering, an
image fault and the per-source "Include 2D images" setting. No model, GPU or
real asset source is used. Evidence: data/gui/<run-name>/.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_images import art, ready_images
from local_asset_library import sources
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from gui_harness import Harness

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir(exist_ok=False)
config, backend, source, art_root = art.__wrapped__(fixture)
ready_images(config, backend, source)
sources.scan_source(config, source)
saved = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in art_root.rglob('*') if p.is_file() and 'metadata-lal' not in p.parts}
assert saved


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result

    def _start_source_operation(self, operation, key):
        if operation != 'scan':
            raise RuntimeError('Only synchronous synthetic scans are allowed here')
        sources.scan_source(self._config, sources.get_source(self._config, key))
        return {'status': 'complete', 'reason': 'Synthetic scan finished'}


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True, 'owner_usability_approval': 'pending'}


ui = Harness(window, OUT, report)


def wait(expression, timeout=30):
    try:
        ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)
    except RuntimeError as exc:
        raise RuntimeError('UI condition timed out: ' + expression + ' ' + str(ui.js(
            "({main:$('error')?.textContent,status:$('status')?.textContent,sources:$('sources-message')?.textContent})"))) from exc


js = ui.js
capture = ui.capture
ZOOM_IN = "$('detail').querySelector('[aria-label=\"Zoom in\"]').click()"


def open_card(name):
    js(f"[...$('grid').querySelectorAll('.card')].find(c=>c.querySelector('.card-name').textContent==={json.dumps(name)}).click()")
    wait(f"$('detail').querySelector('h2')?.textContent==={json.dumps(name)}&&!lal.state.library.detail.loading")


def browse(asset_type='', transparent='', size='', query=''):
    js(f"""(async()=>{{lal.setState({{filters:{{...lal.state.filters,asset_type:{json.dumps(asset_type)},transparent:{json.dumps(transparent)},
       size_class:{json.dumps(size)},mode:'keyword'}}}});lal.setQuery({json.dumps(query)});await lal.submitSearch();return true}})()""")


def scroll_cards():
    # Thumbnails load as cards become visible.
    for index in range(js("$('grid').querySelectorAll('.card').length")):
        js(f"$('grid').querySelectorAll('.card')[{index}].scrollIntoView({{block:'center'}})")
        time.sleep(.15)
    js("$('library-view').scrollTop=0")


def names():
    return sorted(js("[...$('grid').querySelectorAll('.card-name')].map(n=>n.textContent)"))


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===1')
        browse('image')
        wait("[...$('grid').querySelectorAll('.card')].length===11")
        assert names() == sorted(['arrow', 'arrow', 'bare', 'banner', 'blink', 'box', 'copy', 'damaged', 'glow', 'linked', 'potion']), names()
        assert js("[...$('grid').querySelectorAll('.badges .type')].length===11")
        scroll_cards()
        wait("[...$('grid').querySelectorAll('.thumb img')].length===8")
        assert js("[...$('grid').querySelectorAll('.card')].filter(c=>c.querySelector('.card-name').textContent==='potion')[0].querySelector('.thumb img').classList.contains('pixelated')")
        assert js("[...$('grid').querySelectorAll('.thumb.bg-checker')].length===8")
        assert js("[...$('grid').querySelectorAll('.card')].find(c=>c.querySelector('.card-name').textContent==='damaged').textContent.includes('Preview')")
        capture('01-image-cards.png')
        report['checks'].append('Asset type filter lists 11 images with type badges; 8 processed images show checkerboard thumbnails, pixel art with hard edges, faults keep cards')
        browse('image', 'true', 'tiny')
        wait("$('grid').querySelectorAll('.card').length===2")
        assert names() == ['copy', 'potion'], names()
        browse('', 'false')
        wait("$('grid').querySelectorAll('.card').length===1")
        assert names() == ['banner'], names()
        report['checks'].append('Transparency and size filters use measured facts and exclude unprocessed images and 3D models')
        browse('image', 'true', 'tiny')
        wait("$('grid').querySelectorAll('.card').length===2")
        open_card('potion')
        wait("$('detail').querySelector('.image-stage img')?.naturalWidth>0")
        detail = js("$('detail').textContent")
        assert '16 × 16 px' in detail and 'Cut-out' in detail and 'enlarged 16×' in detail and 'not a colour of this image' in detail, detail
        assert 'icon — Folder name' in detail and 'Byte-identical to 1 other image' in detail, detail
        wait("$('detail').querySelector('.image-note').textContent.startsWith('Original source pixels')")
        assert js("$('detail').querySelector('.image-pixelated [role=checkbox]').getAttribute('aria-checked')==='true'")
        js("[...$('detail').querySelectorAll('.image-toolbar button')].find(b=>b.textContent==='1:1').click()")
        wait("$('detail').querySelector('.image-stage img').getBoundingClientRect().width===16")
        for _ in range(4):
            js(ZOOM_IN)
        wait("$('detail').querySelector('.image-zoom').textContent==='600%'&&$('detail').querySelector('.image-stage img').getBoundingClientRect().width===96")
        js("pick('image-background','dark')")
        assert js("$('detail').querySelector('.image-stage').classList.contains('bg-dark')")
        capture('02-pixel-art-zoom-dark.png')
        js("$('detail').querySelector('.image-stage').focus();$('detail').querySelector('.image-stage').dispatchEvent(new KeyboardEvent('keydown',{key:'0',bubbles:true}))")
        wait("$('detail').querySelector('.image-zoom').textContent==='Fit'")
        report['checks'].append('Pixel-art detail shows measured facts, purpose suggestion, duplicate evidence and backdrop note; 1:1 is 16 px, zoom steps, dark background, keyboard fit')
        browse('image')
        wait("[...$('grid').querySelectorAll('.card')].length===11")
        open_card('box')
        wait("$('detail').querySelector('.image-note')?.textContent.includes('Rendered from the SVG source')")
        assert js("$('image-background').dataset.value==='dark'")  # Remembered for this session.
        for _ in range(4):
            js(ZOOM_IN)
        js("[...$('detail').querySelectorAll('.image-toolbar button')].find(b=>b.textContent==='1:1').click()")
        for _ in range(3):
            js(ZOOM_IN)
        wait("$('detail').querySelector('.image-zoom').textContent==='400%'")
        # Re-rendered for the zoom and the display's pixel ratio, not just stretched.
        wait("$('detail').querySelector('.image-note').textContent.includes(`showing ${Math.round(160*devicePixelRatio)} × ${Math.round(80*devicePixelRatio)} px`)", 20)
        assert '40 × 20 canvas units' in js("$('detail').textContent")
        capture('03-svg-zoom.png')
        report['checks'].append('SVG detail is rendered by the recorded renderer and re-rendered sharply at the zoom level; canvas units stated')
        open_card('damaged')
        detail = js("$('detail').textContent")
        assert 'could not be processed' in detail and 'damaged or truncated' in detail, detail
        assert 'no substitute' not in js("$('detail').querySelector('.fault-list').textContent+$('detail').querySelector('.detail-preview').textContent")
        assert 'searchable by name and by its pixels' not in detail and 'Measurement evidence' not in detail, detail
        open_card('blink')
        assert 'animation and multi-page images are deferred' in js("$('detail').textContent")
        assert 'recognized but not supported yet' in js("$('detail').textContent")
        capture('04-image-fault.png')
        report['checks'].append('Damaged and animated images keep their cards with recorded fault/unsupported reasons and no fake preview')
        browse(query='arrow')
        wait("$('grid').querySelectorAll('.card').length===2")
        report['checks'].append('Keyword search finds both arrow images by name')
        js("(async()=>{$('nav-settings').click();await until(()=>$('asset-sources-tab'));$('asset-sources-tab').click();return true})()")
        wait("$('settings-view')&&document.querySelector('.source-images [role=checkbox]')!==null")
        assert js("document.querySelector('.source-images [role=checkbox]').getAttribute('aria-checked')==='true'")
        assert 'Model textures, previews and sprite sheets are left out' in js("document.querySelector('.source-images').parentElement.textContent")
        capture('05-source-images-setting.png')
        for expected in (('model_3d',), ('model_3d', 'image')):
            js("document.querySelector('.source-images [role=checkbox]').click()")
            deadline = time.monotonic() + 30
            while sources.import_types(sources.bound(config, source)) != expected:
                assert time.monotonic() < deadline, 'Image import setting was not saved'
                time.sleep(.1)
            wait(f"document.querySelector('.source-images [role=checkbox]')?.getAttribute('aria-checked')==={json.dumps(str(len(expected) == 2).lower())}")
        wait("[...document.querySelectorAll('.source-format-counts')].some(p=>p.textContent.includes('PNG'))")
        report['checks'].append('Include 2D images is a per-source checkbox; changing it saves the choice and rescans without deleting results')
        js("$('nav-home').click()")
        wait("$('library-view')")
        browse('image')
        wait("[...$('grid').querySelectorAll('.card')].length===11")
        open_card('banner')
        window.resize(680, 900)
        wait('innerWidth<761')
        wait("$('detail').querySelector('.image-stage img')?.naturalWidth>0")
        assert js("$('library-view').scrollWidth<=$('library-view').clientWidth+1&&$('detail').scrollWidth<=$('detail').clientWidth+1")
        capture('06-narrow-detail.png')
        report['checks'].append('Narrow layout keeps the image viewer and toolbar in view without horizontal overflow')
        assert not bridge._gateway.model_requested
        changed = [p for p, digest in saved.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
        assert not changed, changed
        report['checks'].append('Original fixture files unchanged; no model worker loaded')
        report.update(status='passed', protected_files=len(saved))
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
        except Exception:
            pass
    finally:
        (OUT / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        bridge._close()
        window.destroy()

window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2, ensure_ascii=False))
raise SystemExit(0 if report['status'] == 'passed' else 1)
