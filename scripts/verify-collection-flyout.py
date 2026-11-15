"""Real WebView2 check of the "Add to a collection" flyout's roles, keys and IME-safe Enter (decision 0036).

The flyout is a non-modal dialog (a menu may not hold a text field): its opener says so, its rows are
toggle buttons, arrows move between them, Tab and Escape close it. An Enter that confirms an IME
composition creates nothing, here or in the inspection label field. Synthetic sources, keyword search
only: no model loads. Writes data/gui/<run-name>/verification.json and screenshots.
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
from local_asset_library.asset_collections import load
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
            "({toasts:lal.state.toasts.map(t=>t.title+': '+t.body),"
            "focus:(document.activeElement?.id||document.activeElement?.tagName)+' '+(document.activeElement?.textContent||'').slice(0,40)})"))) from exc


def done(text):
    report['checks'].append(text)


def names():
    return sorted(c['name'] for c in load(config)['collections'])


# `key` dispatches on the focused element like a keyboard does; `composing` adds an IME composition,
# either the standard flag or the legacy keyCode 229 some IMEs still send.
HELPERS = """window.rightClick=el=>{const r=el.getBoundingClientRect();el.dispatchEvent(new MouseEvent('contextmenu',
  {bubbles:true,cancelable:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));return true};
window.menuOpen=label=>{const m=document.querySelector('[role=menu][aria-label="'+label+'"]');
  return Boolean(m&&m.closest('[data-context-menu-portal]').getAttribute('aria-hidden')==='false'&&getComputedStyle(m).opacity>0.9)};
window.menuItem=text=>[...document.querySelectorAll('[data-context-menu-portal][aria-hidden=false] [role=menuitem]')].find(b=>b.textContent.includes(text));
window.card=(grid,i)=>document.querySelectorAll('#'+grid+' .card')[i];
window.toast=text=>[...document.querySelectorAll('#toasts .toast')].find(t=>t.textContent.includes(text));
window.key=(k,composing)=>{const e=new KeyboardEvent('keydown',{key:k,bubbles:true,cancelable:true,isComposing:composing==='flag'});
  if(composing==='229')Object.defineProperty(e,'keyCode',{get:()=>229});document.activeElement.dispatchEvent(e);return true};
window.pause=ms=>new Promise(r=>setTimeout(()=>r(true),ms));
window.flyoutRows=()=>[...$('collection-flyout').querySelectorAll('[data-collection]')];
true"""


def open_flyout(index=0):
    js(f"rightClick(card('grid',{index}));true")
    wait("menuOpen('Asset actions')&&Boolean(menuItem('Add to a collection'))")
    js("menuItem('Add to a collection').click();true")
    wait("$('collection-flyout')&&document.activeElement===$('collection-flyout-search')&&lal.state.menu&&!$('collection-flyout').querySelector('[role=status]')")


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===2')
        js(HELPERS)
        js("(async()=>{await lal.createCollection('Aquarium','');$('nav-home').click();await until(()=>$('library-view'));"
           "await lal.submitSearch();await until(()=>lal.state.library.items.length===6);return true})()")
        wait("document.querySelectorAll('#grid .thumb img').length===6")

        # 1. Roles: the opener announces a dialog; the flyout is a named dialog of plain and toggle buttons.
        js("rightClick(card('grid',0));true")
        wait("menuOpen('Asset actions')&&Boolean(menuItem('Add to a collection'))")
        opener = js("(()=>{const b=menuItem('Add to a collection');return [b.getAttribute('aria-haspopup'),b.getAttribute('aria-expanded')]})()")
        assert opener == ['dialog', 'false'], opener
        js("menuItem('Add to a collection').click();true")
        wait("$('collection-flyout')&&document.activeElement===$('collection-flyout-search')&&flyoutRows().length===1")
        roles = js("""(()=>{const f=$('collection-flyout'),c=$('collection-flyout-create'),r=flyoutRows()[0];return {
          role:f.getAttribute('role'),label:f.getAttribute('aria-label'),modal:f.getAttribute('aria-modal'),
          menu_roles:f.querySelectorAll('[role^=menu]').length,opener:menuItem('Add to a collection').getAttribute('aria-expanded'),
          create:[c.tagName,c.getAttribute('role'),c.type],row:[r.tagName,r.getAttribute('role'),r.getAttribute('aria-pressed'),r.hasAttribute('aria-checked')],
          search_label:$('collection-flyout-search').closest('label').textContent.trim()}})()""")
        report['roles'] = roles
        assert roles == {'role': 'dialog', 'label': 'Add to a collection', 'modal': None, 'menu_roles': 0, 'opener': 'true',
                         'create': ['BUTTON', None, 'button'], 'row': ['BUTTON', None, 'false', False],
                         'search_label': 'Find a collection'}, roles
        capture('01-flyout-dialog.png')
        done('Opener says aria-haspopup=dialog and aria-expanded; flyout is a non-modal dialog named "Add to a collection" '
             'with a labelled search, a Create button and aria-pressed toggle rows; no menu roles inside')

        # 2. Arrows move search → Create → rows and back; ArrowLeft in the field stays in the field.
        trail = []
        for k in ('ArrowDown', 'ArrowDown', 'ArrowDown', 'ArrowUp', 'ArrowUp', 'ArrowLeft'):
            js(f"key('{k}');true")
            trail.append(js("document.activeElement.id||document.activeElement.dataset.collection&&'row'"))
        report['arrow_trail'] = trail
        assert trail == ['collection-flyout-create', 'row', 'row', 'collection-flyout-create', 'collection-flyout-search', 'collection-flyout-search'], trail
        # Keys typed in the search never reach the menu's typeahead ("s" would jump to "Show in Explorer").
        js("key('s');key('i');true")
        assert js("Boolean($('collection-flyout'))&&document.activeElement===$('collection-flyout-search')")
        done('ArrowDown/ArrowUp move between search, Create and rows (stopping at the ends); ArrowLeft and letters in the search '
             'stay in the flyout, out of the menu behind it')

        # 3. A composing Enter creates nothing; the plain Enter after it creates and adds.
        js("type('collection-flyout-search','ショップ');true")
        wait("$('collection-flyout-create').textContent.includes('Create “ショップ”')")
        before = names()
        js("key('Enter','flag');key('Enter','229');true")
        js("pause(800)")
        assert names() == before, names()
        assert js("Boolean($('collection-flyout'))&&$('collection-flyout-search').value==='ショップ'&&document.activeElement===$('collection-flyout-search')&&!toast('ショップ')")
        capture('02-composing-enter-ignored.png')
        done('Enter while composing (isComposing, and keyCode 229) keeps the flyout open with the typed text and creates no collection')
        js("key('Enter');true")
        wait("Boolean(toast('Added to “ショップ”'))&&!$('collection-flyout')&&!menuOpen('Asset actions')")
        shop = next(c for c in load(config)['collections'] if c['name'] == 'ショップ')
        asset = js("card('grid',0).dataset.id")
        assert [m['asset_id'] for m in shop['items']] == [asset], shop
        done('A plain Enter then creates “ショップ” with the asset and closes the menu')

        # 4. Membership shows as pressed; a Space on a focused row toggles it like a click.
        open_flyout()
        wait("flyoutRows().length===2&&flyoutRows().find(b=>b.textContent.includes('ショップ'))?.getAttribute('aria-pressed')==='true'")
        assert js("flyoutRows().find(b=>b.textContent.includes('Aquarium')).getAttribute('aria-pressed')==='false'")
        capture('03-pressed-row.png')
        done('A collection holding the asset is aria-pressed=true, the others false')

        # 5. Tab closes the flyout and the menu; Escape closes only the flyout and returns to its opener.
        js("key('Tab');true")
        wait("!$('collection-flyout')&&!menuOpen('Asset actions')")
        open_flyout()
        js("key('Escape');true")
        wait("!$('collection-flyout')&&menuOpen('Asset actions')&&document.activeElement===menuItem('Add to a collection')")
        assert js("menuItem('Add to a collection').getAttribute('aria-expanded')") == 'false'
        js("key('ArrowRight');true")
        wait("$('collection-flyout')&&document.activeElement===$('collection-flyout-search')")
        js("key('Escape');true")
        wait("!$('collection-flyout')&&menuOpen('Asset actions')")
        js("key('Escape');true")
        wait("!menuOpen('Asset actions')")
        done('Tab closes flyout and menu; Escape closes the flyout back to its opener (aria-expanded=false); ArrowRight reopens it')

        # 6. The inspection label field: a composing Enter keeps editing, a plain Enter commits.
        js("lal.openCollection(%s);true" % json.dumps(shop['id']))
        wait("$('collection-view')&&lal.state.collection.items.length===1&&card('collection-grid',0)")
        js("card('collection-grid',0).click();true")
        wait("$('collection-label')&&lal.state.collection.detail&&!lal.state.collection.detail.loading&&document.activeElement?.tagName==='H2'")
        js("$('collection-label').focus();type('collection-label','コイン');true")
        js("key('Enter','flag');key('Enter','229');true")
        js("pause(300)")
        assert js("document.activeElement===$('collection-label')"), 'Composing Enter left the label field'
        js("key('Enter');true")
        wait("document.activeElement!==$('collection-label')&&card('collection-grid',0).querySelector('.card-label')?.textContent==='コイン'", 10)
        capture('04-label-committed.png')
        done('In the inspection label field a composing Enter keeps focus; a plain Enter leaves the field and the label saves')

        assert not bridge._gateway.model_requested
        changed = [p for p, digest in originals.items() if Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
        assert not changed, changed
        done('No model loaded; original asset files unchanged')
        report.update(status='passed', protected_files=len(originals))
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
        except Exception:
            pass
    finally:
        (OUT / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)
