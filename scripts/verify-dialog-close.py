"""Verify the native modal dialogs stay in sync with the store however they close, in the real WebView2 shell.

The confirm, create-collection and run-report dialogs are closed by the browser itself (dialog.close() and
requestClose(), standing in for a repeated Esc the page cannot prevent): the store's request must clear and
the next request must reopen the dialog. While an action is busy, closedby is "none" and requestClose()
leaves the dialog open. Synthetic sources only; writes data/gui/<run-name>/verification.json.
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
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from local_asset_library.publication import atomic_json  # noqa: E402
from gui_harness import Harness, isolate_hash_cache  # noqa: E402
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir()
config, _, one, two = managed.__wrapped__(fixture)
hold_create = threading.Event()
release_create = threading.Event()


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def collection_action(self, action, collection_id=None, options=None):
        # Holds one create in flight so the dialog stays busy until the script releases it.
        if action == 'create' and hold_create.is_set():
            release_create.wait(60)
        return super().collection_action(action, collection_id, options)


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': {}, 'synthetic_only': True}
ui = Harness(window, OUT, report)

# Each dialog: its element, how to open it, and the store field that holds its request.
DIALOGS = {
    'confirm': ("$('confirm-dialog')",
                "lal.askConfirm({tone:'neutral',title:'Synthetic question',body:'Nothing happens.',confirmLabel:''})",
                'lal.state.confirm'),
    'create-collection': ("$('create-collection-dialog')", 'lal.openCreateCollection()', 'lal.state.create'),
    'run-report': ("document.querySelector('dialog[aria-labelledby=run-report-title]')",
                   "lal.setState({runReport:{kind:'description_report',outcome:'complete',source_name:'one',written:1,failed:0,remaining:0}})",
                   'lal.state.runReport'),
}


def opened(dialog, open_it, field):
    return f"(async()=>{{{open_it};await until(()=>{dialog}.open&&{field});await frame();return {dialog}.open&&Boolean({field})}})()"


def closed_by_browser(dialog, field, how):
    return f"(async()=>{{{dialog}.{how}();await until(()=>!{dialog}.open&&!{field});await frame();return !{dialog}.open&&{field}===null}})()"


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===2')
        ui.check('environment', "({userAgent:navigator.userAgent,closedBy:'closedBy' in HTMLDialogElement.prototype,"
                 "requestClose:'requestClose' in HTMLDialogElement.prototype})")
        for name, (dialog, open_it, field) in DIALOGS.items():
            ui.check(f'{name}: opens', opened(dialog, open_it, field))
            ui.check(f'{name}: dialog.close() clears the store', closed_by_browser(dialog, field, 'close'))
            ui.check(f'{name}: the next request reopens it', opened(dialog, open_it, field))
            ui.check(f'{name}: idle closedby is closerequest', f"{dialog}.closedBy==='closerequest'&&{dialog}.getAttribute('closedby')==='closerequest'")
            ui.check(f'{name}: idle requestClose() closes and clears', closed_by_browser(dialog, field, 'requestClose'))
            ui.check(f'{name}: reopens after requestClose()', opened(dialog, open_it, field))
            # close() queues its close event; a request arriving before it fires must survive it.
            ui.check(f'{name}: a request made before the close event fires stays open', f"""(async()=>{{
              {dialog}.close();{open_it};const request={field};
              await new Promise(r=>setTimeout(r,200));await frame();
              return {{open:{dialog}.open,kept:Boolean(request)&&{field}===request}}}})()""")
            if name == 'confirm':
                ui.capture('01-confirm.png')
            ui.js(f"{dialog}.close()")
            ui.js(f"until(()=>!{field})")

        # Focus: the confirm dialog starts on Cancel and returns focus to its invoker.
        ui.check('confirm: initial focus on Cancel and focus returns to the invoker', """(async()=>{
          const invoker=$('nav-processing');invoker.focus();
          lal.askConfirm({tone:'neutral',title:'Synthetic question',body:'Nothing happens.',confirmLabel:''});
          await until(()=>$('confirm-dialog').open);await frame();
          const initial=document.activeElement.id;$('confirm-cancel').click();
          await until(()=>!$('confirm-dialog').open);await frame();
          return {initial:initial==='confirm-cancel',returned:document.activeElement===invoker,cleared:lal.state.confirm===null}})()""")

        # Busy confirm: a run waiting on a promise the script resolves.
        ui.js("""(async()=>{window.finishRun=null;
          lal.askConfirm({tone:'neutral',title:'Synthetic run',body:'Waits for the script.',confirmLabel:'Run',
            run:()=>new Promise(r=>{window.finishRun=()=>r({status:'ready'})})});
          await until(()=>$('confirm-dialog').open&&$('confirm-accept'));$('confirm-accept').click();
          await until(()=>window.finishRun&&$('confirm-dialog').closedBy==='none');return true})()""")
        ui.capture('02-confirm-busy.png')
        ui.check('confirm busy: closedby none and requestClose() leaves it open', """(async()=>{const d=$('confirm-dialog'),request=lal.state.confirm;
          d.requestClose();await frame();await new Promise(r=>setTimeout(r,200));
          return {attribute:d.getAttribute('closedby')==='none',open:d.open,kept:lal.state.confirm===request}})()""")
        ui.check('confirm busy: a browser close clears it and the finished run does not reopen it', """(async()=>{const d=$('confirm-dialog');
          d.close();await until(()=>!lal.state.confirm);finishRun();await new Promise(r=>setTimeout(r,200));await frame();
          return {closed:!d.open,cleared:lal.state.confirm===null}})()""")
        ui.check('confirm: a run that ends after its dialog closed leaves a newer request alone', """(async()=>{let fail;
          lal.askConfirm({tone:'neutral',title:'Old run',body:'Fails late.',confirmLabel:'Run',run:()=>new Promise((_,j)=>{fail=()=>j(Error('late'))})});
          await until(()=>$('confirm-dialog').open&&$('confirm-accept'));$('confirm-accept').click();await until(()=>fail);
          $('confirm-dialog').close();await until(()=>!lal.state.confirm);
          lal.askConfirm({tone:'neutral',title:'Newer question',body:'Stays clean.',confirmLabel:''});
          await until(()=>$('confirm-dialog').open&&$('confirm-title').textContent==='Newer question');
          fail();await new Promise(r=>setTimeout(r,200));await frame();
          const clean=!$('confirm-dialog').querySelector('[role=alert]')&&$('confirm-title').textContent==='Newer question'&&$('confirm-dialog').open;
          $('confirm-cancel').click();await until(()=>!$('confirm-dialog').open);return clean})()""")

        # Busy create-collection: the bridge holds the create until the script releases it.
        hold_create.set()
        ui.js("""(async()=>{lal.openCreateCollection();await until(()=>$('create-collection-dialog').open);
          type('collection-name','Synthetic dialog check');await frame();$('create-collection-submit').click();
          await until(()=>$('create-collection-dialog').closedBy==='none');return true})()""")
        ui.check('create-collection busy: closedby none and requestClose() leaves it open', """(async()=>{const d=$('create-collection-dialog'),request=lal.state.create;
          d.requestClose();await frame();await new Promise(r=>setTimeout(r,200));
          return {attribute:d.getAttribute('closedby')==='none',open:d.open,kept:lal.state.create===request}})()""")
        release_create.set()
        ui.check('create-collection: the finished create closes and clears it', """(async()=>{
          await until(()=>!$('create-collection-dialog').open&&!lal.state.create,20000);return true})()""")
        hold_create.clear()
        assert not bridge._gateway.model_requested
        report['checks']['no inference worker or model was loaded'] = True
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        release_create.set()
        atomic_json(OUT / 'verification.json', report)
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(dict(report, report=str(OUT / 'verification.json')), indent=2))
raise SystemExit(report['status'] != 'passed')
