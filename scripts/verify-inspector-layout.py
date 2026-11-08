"""Real WebView2 check of the asset inspection panel: one scroll, fact chips and remembered sections.

Synthetic assets only (the 2D art fixture plus inspected 3D models with a rig, clips and a license file; one is
measured in another format than the one selected).
Covers: no tabs; the top-to-bottom order; a fault line only on a faulty asset; chips that open and scroll to
their section; a format-mismatch caveat beside the chips while Geometry is closed; section state that survives another selection and a restart (a reload from the saved boot
payload); the Image section for images; and the fields the redesign dropped. No model, GPU or real asset source
is used. Evidence: data/gui/<run-name>/.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from PIL import Image
from test_images import art, ready_images
from local_asset_library import sources
from local_asset_library.captions import file_hash
from local_asset_library.desktop import DesktopBridge, create_window, page_html, profile_path, record_profile_outcome
from local_asset_library.incremental import update_record
from local_asset_library.library_index import index_library
from local_asset_library.membership import records
from local_asset_library.source_operations import publish_source
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
config, backend, source, art_root = art.__wrapped__(fixture)
# License files: CC0 for the pixel icons and the model, an unrecognized one for the wide images, none for vectors.
(art_root / 'Pixel/License.txt').write_text('Pixel icons. License: Creative Commons Zero (CC0).\n', encoding='utf-8')
(art_root / 'Models/License.txt').write_text('Crate model. License: CC0 1.0 Universal.\n', encoding='utf-8')
(art_root / 'Wide/LICENSE.txt').write_text('Wide images. All rights reserved; ask before use.\n', encoding='utf-8')
(art_root / 'Models/barrel.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n', encoding='utf-8')
work, _ = ready_images(config, backend, source)
# The art fixture has no Blender; give its crate model the record a successful inspection would leave.
# The barrel's measurements claim FBX while only its OBJ exists: the selected format is not the inspected one.
for name, inspected in (('crate', 'obj'), ('barrel', 'fbx')):
    model = next(r for r in records(work) if r['display_name'] == name)
    model['processing'].update(inspection='complete', previews='complete')
    model['stage_faults'] = {}
    model['technical'] = {'inspected_path': model['files'][0]['path'], 'inspected_sha256': model['files'][0]['sha256'], 'inspected_format': inspected,
                          'evaluated_instance_totals': {'triangles': 1248, 'vertices': 702}, 'armatures': [{'object': 'Rig', 'bones': 12}],
                          'animation_clips': [{'name': 'Idle', 'frame_range': [1, 40]}, {'name': 'Walk', 'frame_range': [1, 24]}]}
    model['previews'] = []
    for view in ('three_quarter', 'front', 'side'):
        path = work.output_path('data', f'results/synthetic/{name}-{view}.png')
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (96, 96), '#8a6a4b').save(path)
        model['previews'].append({'path': path.relative_to(work.project_root).as_posix(), 'sha256': file_hash(path), 'view_label': view, 'origin': 'rendered'})
    update_record(work, model)
index_library(work, backend)
publish_source(sources.bound(config, source))
sources.aggregate(config)
sources.scan_source(config, source)
IDS = {r['display_name']: r['asset_id'] for r in records(work) if r['display_name'] in ('crate', 'barrel', 'potion', 'banner', 'box', 'damaged')}
saved = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in art_root.rglob('*') if p.is_file()}


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
report = {'status': 'running', 'checks': {}, 'synthetic_only': True, 'owner_visual_review': 'pending', 'real_model_load': False}
ui = Harness(window, OUT, report)
js, check, capture = ui.js, ui.check, ui.capture

DROPPED = ['Physical scale', 'Owner review', 'Artistic suitability', 'Caption review:', 'Unknowns remain unknown',
           'Original files stay in their source folder', 'Interpretations, separate from measured facts',
           'No suggestions recorded', 'No caption review notes', 'No faults recorded', 'verified hash', 'Actions']


def select(name):
    js(f"""(async()=>{{await lal.selectAsset('library',{json.dumps(IDS[name])});
      await until(()=>lal.state.library.detail&&!lal.state.library.detail.loading&&$('detail').querySelector('.detail-header h2')?.textContent==={json.dumps(name)});
      await frame();return true}})()""")


CHIPS = "[...$('detail').querySelectorAll('.fact-chip')].map(c=>c.textContent)"
EXPANDED = "Object.fromEntries([...$('detail').querySelectorAll('.inspector-section')].map(s=>[s.dataset.section,s.querySelector('h3 button').getAttribute('aria-expanded')==='true']))"
SAVED = "(async()=>{const r=await lal.state.api.interface_settings();return r.inspector_sections})()"


def chip(label):
    return f"[...$('detail').querySelectorAll('.fact-chip')].find(c=>c.textContent==={json.dumps(label)})"


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===1')
        js("lal.setAppearance('light')")
        js("lal.setInspectorOpen(true)")
        select('crate')
        check('model_one_scroll', f"""(()=>{{const d=$('detail'),at=sel=>d.querySelector(sel);
          const order=['.detail-header','.detail-preview','.fact-chips','.inspector-description','.asset-tags','.inspector-sections'].map(at);
          const text=d.textContent;
          return {{noTabs:!document.querySelector('#inspector [role=tab],#inspector [role=tabpanel]'),noFaultLine:!at('.fault-line'),
            ordered:order.every(Boolean)&&order.every((el,i)=>!i||order[i-1].compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING),
            chips:JSON.stringify({CHIPS})===JSON.stringify(['1,248 tris','OBJ','2 dependency files','Rigged','Animated · 2 clips','CC0']),
            sections:JSON.stringify({EXPANDED})==='{{"file":false,"geometry":false,"record":false}}',
            oneFormatNoSelect:!$('detail-format')&&!!$('detail-view'),
            noCaveat:!at('.format-caveat'),dropped:{json.dumps(DROPPED)}.every(t=>!text.includes(t))}}}})()""")
        capture('01-model-collapsed.png')

        select('barrel')
        check('format_caveat_beside_chips', f"""(()=>{{const d=$('detail'),caveat=d.querySelector('.format-caveat'),chips={CHIPS};
          const box=caveat?.getBoundingClientRect(),list=d.querySelector('.fact-chips').getBoundingClientRect();
          return {{geometryClosed:!{EXPANDED}.geometry,visible:!!box&&box.height>0&&box.top>=list.bottom-1&&box.top-list.bottom<24,
            text:caveat?.textContent==='OBJ is uninspected; the measurements describe FBX.',
            chips:JSON.stringify(chips)===JSON.stringify(['1,248 tris · FBX','OBJ','Rigged · FBX','Animated · 2 clips · FBX','CC0'])}}}})()""")
        capture('01b-model-format-caveat.png')
        select('crate')

        check('chip_opens_geometry', f"""(async()=>{{{chip('Rigged')}.click();await until(()=>$('inspector-section-geometry-content'));
          await new Promise(r=>setTimeout(r,700));const box=$('inspector-section-geometry').getBoundingClientRect(),view=$('detail').getBoundingClientRect();
          const text=$('inspector-section-geometry-content').textContent;
          return {{open:{EXPANDED}.geometry,scrolled:box.top>=view.top-2&&box.top<view.bottom-40,rig:text.includes('Rig · 12 bones'),
            clips:text.includes('Idle, Walk'),sameFormatHidden:!text.includes('Inspected format'),noScale:!text.includes('scale')}}}})()""")
        capture('02-model-geometry-from-chip.png')
        check('license_chip_opens_file', f"""(async()=>{{{chip('CC0')}.click();await until(()=>$('inspector-section-file-content'));await frame();
          const c=$('inspector-section-file-content');return {{open:{EXPANDED}.file,license:c.textContent.includes('CC0 1.0 (Creative Commons Zero)'),
            excerpt:c.querySelector('.license-excerpt')?.textContent.includes('CC0 1.0 Universal'),deps:c.querySelectorAll('.dependency-list li').length===2,
            depsTitle:c.textContent.includes('Dependencies · 2 files'),copy:[...c.querySelectorAll('button')].some(b=>b.textContent==='Copy source path')}}}})()""")
        check('sections_saved', f"""(async()=>{{const end=Date.now()+5000;let s;
          while(Date.now()<end){{s=await lal.state.api.interface_settings();if(s.inspector_sections.file&&s.inspector_sections.geometry)break;await new Promise(r=>setTimeout(r,100))}}
          return {{file:s.inspector_sections.file,geometry:s.inspector_sections.geometry,recordClosed:!s.inspector_sections.record}}}})()""")
        capture('03-model-file-and-license.png')

        select('potion')
        check('image_keeps_sections', f"""(()=>{{const e={EXPANDED},chips={CHIPS},text=$('detail').textContent;
          return {{sections:JSON.stringify(Object.keys(e))==='["file","image","record"]',fileRemembered:e.file,imageClosed:!e.image,
            chips:chips[0]==='16 × 16 px'&&chips.includes('Cut-out')&&chips.includes('PNG')&&chips.at(-1)==='CC0',
            noFaultLine:!$('detail').querySelector('.fault-line'),dropped:{json.dumps(DROPPED)}.every(t=>!text.includes(t))}}}})()""")
        check('image_chip_opens_image', f"""(async()=>{{{chip('16 × 16 px')}.click();await until(()=>$('inspector-section-image-content'));await frame();
          const t=$('inspector-section-image-content').textContent;return {{open:{EXPANDED}.image,size:t.includes('16 × 16 px'),transparency:t.includes('Cut-out (fully transparent'),
            derivation:t.includes('enlarged 16×')}}}})()""")
        capture('04-image-sections.png')
        select('banner')
        check('unrecognized_license', f"""(()=>({{chip:{CHIPS}.at(-1)==='License file',text:$('inspector-section-file-content').textContent.includes('Not recognized automatically')}}))()""")
        select('box')
        check('no_license_file', f"""(()=>({{chip:{CHIPS}.at(-1)==='No license file',text:$('inspector-section-file-content').textContent.includes('No license file was found')}}))()""")

        select('damaged')
        check('fault_line_on_faulty_asset', """(async()=>{const line=$('detail').querySelector('.fault-line');const header=$('detail').querySelector('.detail-header');
          const first=!!line&&header.nextElementSibling===line;const reason=line?.textContent.includes('damaged or truncated');
          [...line.querySelectorAll('button')].find(b=>b.textContent==='Details').click();await until(()=>$('inspector-section-record-content'));
          await new Promise(r=>setTimeout(r,1200));const record=$('inspector-section-record-content');
          const top=$('inspector-section-record').getBoundingClientRect().top-$('detail').getBoundingClientRect().top;
          return {first,reason,recordOpen:lal.state.inspector.sections.record,scrolledToTop:top>=-2&&(top<40||$('detail').scrollTop+$('detail').clientHeight>=$('detail').scrollHeight-2),
            list:[...record.querySelectorAll('.fault-list li')].some(li=>li.textContent.includes('damaged or truncated'))}})()""")
        capture('05-faulty-image-record.png')
        # Closing a section is remembered too.
        js("$('inspector-section-file-toggle').click()")
        check('closing_saved', """(async()=>{const end=Date.now()+5000;let s;
          while(Date.now()<end){s=(await lal.state.api.interface_settings()).inspector_sections;if(!s.file&&s.record)break;await new Promise(r=>setTimeout(r,100))}
          return {fileClosed:!s.file,geometry:s.geometry,image:s.image,record:s.record}})()""")

        # Restart: a fresh page from the saved boot payload, the same path the app's start takes.
        js("window.__beforeRestart=true")
        window.load_html(page_html(config)[0])
        ui.wait_ready(extra='!window.__beforeRestart&&lal.state.sources.length===1')
        js("lal.setInspectorOpen(true)")
        check('restart_restores_sections', """(()=>JSON.stringify(lal.state.inspector.sections)==='{"file":false,"geometry":true,"image":true,"record":true}')()""")
        select('crate')
        check('restart_model_sections', f"""(()=>({{sections:JSON.stringify({EXPANDED})==='{{"file":false,"geometry":true,"record":true}}',
          chips:{CHIPS}.length===6,noFaultLine:!$('detail').querySelector('.fault-line')}}))()""")
        capture('06-after-restart.png')
        js("lal.setAppearance('dark')")
        capture('d06-after-restart-dark.png')
        js("lal.setAppearance('system')")
        changed = [p for p, digest in saved.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
        assert not changed, changed
        report['checks']['originals_unchanged'] = True
        assert not bridge._gateway.model_requested
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
        except Exception:
            pass
    finally:
        (OUT / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        window.destroy()


try:
    webview.start(verify, gui='edgechromium', private_mode=True, storage_path=str(profile))
finally:
    bridge._close()
    record_profile_outcome(bridge, profile)
print(json.dumps({k: report[k] for k in ('status', 'reason') if k in report}, indent=2))
sys.exit(0 if report['status'] == 'passed' else 1)
