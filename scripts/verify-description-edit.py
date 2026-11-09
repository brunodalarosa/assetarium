"""Real WebView2 check of the inspector's description states: one line and the one action that resolves each.

Synthetic models only, no model or GPU: queued work is recorded instead of spawned (operation state written by the
script), and "descriptions set up" is switched by the script. Covers generated (Edit, the Generated tooltip naming
the model), the edit form (prose first, More details folded, a rule the edit breaks shown inline), edited (label,
Show original, the search update waiting, running, failed with Update search, then done), none (Generate
description → queued in line → running), failed (reason, Try again), not set up (Set up descriptions opens the
setup wizard's descriptions step), no owner-review or approval wording, and no card "Review" chip.
Evidence: data/gui/<run-name>/.
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
from test_sources import failed_caption, managed, ready_source
from local_asset_library import desktop_service, library_view, processing_queue, source_operations, sources
from local_asset_library.catalog import detail
from local_asset_library.desktop import DesktopBridge, create_window, page_html, profile_path, record_profile_outcome
from local_asset_library.incremental import update_record
from local_asset_library.membership import records
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
config, backend, one, _ = managed.__wrapped__(fixture)
work = ready_source(config, backend, one)
assets = sorted(records(work), key=lambda r: r['display_name'])
GENERATED, NONE, FAILED = (r['asset_id'] for r in assets[:3])
MODEL = 'Qwen/Qwen3-VL-2B-Instruct'
for record in assets:
    record['caption_provenance']['model'] = {'model_id': MODEL}
    if record['asset_id'] == NONE:
        record.update(description=None, caption_provenance=None)
        record['processing']['caption'] = 'pending'
    update_record(work, record)
failed_caption(work, detail(work, FAILED))
source_operations.publish_source(sources.bound(config, one))
sources.aggregate(config)
sources.scan_source(config, one)
saved = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(one['path']).rglob('*') if p.is_file()}

# Queued work is recorded, never spawned: the script moves each operation through its states.
started, setup = [], {'ready': True}


def start(config, operation, key=None, asset_ids=None, queue_item=None, owner=None, quiet=False, mode=None):
    token = 'synthetic-%d' % len(started)
    started.append({'operation': operation, 'asset_ids': asset_ids, 'mode': mode, 'token': token})
    source_operations.state(sources.bound(config, sources.get_source(config, key)), token=token, status='processing',
                            phase='Synthetic', operation=operation, key=key, asset_ids=asset_ids, mode=mode, queue_item=queue_item)
    return {'status': 'started', 'token': token}


def finish(status='complete', reason=None):
    source_operations.state(sources.bound(config, one), status=status, reason=reason, phase='Synthetic end')
    processing_queue.advance(config)


source_operations.start = start
library_view.blockers = lambda config: {}
desktop_service.DesktopService.description_setup = lambda self: (
    {'ready': True, 'reason': None} if setup['ready'] else {'ready': False, 'reason': 'The description model is not installed'})


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
js, check = ui.js, ui.check


def capture(name):
    """The description section in view (it sits below the preview), then the screenshot."""
    js("(async()=>{(document.querySelector('#detail .inspector-description')||document.body).scrollIntoView({block:'start'});await frame();return true})()")
    ui.capture(name)

NEW = 'A blue wooden barrel with dark iron hoops, a round lid and a short spout near the bottom edge.'
DROPPED = ['Owner review', 'Review pending', 'Artistic suitability', 'Approve', 'Approved', ' AI ']
SECTION = "$('detail').querySelector('.inspector-description')"
STATE = f"{SECTION}?.dataset.state"
BUTTON = "(label=>[...$('detail').querySelectorAll('.inspector-description button')].find(b=>b.textContent===label))"
AREA = ("window.typeArea=(target,value)=>{Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(target,value);"
        "target.dispatchEvent(new Event('input',{bubbles:true}));return true};true")


def select(asset):
    js(f"""(async()=>{{await lal.selectAsset('library',{json.dumps(asset)},null,'three_quarter',true,true);
      await until(()=>lal.state.library.detail&&!lal.state.library.detail.loading&&{STATE});await frame();return true}})()""")


def described(state):
    """Wait until the shown description reaches ``state`` (the app's own poll or an action refreshes it)."""
    js(f"(async()=>{{await lal.refreshDescription('library');await until(()=>{STATE}==={json.dumps(state)});await frame();return true}})()")


def no_dropped():
    return f"{json.dumps(DROPPED)}.every(t=>!{SECTION}.textContent.includes(t))"


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===2')
        js(AREA)
        js("lal.setAppearance('light')")
        js("lal.setInspectorOpen(true)")

        select(GENERATED)
        check('generated_shows_text_and_edit', f"""(async()=>{{const s={SECTION},label=s.querySelector('.generated-label');
          window.dispatchEvent(new KeyboardEvent('keydown',{{key:'Tab'}}));label.focus();await new Promise(r=>setTimeout(r,500));const tip=document.querySelector('[role=tooltip]')?.textContent||'';label.blur();
          return {{state:{STATE}==='generated',label:label.textContent==='Generated',model:tip.includes({json.dumps(MODEL)})&&tip.includes('local model'),
            edit:!!{BUTTON}('Edit'),noOriginal:!{BUTTON}('Show original'),dropped:{no_dropped()}}}}})()""")
        capture('01-generated.png')

        check('edit_form_prose_first', f"""(async()=>{{{BUTTON}('Edit').click();await until(()=>$('description-edit'));await frame();
          const form={SECTION}.querySelector('.description-form');
          return {{focused:document.activeElement===$('description-edit'),folded:!$('description-colors'),
            more:[...form.querySelectorAll('button')].some(b=>b.textContent.includes('More details')),noVariantNotice:!form.textContent.includes('variants')}}}})()""")
        check('broken_rule_is_shown_and_nothing_saved', f"""(async()=>{{typeArea($('description-edit'),'Too short.');await frame();
          [...{SECTION}.querySelectorAll('button')].find(b=>b.textContent==='Save').click();
          await until(()=>{SECTION}.querySelector('.description-error'));
          return {{reason:{SECTION}.querySelector('.description-error').textContent.includes('10-170 words'),stillEditing:!!$('description-edit')}}}})()""")
        capture('02-edit-form-rule.png')
        check('save_edit_with_more_details', f"""(async()=>{{typeArea($('description-edit'),{json.dumps(NEW)});
          [...{SECTION}.querySelectorAll('button')].find(b=>b.textContent.includes('More details')).click();await until(()=>$('description-colors'));await frame();
          const lines=$('description-colors').value.split('\\n');typeArea($('description-colors'),'blue\\nbrown');await frame();
          [...{SECTION}.querySelectorAll('button')].find(b=>b.textContent==='Save').click();
          await until(()=>{STATE}==='edited'&&!$('description-edit'));await frame();
          return {{listOnePerLine:lines.length===1&&lines[0]==='red',text:{SECTION}.querySelector('.description-text').textContent==={json.dumps(NEW)}}}}})()""")
        assert started and started[-1]['mode'] == 'edited' and started[-1]['asset_ids'] == [GENERATED], started
        report['checks']['edit_queued_search_update'] = True
        check('edited_label_original_and_search_running', f"""(async()=>{{const s={SECTION};{BUTTON}('Show original').click();
          await until(()=>s.querySelector('.description-original'));await frame();const original=s.querySelector('.description-original').textContent;
          return {{label:s.querySelector('.generated-label').textContent==='Edited',original:original.includes('A red synthetic')&&original.includes({json.dumps(MODEL)}),
            also:original.includes('You also corrected: colors'),hide:!!{BUTTON}('Hide original'),
            running:s.querySelector('.search-update')?.dataset.status==='running'&&s.textContent.includes('Updating search for this edit'),dropped:{no_dropped()}}}}})()""")
        capture('03-edited-original-search-running.png')
        finish('faulty', 'Synthetic search fault')
        check('failed_search_update_offers_update_search', f"""(async()=>{{await lal.refreshDescription('library');
          await until(()=>{SECTION}.querySelector('.search-update')?.dataset.status==='faulty');await frame();const s={SECTION};
          await new Promise(r=>setTimeout(r,2500));  // The app's change poll would raise a report notice by now.
          const told=[...lal.state.toasts,...lal.state.notifications].map(t=>t.title||t.kind||'');
          return {{reason:s.textContent.includes('Search still uses the earlier text: Synthetic search fault'),action:!!{BUTTON}('Update search'),
            noRunReport:!told.some(t=>/Description run|descriptions_report/.test(t))}}}})()""")
        capture('04-search-update-failed.png')
        js(f"(async()=>{{{BUTTON}('Update search').click();await until(()=>{SECTION}.querySelector('.search-update')?.dataset.status==='running');return true}})()")
        assert len(started) == 2 and started[-1]['mode'] == 'edited', started
        finish()
        check('search_update_done', f"""(async()=>{{await lal.refreshDescription('library');await until(()=>!{SECTION}.querySelector('.search-update'));
          return {{edited:{STATE}==='edited',text:{SECTION}.querySelector('.description-text').textContent==={json.dumps(NEW)}}}}})()""")

        select(NONE)
        check('none_offers_generate', f"""(()=>({{state:{STATE}==='none',line:{SECTION}.textContent.includes('No description yet'),
          action:!!{BUTTON}('Generate description'),noEdit:!{BUTTON}('Edit'),dropped:{no_dropped()}}}))()""")
        capture('05-none.png')
        # Something else runs first, so this asset waits in line.
        processing_queue.add(config, 'descriptions', {'key': one['key'], 'asset_ids': [GENERATED], 'mode': 'edited'})
        js(f"(async()=>{{{BUTTON}('Generate description').click();return true}})()")
        described('queued')
        check('queued_shows_its_place', f"""(()=>({{line:{SECTION}.textContent.includes('Waiting to be described · 2nd in line'),noAction:!{SECTION}.querySelector('button'),
          noQueueToast:!lal.state.toasts.some(t=>/Waiting in line|Started/.test(t.title))}}))()""")
        capture('06-queued.png')
        finish()
        described('running')
        check('running_shows_it', f"""(()=>({{line:{SECTION}.textContent.includes('Writing the description now'),noAction:!{SECTION}.querySelector('button')}}))()""")
        assert started[-1]['mode'] is None and started[-1]['asset_ids'] == [NONE], started
        capture('07-running.png')
        finish()

        select(FAILED)
        check('failed_offers_try_again', f"""(()=>({{state:{STATE}==='failed',reason:{SECTION}.textContent.includes('Description generation failed: Synthetic retained fault'),
          action:!!{BUTTON}('Try again'),dropped:{no_dropped()}}}))()""")
        capture('08-failed.png')
        js(f"(async()=>{{{BUTTON}('Try again').click();return true}})()")
        described('running')
        assert started[-1]['mode'] == 'retry' and started[-1]['asset_ids'] == [FAILED], started
        report['checks']['try_again_queued_for_this_asset_only'] = True
        finish()

        setup['ready'] = False
        select(NONE)
        check('not_set_up_offers_setup', f"""(()=>({{state:{STATE}==='not_set_up',line:{SECTION}.textContent.includes('The description model is not installed'),
          action:!!{BUTTON}('Set up descriptions'),noGenerate:!{BUTTON}('Generate description')}}))()""")
        capture('09-not-set-up.png')
        check('setup_opens_descriptions_step', f"""(async()=>{{{BUTTON}('Set up descriptions').click();
          await until(()=>lal.state.setup.open&&!lal.state.setup.loading&&lal.SETUP_STEPS[lal.state.setup.step]==='descriptions');await frame();return true}})()""")
        ui.capture('10-setup-descriptions-step.png')
        js("lal.closeSetup()")
        setup['ready'] = True

        js("lal.setAppearance('dark')")
        select(GENERATED)
        capture('d11-edited-dark.png')
        js("lal.setAppearance('system')")
        js(f"lal.inspectFolder({json.dumps(one['key'])},'')")
        check('no_review_chip_on_cards', """(async()=>{await until(()=>document.querySelectorAll('#sources-grid .card-wrap').length===3);await frame();
          const cards=[...document.querySelectorAll('#sources-grid .card-wrap')];
          return {cards:cards.length===3,noReview:cards.every(c=>!/Review|Approved|pending/.test(c.textContent))}})()""")
        ui.capture('12-folder-cards.png')
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
        report['started'] = started
        (OUT / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        window.destroy()


try:
    webview.start(verify, gui='edgechromium', private_mode=True, storage_path=str(profile))
finally:
    bridge._close()
    record_profile_outcome(bridge, profile)
print(json.dumps({k: report[k] for k in ('status', 'reason') if k in report}, indent=2))
sys.exit(0 if report['status'] == 'passed' else 1)
