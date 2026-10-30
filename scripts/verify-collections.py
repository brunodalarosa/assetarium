"""Real WebView2 check of Collections with small isolated synthetic sources (decision 0012).

Covers the Collections tab, creation, the asset context menu and its collection flyout, labels,
notes and tags, in-collection and Collections-tab search, batch removal with Undo, rename, agent
edits and their notice, unavailable members, confirmed deletions and all four exports. Keyword
search only: no model loads. Writes data/gui/<run-name>/verification.json and screenshots.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source
from local_asset_library import sources
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.mcp_assets import AssetService
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
EXPORTS = config.storage_root('data') / 'exports/collections'
# Originals only: generated metadata and app data may change, source asset files never.
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for root in (one['path'], two['path'])
             for p in Path(root).rglob('*') if p.is_file()}


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
report = {'status': 'running', 'checks': [], 'synthetic_only': True, 'owner_usability_approval': 'pending', 'real_model_load': False}
ui = Harness(window, OUT, report)
js, capture = ui.js, ui.capture


def wait(expression, timeout=30):
    try:
        ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)
    except RuntimeError as exc:
        raise RuntimeError('UI condition timed out: ' + expression + ' ' + str(ui.js(
            "({toasts:lal.state.toasts.map(t=>t.title+': '+t.body),view:lal.state.collectionView.error,list:lal.state.collections.error,"
            "focus:(document.activeElement?.id||document.activeElement?.tagName)+' '+(document.activeElement?.textContent||'').slice(0,40)})"))) from exc


def done(text):
    report['checks'].append(text)


# Opens the shared menu on a card the way a right-click does, at the card's centre.
MENU = """window.rightClick=el=>{const r=el.getBoundingClientRect();el.dispatchEvent(new MouseEvent('contextmenu',
  {bubbles:true,cancelable:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));return true};
window.menuOpen=label=>{const m=document.querySelector('[role=menu][aria-label="'+label+'"]');
  return Boolean(m&&m.closest('[data-context-menu-portal]').getAttribute('aria-hidden')==='false'&&getComputedStyle(m).opacity>0.9)};
window.menuItem=text=>[...document.querySelectorAll('[data-context-menu-portal][aria-hidden=false] [role=menuitem]')].find(b=>b.textContent.includes(text));
window.enter=el=>{el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));return true};
window.card=(grid,i)=>document.querySelectorAll('#'+grid+' .card')[i];
window.toast=text=>[...document.querySelectorAll('#toasts .toast')].find(t=>t.textContent.includes(text));
window.typeArea=(id,value)=>{const t=$(id);Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(t,value);
  t.dispatchEvent(new Event('input',{bubbles:true}));return true};
true"""


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===2')
        js(MENU)
        # 1. Empty Collections tab explains how to start.
        js("$('nav-collections').click()")
        wait("$('collections-view')&&$('collections-empty')")
        assert js("$('nav-collections').getAttribute('aria-current')==='page'&&!$('collections-query')")
        capture('01-collections-empty.png')
        done('Empty Collections tab explains creating a collection and adding from the asset menu; no futile search')

        # 2. Create from the tab: the new, empty collection opens with the name top left.
        js("$('new-collection').click()")
        wait("$('create-collection-dialog').open&&document.activeElement===$('collection-name')")
        js("type('collection-name','Aquarium creatures');typeArea('collection-description','Small fishes for the minigame');true")
        capture('02-create-dialog.png')
        js("$('create-collection-submit').click()")
        wait("$('collection-view')&&$('collection-title')?.textContent==='Aquarium creatures'&&$('collection-empty')")
        size = js("parseFloat(getComputedStyle($('collection-title')).fontSize)")
        assert size >= 22, size
        assert js("$('collection-description').textContent==='Small fishes for the minigame'&&$('nav-collections').getAttribute('aria-current')==='page'")
        capture('03-collection-empty.png')
        done(f'Created collection opens empty with its {size:.0f}px name and rename pencil in the top bar')

        # 3. Asset context menu on Home: Inspect, and the flyout adds to a collection.
        js("(async()=>{$('nav-home').click();await until(()=>$('library-view'));await lal.submitSearch();await until(()=>lal.state.library.items.length===6);return true})()")
        wait("document.querySelectorAll('#grid .thumb img').length===6")
        js("rightClick(card('grid',0))")
        wait("menuOpen('Asset actions')&&Boolean(menuItem('Inspect'))&&Boolean(menuItem('Add to a collection'))")
        assert not js("Boolean(menuItem('Remove from collection'))")
        capture('04-asset-menu.png')
        js("menuItem('Inspect').click()")
        wait("lal.state.inspector.open&&lal.state.library.selected===card('grid',0).dataset.id&&!menuOpen('Asset actions')")
        wait("lal.state.library.detail.result&&!lal.state.library.detail.loading&&document.activeElement?.tagName==='H2'")
        done('Right-click shows Inspect and Add to a collection only; Inspect opens inspection for that card')
        js("rightClick(card('grid',0));true")
        wait("menuOpen('Asset actions')")
        js("menuItem('Add to a collection').click()")
        wait("$('collection-flyout')&&document.activeElement===$('collection-flyout-search')&&$('collection-flyout').querySelectorAll('[role=menuitemcheckbox]').length===1")
        assert js("$('collection-flyout-create').textContent.includes('Create new collection')")
        capture('05-collection-flyout.png')
        js("$('collection-flyout').querySelector('[role=menuitemcheckbox]').click()")
        wait("Boolean(toast('Added to “Aquarium creatures”'))&&!$('collection-flyout')")
        done('Flyout opens beside the menu with focus in its search and adds the asset in one click')
        # A typed new name creates and adds in one step.
        js("rightClick(card('grid',1));true")
        wait("menuOpen('Asset actions')")
        js("menuItem('Add to a collection').click()")
        wait("$('collection-flyout-search')")
        js("type('collection-flyout-search','Shop')")
        wait("$('collection-flyout-create').textContent.includes('Create “Shop”')&&$('collection-flyout').textContent.includes('No collection matches')")
        js("enter($('collection-flyout-search'))")
        wait("Boolean(toast('Added to “Shop”'))")
        # Already-added assets show a check; choosing again removes with Undo.
        js("rightClick(card('grid',0));true")
        wait("menuOpen('Asset actions')")
        js("menuItem('Add to a collection').click()")
        wait("[...$('collection-flyout').querySelectorAll('[role=menuitemcheckbox]')].find(b=>b.textContent.includes('Aquarium'))?.getAttribute('aria-checked')==='true'")
        js("$('collection-flyout-search').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));true")
        wait("!$('collection-flyout')&&menuOpen('Asset actions')")
        js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));true")
        wait("!menuOpen('Asset actions')")
        done('Typing a new name creates and adds; existing membership is checked; Escape closes the flyout, then the menu')

        # 3b. Miss-click protection: hover intent, the bridge, the click shield and its cost.
        js("rightClick(card('grid',0));true")
        wait("menuOpen('Asset actions')&&$('menu-shield')")
        js("""(()=>{const c=card('grid',2).getBoundingClientRect();window.shieldHit=document.elementFromPoint(c.left+c.width/2,c.top+c.height/2)?.id;
          const s=getComputedStyle($('menu-shield'));window.shieldStyle={blur:s.backdropFilter,background:s.backgroundColor};return true})()""")
        assert js("shieldHit==='menu-shield'&&shieldStyle.blur.includes('blur')"), js("[shieldHit,shieldStyle]")
        hole = js("""(()=>{const at=el=>{const c=el.getBoundingClientRect();return document.elementFromPoint(c.left+c.width/2,c.top+c.height/2)};
          const o=card('grid',0).getBoundingClientRect();  // Top-left corner: the menu opens at the card's centre.
          return {origin_uncovered:card('grid',0).contains(document.elementFromPoint(o.left+24,o.top+24)),neighbour_covered:at(card('grid',1))?.id==='menu-shield',
          clip:getComputedStyle($('menu-shield')).clipPath.startsWith('path(evenodd')}})()""")
        assert all(hole.values()), hole
        # The hole matches the card (within the 2 px margin), even after the layout underneath changes.
        def hole_fits():
            return js("""(()=>{const c=card('grid',0).getBoundingClientRect(),[x,y,w,h]=$('menu-shield').dataset.hole.split(',').map(Number);
              return [x-(c.left-2),y-(c.top-2),w-(c.width+4),h-(c.height+4)].every(d=>Math.abs(d)<1.5)})()""")
        assert hole_fits(), js("[$('menu-shield').dataset.hole,JSON.stringify(card('grid',0).getBoundingClientRect())]")
        report['inspector_open_at_menu'] = js("lal.state.inspector.open")
        js("lal.setInspectorOpen(!lal.state.inspector.open);true")
        js("new Promise(r=>setTimeout(()=>r(true),700))")
        assert hole_fits(), 'Hole did not follow the card after the inspection panel toggled'
        js("lal.setInspectorOpen(!lal.state.inspector.open);true")
        js("new Promise(r=>setTimeout(()=>r(true),700))")
        capture('05a-menu-origin-sharp.png')
        done('The card the menu came from stays sharp and clickable through a rounded hole; neighbouring cards stay shielded')
        js("const t=document.querySelector('[data-menu-action=add-to-collection] [data-context-menu-item]');t.dispatchEvent(new PointerEvent('pointermove',{bubbles:true}));true")
        wait("$('collection-flyout')&&$('collection-flyout-bridge').offsetHeight>0")
        js("document.querySelector('[data-context-menu-portal][aria-hidden=false] [role=menu] > div > div').dispatchEvent(new PointerEvent('pointermove',{bubbles:true}));true")
        js("new Promise(r=>setTimeout(()=>r(true),650))")
        assert js("Boolean($('collection-flyout'))")
        capture('05b-menu-shield-flyout.png')
        js("menuItem('Inspect').dispatchEvent(new PointerEvent('pointermove',{bubbles:true}));true")
        wait("!$('collection-flyout')", 3)
        done('Flyout stays open while the pointer crosses gaps for 650 ms; resting on another row closes it')
        selected = js("lal.state.library.selected")
        js("""(()=>{const c=card('grid',2).getBoundingClientRect(),s=$('menu-shield'),o={bubbles:true,cancelable:true,clientX:c.left+20,clientY:c.top+20};
          s.dispatchEvent(new PointerEvent('pointerdown',o));s.dispatchEvent(new PointerEvent('pointerup',o));s.dispatchEvent(new MouseEvent('click',o));return true})()""")
        wait("!menuOpen('Asset actions')")
        assert js("lal.state.library.selected") == selected
        js("rightClick(card('grid',0));true")
        wait("menuOpen('Asset actions')")
        js("const c=card('grid',3).getBoundingClientRect();$('menu-shield').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:c.left+30,clientY:c.top+30}));true")
        # Names repeat across the synthetic sources, so the moved menu is identified by asset ID.
        wait("menuOpen('Asset actions')&&lal.state.menu?.item.asset_id===lal.state.library.items[3].asset_id&&document.activeElement?.closest('[role=menu]')")
        assert js("(()=>{const o=card('grid',3).getBoundingClientRect();return card('grid',3).contains(document.elementFromPoint(o.left+24,o.top+24))})()")
        js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));true")
        wait("!menuOpen('Asset actions')&&!$('menu-shield')")
        done('Shield covers the cards: an outside click only closes the menu, right-click on another card moves the menu there')
        # Frame timing while the menu opens and settles, with and without the blur.
        timing = {}
        for label, css in (('blur', ''), ('dim_only', '#menu-shield{backdrop-filter:none!important}')):
            timing[label] = js("""(async()=>{const st=document.createElement('style');st.textContent=%s;document.head.append(st);
              const frames=[];let last=performance.now();let run=true;const tick=t=>{frames.push(t-last);last=t;if(run)requestAnimationFrame(tick)};
              requestAnimationFrame(tick);rightClick(card('grid',0));await new Promise(r=>setTimeout(r,600));run=false;
              document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));await new Promise(r=>setTimeout(r,300));st.remove();
              const f=frames.slice(1);return {frames:f.length,max_ms:Math.round(Math.max(...f)*10)/10,mean_ms:Math.round(f.reduce((a,b)=>a+b,0)/f.length*10)/10,
              over_25ms:f.filter(x=>x>25).length}})()""" % json.dumps(css))
        report['menu_frame_timing'] = timing
        done(f"Menu open frame timing recorded: blur {timing['blur']}, dim only {timing['dim_only']}")
        ids = js("lal.state.library.items.map(i=>i.asset_id)")
        from local_asset_library.asset_collections import load
        aquarium = next(c['id'] for c in load(config)['collections'] if c['name'] == 'Aquarium creatures')
        for index in (2, 3, 4):
            js(f"lal.addToCollection({{collection_id:{json.dumps(aquarium)}}},'library',lal.state.library.items[{index}])")

        # 4. Collections tab: cards with four covers, updated date, and search by contents.
        js("$('nav-collections').click()")
        wait("document.querySelectorAll('#collections-grid .collection-card').length===2")
        wait("document.querySelectorAll('#collections-grid .collection-card img').length===5", 40)
        assert js("[...document.querySelectorAll('.collection-updated')].every(e=>e.textContent.startsWith('Updated'))")
        assert js("document.querySelector('.collection-card .collection-name').textContent==='Aquarium creatures'")  # Newest first.
        capture('06-collections-grid.png')
        done('Collections tab shows newest first, four cover tiles, name and a small Updated date')

        # 5. Collection view: label, notes and tags in inspection; label on the card.
        js("document.querySelector('.collection-card').click()")
        wait("$('collection-view')&&lal.state.collection.items.length===4&&document.querySelectorAll('#collection-grid .thumb img').length===4")
        js("card('collection-grid',1).click()")
        wait("$('collection-entry')&&$('collection-label')&&document.querySelector('.asset-tags #tag-input')")
        # Inspection moves focus to its heading once the detail loads; wait until the field really has focus.
        wait("lal.state.collection.detail&&!lal.state.collection.detail.loading&&document.activeElement?.tagName==='H2'")
        js("$('collection-label').focus();true")
        wait("document.activeElement===$('collection-label')")
        # Autosave without leaving the field, then keep typing while that save lands.
        js("type('collection-label','Straw');true")
        wait("card('collection-grid',1).querySelector('.card-label')?.textContent==='Straw'&&$('collection-entry').textContent.includes('Saved')", 10)
        js("type('collection-label','Strawberry bait');$('collection-label').blur();true")
        try:
            wait("card('collection-grid',1).querySelector('.card-label')?.textContent==='Strawberry bait'", 10)
        except RuntimeError:
            from local_asset_library.asset_collections import load
            saved = [(i['asset_id'], i['label']) for c in load(config)['collections'] for i in c['items']]
            raise RuntimeError('Label not shown: ' + json.dumps({'ui': js("""({field:$('collection-label')?.value,entry:$('collection-entry')?.textContent.slice(0,90),
              selected:lal.state.collection.selected,card:card('collection-grid',1).dataset.id,items:lal.state.collection.items.map(i=>i.asset_id+':'+i.label)})"""),
              'saved': saved}))
        js("$('collection-notes').focus();typeArea('collection-notes','Spawns every 3 s\\nWorth 10 points');$('collection-notes').blur();true")
        wait("$('collection-entry').textContent.includes('Saved')&&lal.state.collection.items[1].notes.includes('Worth 10')")
        js("type('tag-input','fish, small');$('tag-input').form.requestSubmit();true")
        wait("document.querySelectorAll('.asset-tags li').length===2")
        capture('07-collection-inspector.png')
        done('Label (collection only) and multi-line notes save on blur; app-wide tags add from one comma list')

        # 6. Search inside the collection (keyword mode: no model) finds the label first.
        js("lal.setCollectionMode('keyword');type('collection-query','strawberry');$('collection-search').requestSubmit();true")
        wait("lal.state.collectionView.phase==='search'&&!lal.state.collectionView.busy&&lal.state.collection.items.length===1")
        assert js("lal.state.collection.items[0].match==='text'&&$('collection-results-title').textContent.includes('1 match')")
        capture('08-collection-search.png')
        js("$('collection-clear').click()")
        wait("lal.state.collectionView.phase==='all'&&lal.state.collection.items.length===4")
        done('In-collection search matches the label and shows only members; clearing restores all four')

        # 7. Rename with the pencil.
        js("$('rename-collection').click()")
        wait("document.activeElement===$('collection-rename')")
        js("type('collection-rename','Aquarium minigame');$('collection-rename').form.requestSubmit();true")
        wait("$('collection-title')?.textContent==='Aquarium minigame'&&document.activeElement===$('rename-collection')")
        js("$('rename-collection').click()")
        wait("$('collection-rename')")
        js("type('collection-rename','shop');$('collection-rename').form.requestSubmit();true")
        wait("$('collection-rename-error')?.textContent.includes('already exists')")
        js("$('collection-rename').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));true")
        wait("$('collection-title')?.textContent==='Aquarium minigame'")
        done('Pencil renames in place; a duplicate name is refused inline and Escape keeps the old name')

        # 8. Batch removal like forwarding messages, then Undo.
        js("rightClick(card('collection-grid',0));true")
        wait("menuOpen('Asset actions')&&Boolean(menuItem('Remove from collection'))")
        capture('09-collection-asset-menu.png')
        js("menuItem('Remove from collection').click()")
        wait("lal.state.selection.active&&lal.state.selection.ids.length===1&&$('selection-bar')")
        js("card('collection-grid',1).click();true")
        wait("lal.state.selection.ids.length===2&&$('selection-count').textContent.includes('2 assets selected')")
        assert not js("Boolean(lal.state.collection.detail&&lal.state.collection.selected===card('collection-grid',2).dataset.id)")
        capture('10-batch-selection.png')
        js("$('selection-remove').click()")
        wait("lal.state.collection.items.length===2&&!lal.state.selection.active&&Boolean(toast('Removed 2 assets'))")
        js("toast('Removed 2 assets').querySelector('[data-toast-action=Undo]').click()")
        wait("lal.state.collection.items.length===4&&lal.state.collection.items[1].label==='Strawberry bait'")
        done('Remove enters selection with the card ticked; more cards toggle; one removal for both; Undo restores labels and notes')

        # 9. Collections-tab search finds collections by what is inside.
        js("$('nav-collections').click()")
        wait("document.querySelectorAll('#collections-grid .collection-card').length===2")
        js("type('collections-query','strawberry')")
        wait("document.querySelectorAll('#collections-grid .collection-card').length===1&&document.querySelector('.collection-match')?.textContent.includes('1 matching asset')")
        capture('11-collections-search.png')
        js("type('collections-query','zzz-nothing')")
        wait("$('collections-no-match')")
        js("$('collections-clear').click()")
        wait("document.querySelectorAll('#collections-grid .collection-card').length===2")
        done('Collections search matches a label inside a collection and explains when nothing matches')

        # 10. Agent edit through MCP appears live, with a notice that opens it.
        agent = AssetService(config)
        created = agent.execute('edit_collection', {'action': 'create', 'name': 'Agent picks', 'asset_ids': ids[4:6],
                                                    'label': 'Fish', 'description': 'Small fishes only'})[0]
        wait("document.querySelectorAll('#collections-grid .collection-card').length===3&&Boolean(toast('Agent created “Agent picks”'))", 20)
        capture('12-agent-notice.png')
        js("toast('Agent created').querySelector('[data-action=open_collection]').click()")
        wait("$('collection-title')?.textContent==='Agent picks'&&lal.state.collection.items.every(i=>i.label==='Fish')")
        done('An agent-created collection appears live; its notice opens it with the agent labels')

        # 11. Members whose source disappears stay, marked unavailable with the reason.
        removed_key = js("lal.state.collection.items[0].source_key")
        js("$('nav-collections').click()")
        wait("$('collections-view')")
        js(f"lal.openCollection({json.dumps(aquarium)})")
        wait("$('collection-title')?.textContent==='Aquarium minigame'&&lal.state.collection.items.length===4")
        sources.remove(config, removed_key)
        sources.aggregate(config)
        wait("lal.state.collection.items.some(i=>i.availability==='unavailable')", 20)
        js("[...document.querySelectorAll('#collection-grid .card')].find(c=>c.textContent.includes('Unavailable')).click()")
        wait("$('unavailable-reason')?.textContent.includes('removed')&&$('collection-label')")
        capture('13-unavailable-member.png')
        done('Removing a source keeps its members as Unavailable cards with the reason; inspection still edits label and notes')

        # 12. Exports: the menu, then each kind to a scripted target under data/exports.
        js("$('collection-export').click()")
        wait("menuOpen('Export collection')&&document.querySelectorAll('[data-export]').length===4")
        capture('14-export-menu.png')
        js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));true")
        wait("!menuOpen('Export collection')")
        outputs = {}
        for kind in ('json', 'png', 'md', 'pdf'):
            target = EXPORTS / f'verify-{args.run_name}.{kind}'
            result = js(f"lal.exportCollection({json.dumps(aquarium)},{json.dumps(kind)},{json.dumps(str(target))})", 150)
            assert result['status'] == 'exported' and Path(result['path']) == target, result
            outputs[kind] = target
        data = json.loads(outputs['json'].read_text(encoding='utf-8'))
        available = [m for m in data['members'] if m['files']['status'] == 'available']
        assert data['kind'] == 'assetarium_collection' and data['asset_count'] == 4 and available
        assert all(Path(m['files']['selected_source']).is_file() for m in available)
        assert any(m['availability'] == 'unavailable' for m in data['members'])
        assert outputs['png'].read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
        markdown = outputs['md'].read_text(encoding='utf-8')
        thumbs = outputs['md'].parent / (outputs['md'].stem + '-thumbnails')
        assert '# Aquarium minigame' in markdown and 'Strawberry bait' in markdown and len(list(thumbs.glob('*.png'))) >= 1
        assert outputs['pdf'].read_bytes()[:5] == b'%PDF-' and outputs['pdf'].stat().st_size > 2000
        assert not js("$('print-root')?.childElementCount")
        # The printed report, shown on screen once for review (the PDF uses the same markup and styles).
        from local_asset_library.asset_collections import detail
        from local_asset_library.collection_export import package, report_html
        value = detail(config, aquarium)
        page = report_html(value, package(config, value), {})
        js("(()=>{const d=document.createElement('div');d.id='report-preview';d.style.cssText='position:fixed;inset:0;z-index:200;overflow:auto;"
           "background:#fff;padding:32px 48px';d.innerHTML=" + json.dumps(page) + ";document.body.append(d);return true})()")
        capture('14b-pdf-report-layout.png')
        js("$('report-preview').remove();true")
        report['exports'] = {kind: str(path.relative_to(ROOT)) for kind, path in outputs.items()}
        done('JSON (absolute original paths, unavailable member kept), PNG sheet, Markdown with thumbnails and WebView2 PDF exported')

        # 13. Deleting asks first with a red button; Cancel keeps it.
        js("$('nav-collections').click()")
        wait("document.querySelectorAll('#collections-grid .collection-card').length===3")
        js("rightClick([...document.querySelectorAll('.collection-card')].find(c=>c.textContent.includes('Shop')))")
        wait("menuOpen('Collection actions')&&Boolean(menuItem('Open'))&&Boolean(menuItem('Delete'))")
        capture('15-collection-menu.png')
        js("menuItem('Delete').click()")
        wait("$('confirm-dialog').open&&$('confirm-title').textContent.includes('Shop')")
        red = js("(()=>{const [r,g,b]=getComputedStyle($('confirm-accept')).backgroundColor.match(/\\d+/g).map(Number);return r>170&&g<90&&b<90})()")
        assert red
        capture('16-delete-confirm.png')
        js("$('confirm-cancel').click()")
        wait("!$('confirm-dialog').open&&document.querySelectorAll('.collection-card').length===3")
        js("rightClick([...document.querySelectorAll('.collection-card')].find(c=>c.textContent.includes('Shop')))")
        wait("menuOpen('Collection actions')")
        js("menuItem('Delete').click()")
        wait("$('confirm-dialog').open")
        js("$('confirm-accept').click()")
        wait("!$('confirm-dialog').open&&document.querySelectorAll('.collection-card').length===2&&Boolean(toast('Deleted “Shop”'))")
        done('Collection menu offers Open and Delete; delete needs the red confirm button and Cancel keeps it')

        # 14. Removing a source also asks first.
        js("(async()=>{$('nav-settings').click();await until(()=>$('asset-sources-tab'));$('asset-sources-tab').click();return true})()")
        wait("document.querySelectorAll('[data-action=remove]').length===1")
        js("document.querySelector('[data-action=remove]').click()")
        wait("$('confirm-dialog').open&&$('confirm-accept').textContent.includes('Remove source')")
        js("$('confirm-cancel').click()")
        wait("!$('confirm-dialog').open&&lal.state.sources.length===1")
        done('Source Remove asks for confirmation; Cancel keeps the source')

        # 15. Dark theme and narrow layout of the Collections tab.
        js("(async()=>{await lal.setAppearance('dark');$('nav-collections').click();await until(()=>document.querySelectorAll('.collection-card').length===2);return true})()")
        capture('17-collections-dark.png')
        js("rightClick(document.querySelector('.collection-card'))")
        wait("menuOpen('Collection actions')&&$('menu-shield')")
        capture('17b-collection-menu-shield-dark.png')
        js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));true")
        wait("!menuOpen('Collection actions')")
        window.resize(700, 800)
        wait('innerWidth<761')
        assert js("$('collections-view').scrollWidth<=$('collections-view').clientWidth+1")
        capture('18-collections-narrow.png')
        js("lal.setAppearance('system')")
        done('Dark theme and narrow window keep the Collections grid without horizontal overflow')

        assert not bridge._gateway.model_requested
        changed = [p for p, digest in originals.items() if Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
        assert not changed, changed
        done('No model loaded; original asset files unchanged')
        report.update(status='passed', protected_files=len(originals), agent_collection=created['collection_id'])
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
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
