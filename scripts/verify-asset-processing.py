"""Real WebView2 check of the Asset processing page (design principle P7, decision 0032).

Synthetic sources only; no model, worker or Blender run. A synthetic running item and a waiting one fill the Now and
next timeline; recorded failures (one without a reason) and a run stopped by the search check fill Needs your
attention; a long history fills Recent activity. Checks the left-aligned layout, the header without versions (they
moved to Agent activity), the timeline, Dismiss / Show / Bring back / Dismiss all + Undo, that dismissing never
touches fault records, a dismissed failure coming back as Again when another asset fails the same way, Recent
activity folded until opened by scrolling past the end, its fading inner scroll, closing it on leaving the page,
tooltips and a narrow layout. Writes data/gui/<run-name>/report.json.
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
from test_sources import managed  # noqa: E402
from test_alternate_faults import fail, kit  # noqa: E402
from local_asset_library import processing_queue, sources  # noqa: E402
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from local_asset_library.incremental import working  # noqa: E402
from local_asset_library.publication import atomic_json  # noqa: E402
from gui_harness import Harness, isolate_hash_cache  # noqa: E402
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir()
config, _, one, two = managed.__wrapped__(fixture)
added = sources.add(config, str(kit(fixture / 'kit')))
sources.scan_source(config, added)
work = working(sources.bound(config, added))
records = sorted(sources.read_records(work), key=lambda r: r['display_name'])
REASON = 'Missing, rejected or unresolved texture dependencies: atlas'
fail(work, records[0], 'inspection', REASON)
fail(work, records[1], 'previews', '')  # Recorded without a reason: the page says so and never invents one.
sources.scan_source(config, added)

queue = processing_queue.load(config)
for source, status in ((one, 'running'), (two, 'waiting')):
    queue['items'].append({'id': source['key'] + '-item', 'action': 'previews', 'scope': {'key': source['key'], 'path': '', 'asset_ids': []},
                           'label': source['name'], 'added_utc': processing_queue.now(), 'status': status, 'estimate': {'seconds': [300, 600]},
                           **({'token': 'synthetic', 'started_utc': processing_queue.now(), 'resolved': 3} if status == 'running' else {})})
scope = {'key': added['key'], 'path': '', 'asset_ids': []}
queue['recent'] = [{'id': 'stopped', 'action': 'previews', 'scope': scope, 'label': 'kit', 'status': 'faulty',
                    'finished_utc': processing_queue.now(), 'reason': 'The search check did not pass, so search data was not built: synthetic'}]
queue['recent'] += [{'id': f'done-{n}', 'action': 'descriptions' if n % 2 else 'previews', 'scope': {**scope, 'path': f'Set/{n}'},
                     'label': f'Folder {n}', 'status': 'complete', 'resolved': n + 1, 'started_utc': '2026-11-20T10:00:00+00:00',
                     'finished_utc': '2026-11-20T10:0%d:00+00:00' % (n % 10)} for n in range(16)]
processing_queue.save(config, queue)
atomic_json(sources.bound(config, one).output_path('data', 'library/source-operation.json'),
            {'status': 'processing', 'token': 'synthetic', 'pid': os.getpid(), 'operation': 'process', 'completed': 1, 'total': 3,
             'phase': 'Rendering previews'})


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': {}, 'synthetic_only': True, 'owner_visual_approval': 'pending'}
ui = Harness(window, OUT, report)
js, check = ui.js, ui.check
CARDS = "[...document.querySelectorAll('#attention-list .attention-card')]"


def failed_stages():
    return {r['display_name']: {s: v for s, v in r['processing'].items() if v == 'failed'} for r in sources.read_records(work)}


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===3')
        window.resize(1600, 1000)
        js("until(()=>innerWidth>1400)")
        js("lal.navigate({page:'processing'});true")
        check('left_aligned_header_without_versions', """until(()=>$('now-next')&&$('attention')&&$('recent-activity')).then(()=>{
          const view=$('processing-view').getBoundingClientRect(),page=$('processing-view').firstElementChild.getBoundingClientRect();
          return {left:page.left-view.left<=33,notCentered:view.right-page.right>100,noCoverage:!$('coverage'),noVersion:!$('version')}})""")
        check('timeline', """until(()=>$('running-item')&&$('up-next')).then(()=>({
          running:$('running-item').querySelector('.timeline-pulse')!==null,
          waiting:$('up-next').querySelectorAll('li').length===1&&$('up-next').querySelector('.timeline-step span.border-2')!==null,
          pause:[...$('now-next').querySelectorAll('button')].some(b=>b.textContent==='Pause'),
          cancel:[...$('running-item').querySelectorAll('button')].some(b=>b.textContent.includes('Cancel'))}))""")
        ui.capture('01-asset-processing.png')
        check('attention_cards', f"""until(()=>{CARDS}.length>=3).then(()=>{{const cards={CARDS};
          const failure=cards.find(c=>c.dataset.kind==='failure'&&c.textContent.includes('texture dependencies'));
          const silent=cards.find(c=>c.querySelector('.no-reason'));
          const run=cards.find(c=>c.dataset.kind==='run');
          return {{failure:!!failure&&!!failure.querySelector('[data-action=recheck]')&&!!failure.querySelector('[data-action=library]'),
            noReason:!!silent&&silent.querySelector('.no-reason').textContent==='No reason was recorded for this asset',
            runCheck:!!run&&!!run.querySelector('[data-action=run-search-check]'),
            notInvented:!$('attention').textContent.includes('Recorded failure')}}}})""")
        before = failed_stages()
        js(f"{CARDS}.find(c=>c.textContent.includes('texture dependencies')).querySelector('.attention-dismiss').click();true")
        check('dismiss_hides_and_counts', f"""until(()=>!{CARDS}.some(c=>c.textContent.includes('texture dependencies'))&&$('attention-show-dismissed')).then(()=>
          $('attention-show-dismissed').textContent==='1 dismissed · Show')""")
        assert failed_stages() == before, 'Dismissing changed a fault record'
        report['checks']['fault_records_unchanged'] = True
        js("$('attention-show-dismissed').click();true")
        check('show_lists_dismissed_dimmed', f"""until(()=>{CARDS}.some(c=>c.dataset.dismissed==='true')).then(()=>{{
          const card={CARDS}.find(c=>c.dataset.dismissed==='true');return {{restore:!!card.querySelector('.attention-restore'),
          noActions:!card.querySelector('[data-action=recheck]'),label:$('attention-show-dismissed').textContent==='1 dismissed · Hide'}}}})""")
        ui.capture('02-dismissed-shown.png')
        js(f"{CARDS}.find(c=>c.dataset.dismissed==='true').querySelector('.attention-restore').click();true")
        check('bring_back', f"until(()=>!$('attention-show-dismissed')&&{CARDS}.every(c=>c.dataset.dismissed==='false'))")
        count = js(f"{CARDS}.length")
        js("$('attention-dismiss-all').click();true")
        check('dismiss_all_with_undo', f"""until(()=>$('attention-empty')&&[...document.querySelectorAll('#toasts button')].some(b=>b.textContent==='Undo')).then(()=>
          $('attention-show-dismissed').textContent==='{count} dismissed · Show')""")
        ui.capture('03-dismissed-all.png')
        js("[...document.querySelectorAll('#toasts button')].find(b=>b.textContent==='Undo').click();true")
        check('undo_brings_all_back', f"until(()=>{CARDS}.length==={count}&&!$('attention-show-dismissed'))")
        # Dismissed, then the same step fails for the same reason in another asset: it comes back marked Again.
        js(f"{CARDS}.find(c=>c.textContent.includes('texture dependencies')).querySelector('.attention-dismiss').click();true")
        js(f"until(()=>!{CARDS}.some(c=>c.textContent.includes('texture dependencies')))")
        fail(work, sources.read_records(work)[[r['display_name'] for r in sources.read_records(work)].index(records[2]['display_name'])], 'inspection', REASON)
        sources.scan_source(config, added)
        check('returns_again', f"""until(()=>{CARDS}.some(c=>c.textContent.includes('texture dependencies')&&c.dataset.again==='true'),20000).then(()=>
          {CARDS}.find(c=>c.dataset.again==='true').textContent.includes('Again'))""", timeout=30)
        ui.capture('04-again.png')
        # Recent activity: folded into one summary line; scrolling on past the end of the page opens it.
        check('recent_folded', """({closed:!$('recent-activity').open,more:$('recent-summary').textContent.includes('more'),
          stopped:$('recent-summary').textContent.includes('Stopped')})""")
        check('scroll_past_end_opens', """(async()=>{const view=$('processing-view');view.scrollTop=view.scrollHeight;await frame();
          view.dispatchEvent(new WheelEvent('wheel',{deltaY:120,bubbles:true}));await until(()=>$('recent-activity').open);
          await new Promise(r=>setTimeout(r,500));const list=document.querySelector('.recent-scroll');const style=getComputedStyle(list);
          return {open:true,innerScroll:list.scrollHeight>list.clientHeight&&style.overflowY==='auto',masked:style.maskImage!=='none',
            items:$('recent-items').children.length>10}})()""")
        check('fades_only_where_more', """(async()=>{const list=document.querySelector('.recent-scroll'),fade=e=>getComputedStyle(list).getPropertyValue('--fade-'+e);
          list.scrollTop=0;await frame();const top={start:fade('start'),end:fade('end')};list.scrollTop=list.scrollHeight;await frame();
          const bottom={start:fade('start'),end:fade('end')};list.scrollTop=0;await frame();
          return {topClear:top.start==='0px',moreBelow:top.end!=='0px',bottomClear:bottom.end==='0px',moreAbove:bottom.start!=='0px',detail:JSON.stringify({top,bottom})}})()""")
        js("$('processing-view').scrollTop=$('processing-view').scrollHeight;true")
        ui.capture('05-recent-activity-open.png')
        check('scrolling_up_keeps_it_open', """(async()=>{const view=$('processing-view');view.scrollTop=0;
          view.dispatchEvent(new WheelEvent('wheel',{deltaY:-120,bubbles:true}));await frame();return $('recent-activity').open})()""")
        check('leaving_the_page_closes_it', """(async()=>{lal.navigate({page:'collections'});await until(()=>!$('processing-view'));
          lal.navigate({page:'processing'});await until(()=>$('recent-activity'));return !$('recent-activity').open})()""")
        check('click_opens_it', "(async()=>{document.querySelector('#recent-activity summary').click();await frame();return $('recent-activity').open})()")
        check('reduced_motion_rules', """[...document.styleSheets].flatMap(s=>[...s.cssRules]).some(r=>r.media&&r.media.mediaText.includes('reduce')
          &&r.cssText.includes('recent-chevron')&&r.cssText.includes('timeline-pulse'))""")
        # Versions and Refresh published view now live in Agent activity.
        js("$('open-agent-activity').click();true")
        check('versions_in_agent_activity', """until(()=>$('published-view')).then(()=>({
          refresh:[...$('published-view').querySelectorAll('button')].some(b=>b.textContent.includes('Refresh published view'))}))""")
        js("$('open-agent-activity').click();true")
        check('tooltips', """(()=>{const controls=[...$('processing-view').querySelectorAll('button,[role=button],summary')];
          return controls.length>0&&controls.every(e=>e.matches('[data-tooltip],[data-no-tooltip]')||e.closest('[data-tooltip]'))})()""")
        # Nothing running or waiting: the timeline's empty state names the pending work and the way to Asset sources.
        value = processing_queue.load(config)
        value['items'] = []
        processing_queue.save(config, value)
        atomic_json(sources.bound(config, one).output_path('data', 'library/source-operation.json'),
                    {'status': 'complete', 'token': 'synthetic', 'operation': 'process', 'phase': 'Done'})
        js("(async()=>{lal.navigate({page:'collections'});await until(()=>!$('processing-view'));lal.navigate({page:'processing'});return true})()")
        check('empty_state', """until(()=>$('nothing-running')).then(()=>({asset_sources:$('nothing-running').textContent.includes('Asset sources'),
          says:$('nothing-running').textContent.startsWith('Nothing is running or waiting.')}))""")
        window.resize(680, 900)
        js('until(()=>innerWidth<761)')
        check('narrow_no_overflow', "$('processing-view').scrollWidth<=$('processing-view').clientWidth+1")
        ui.capture('06-narrow.png')
        assert not bridge._gateway.model_requested
        report['checks']['no_model_loaded'] = True
        report.update(status='passed')
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        atomic_json(OUT / 'report.json', report)
        bridge._allow_close = True
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
bridge._close()
record_profile_outcome(bridge, profile)
print(json.dumps({'status': report['status'], 'report': str(OUT / 'report.json'), 'reason': report.get('reason', '')}, indent=2))
sys.exit(0 if report['status'] == 'passed' else 1)
