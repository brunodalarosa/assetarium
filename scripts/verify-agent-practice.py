"""Verify Try your agent in the real desktop, using the actual pack gateway, scans and review controls.

Only synthetic libraries are used. Reports and screenshots are development evidence under data/gui;
the product's generated practice files, store and activity must all disappear when it finishes.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed
from local_asset_library import agent_practice, sources
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.mcp_server import Gateway
from local_asset_library.publication import atomic_json
from local_asset_library.setup_agent import note_client, remove_connection, write_connection
from gui_harness import Harness, isolate_hash_cache
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
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for s in (one, two)
             for p in Path(s['path']).rglob('*') if p.is_file()}
folders_before = sources.registry(config)


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result


agent = Gateway(config)
agent.client = {'name': 'practice-verification-agent', 'version': '1'}
write_connection(config.project_root, agent.run_id, 'normal')
note_client(config.project_root, os.getpid(), agent.client)


def tool(name, **arguments):
    result = asyncio.run(agent.call(name, arguments))
    payload = json.loads(result.content[0].text)
    assert not result.is_error, payload
    return payload


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config, prestart_worker=False)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': {}, 'synthetic_only': True, 'owner_visual_review': 'pending'}
ui = Harness(window, OUT, report)


def wait(expression, seconds=30):
    ui.js('until(()=>(%s),%d)' % (expression, seconds * 1000), seconds + 5)


def verify():
    try:
        ui.wait_ready()
        ui.js("lal.navigate({page:'settings'})")
        wait("$('try-agent-start')&&!$('try-agent-start').matches(':disabled,[aria-disabled=true]')")
        ui.check('old_checker_removed', "!$('model-check-card')")
        ui.js("$('try-agent-start').click()")
        wait("lal.state.addFolder.step==='found'")
        ui.capture('01-practice-packs.png')
        ui.check('shared_discovery', "!!$('found-counts')&&!!$('found-why')&&!$('add-folder-myself')")
        ui.js("$('add-folder-agent').click()")
        wait("lal.state.addFolder.step==='agent'&&!!$('agent-take-over-prompt')")
        key = ui.js('lal.state.addFolder.key')
        root = agent_practice._root(config, key)
        listed = tool('list_packs', library_folder=key)
        for pack in listed['packs']:
            tool('get_pack_outline', library_folder=key, path=pack['pack'])
            tool('finish_structure', library_folder=key, pack=pack['pack'])
        wait("!!lal.state.addFolder.practiceState?.checks.length")
        ui.check('marking_reviewed_does_not_pass', "lal.state.addFolder.step==='agent'&&!lal.state.addFolder.practiceState.complete")
        for pack, rules in (
            ('Village Props', [{'kind': 'engine_copy', 'folder': 'Unity Models', 'of': 'Models'}]),
            ('Castle Kit/v1.2', [{'kind': 'pack', 'folder': '', 'value': 'merge'}]),
            ('Terrain Pack', [{'kind': 'image_kind', 'folder': 'Art', 'value': 'texture'}]),
            ('Hero Pack', [{'kind': 'image_kind', 'folder': 'Art', 'value': 'image'}]),
        ):
            tool('propose_profile', library_folder=key, pack=pack, rules=rules, note='Practice organization decision')
        wait("document.querySelector('#add-folder-wizard .proposal-review')")
        ui.check('real_review_and_activity', "!!$('take-over-feed')&&document.querySelectorAll('#take-over-feed li').length>0")
        ui.capture('02-proposals.png')
        window.resize(680, 900)
        wait('innerWidth<761')
        ui.check('narrow_layout_fits', "$('add-folder-wizard').querySelector('section').getBoundingClientRect().right<=innerWidth+1")
        ui.capture('03-narrow-review.png')
        ui.js("document.querySelector('#add-folder-wizard [data-action=accept-all]').click()")
        wait("!document.querySelector('#add-folder-wizard [data-action=apply-staged]').matches(':disabled,[aria-disabled=true]')")
        ui.js("document.querySelector('#add-folder-wizard [data-action=apply-staged]').click()")
        wait("!!$('agent-practice-result')", 60)
        ui.check('outcomes_and_cleanup', "lal.state.addFolder.result.cleaned&&lal.state.addFolder.result.checks.every(c=>c.passed)&&!$('add-folder-done')")
        assert not root.exists() and not agent_practice._parent(config).exists()
        ui.capture('04-results.png')
        ui.js("[...$('agent-practice-result').querySelectorAll('button')].find(b=>b.textContent==='Close').click()")
        wait("!$('add-folder-wizard')")
        ui.check('results_forgotten', "lal.state.practiceResult===null&&lal.state.addFolder.result===null")
        # Cancellation uses the same cleanup, even before the folder is added.
        ui.js("$('try-agent-start').click()")
        wait("lal.state.addFolder.step==='found'")
        ui.js("document.querySelector('#add-folder-wizard button[aria-label=\"Cancel practice and remove test data\"]').click()")
        wait("!$('add-folder-wizard')")
        assert not agent_practice._parent(config).exists()
        report['checks']['cancel_cleanup'] = True
        ui.js("(async()=>{await lal.openSetup();lal.goToSetupStep(lal.SETUP_STEPS.indexOf('practice'))})()")
        wait("$('setup-try-agent-start')&&!$('setup-try-agent-start').matches(':disabled,[aria-disabled=true]')")
        ui.js("$('setup-try-agent-start').click()")
        wait("lal.state.addFolder.step==='found'")
        ui.check('setup_reuses_same_practice', "lal.state.setup.open&&lal.state.addFolder.practice&&Number(getComputedStyle($('add-folder-wizard')).zIndex)>Number(getComputedStyle($('setup-wizard')).zIndex)")
        ui.capture('05-practice-from-setup.png')
        ui.js("document.querySelector('#add-folder-wizard button[aria-label=\"Cancel practice and remove test data\"]').click()")
        wait("!$('add-folder-wizard')")
        assert not agent_practice._parent(config).exists()
        ui.check('cancel_returns_to_setup', "lal.state.setup.open&&!!$('setup-try-agent')")
        assert sources.registry(config) == folders_before
        assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for s in (one, two)
                for p in Path(s['path']).rglob('*') if p.is_file()} == originals
        assert not bridge._gateway.model_requested and not agent.model_requested
        assert not list(agent.audit_root.iterdir())
        report['checks']['real_library_and_models_untouched'] = True
        report['status'] = 'passed'
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        atomic_json(OUT / 'verification.json', report)
        remove_connection(config.project_root)
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(dict(report, report=str(OUT / 'verification.json')), indent=2))
raise SystemExit(report['status'] != 'passed')
