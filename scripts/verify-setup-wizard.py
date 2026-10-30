"""Real WebView2 check of Setup (decision 0014) on isolated synthetic projects, in light and dark.

Phase "fresh": an empty project with the shipped example config opens setup by itself; every step,
Back/Next/Skip, arrow keys and focus, a failing and a passing Blender check, a fake local model
server, Save (which writes the discovered Blender, so the speed test can start without a restart)
and Skip; Settings → Blender installation shows it saved. Phase "existing" (a child process): an install with sources is not
interrupted; Run setup pre-fills; changing Blender asks to confirm re-rendering; descriptions off
removes Generate descriptions. Writes data/gui/<run-name>/report.json and screenshots.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests'), str(ROOT / 'scripts')]
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)
from local_asset_library import setup_core
from local_asset_library.config import load_project_config
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.publication import atomic_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
parser.add_argument('--phase', choices=['fresh', 'existing'], default='fresh', help=argparse.SUPPRESS)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
FIXTURE = ROOT / 'scratch' / args.run_name / args.phase
OUT.mkdir(parents=True, exist_ok=args.phase == 'existing')
FIXTURE.mkdir(parents=True, exist_ok=False)
os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
report = {'status': 'running', 'phase': args.phase, 'checks': {}, 'screenshots': [], 'synthetic_only': True,
          'owner_visual_review': 'pending', 'real_model_load': False}
probes = []
real_probe = setup_core._probe
setup_core._probe = lambda *a: probes.append(a[0][0]) or real_probe(*a)  # Counts every program setup runs.
STEPS = ['welcome', 'blender', 'formats', 'storage', 'descriptions', 'batch', 'review']
BLENDER = setup_core.blender_report  # noqa: F841 (discovery is the app's own)

if args.phase == 'fresh':
    for relative in ('config.example.toml', 'docs/caption-model.json', 'docs/embedding-model.json',
                     'scripts/storage-report.py'):
        (FIXTURE / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, FIXTURE / relative)
    config = load_project_config(FIXTURE)
else:
    from test_sources import managed, ready_source
    config, backend, one, two = managed.__wrapped__(FIXTURE)
    ready_source(config, backend, one)
    from local_asset_library.settings import save_general_settings
    save_general_settings(config, 40, ['gltf', 'obj'], 4)
    # A configured Blender that no longer exists, so choosing the installed one is a real change.
    example = (ROOT / 'config.example.toml').read_text(encoding='utf-8')
    missing = 'C:\\Missing Blender\\blender.exe' if os.name == 'nt' else '/missing/blender'
    (config.project_root / 'config.local.toml').write_text(setup_core.with_blender(example, missing), encoding='utf-8')

class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        if args.phase == 'existing':
            result['managed_sources'] = False  # Synthetic sources: no startup scan (the fixture has no .venv).
        return result


bridge = FixtureBridge(config)
import webview
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
ui = Harness(window, OUT, report)
prefix = '' if args.phase == 'fresh' else 'existing-'


def wait(expression, timeout=30):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def theme(name):
    ui.js(f"(async()=>{{await lal.setAppearance('{name}');await frame();return true}})()")


def step(name):
    ui.js(f"(async()=>{{lal.goToSetupStep({STEPS.index(name)});await until(()=>$('setup-wizard').dataset.step==='{name}');await frame();return true}})()")


def shoot(label):
    for name in ('light', 'dark'):
        theme(name)
        ui.capture(f'{prefix}{label}-{name}.png')
    theme('light')


def fresh():
    from test_engines import server
    ui.wait_ready()
    wait("$('setup-wizard')&&lal.state.setup.env&&$('setup-environment')")
    ui.check('opens_by_itself_on_a_fresh_install', """(async()=>({auto:lal.state.setup.info.auto_open,
      dialog:$('setup-wizard').getAttribute('role')==='dialog'&&$('setup-wizard').getAttribute('aria-modal')==='true',
      inert:$('nav-settings').closest('[inert]')!==null,
      noBlenderRun:true, focus:document.activeElement===$('setup-step-title'),
      twoPaths:!!$('setup-agent-start')&&!!$('setup-manual')&&!$('setup-next'), noSessionYet:!lal.state.setup.agentMode}))()""")
    assert not probes, probes  # Opening setup ran no program (Blender only runs on Check).
    assert not (FIXTURE / 'data/library/settings.json').exists()
    shoot('00-welcome')
    ui.js("$('setup-manual').click()")
    wait("$('setup-wizard').dataset.step==='blender'&&lal.state.setup.blender")
    ui.check('focus_moves_to_each_step_title', "document.activeElement===$('setup-step-title')")
    fake = FIXTURE / ('blender.exe' if os.name == 'nt' else 'blender')
    fake.write_bytes(b'not a program')
    ui.js(f"(async()=>{{lal.updateSetupDraft({{blenderPath:{json.dumps(str(fake))}}});await frame();$('setup-check-blender').click();return true}})()")
    wait("lal.state.setup.check&&!lal.state.setup.checking", 120)
    ui.check('bad_blender_fails_with_reasons', """(async()=>({failed:lal.state.setup.check.status==='failed',
      shown:$('setup-blender-checks').querySelector('[data-status=failed]')!==null}))()""")
    shoot('01-blender-failed')
    found = ui.js("lal.state.setup.blender.candidates.map(c=>c.path)")
    report['checks']['blender_candidates'] = found
    if found:
        ui.js(f"(async()=>{{lal.updateSetupDraft({{blenderPath:{json.dumps(found[0])}}});await frame();$('setup-check-blender').click();return true}})()")
        wait("lal.state.setup.check&&!lal.state.setup.checking&&lal.state.setup.check.path===lal.state.setup.draft.blenderPath", 180)
        ui.check('discovered_blender_passes_and_will_be_saved', """(async()=>({passed:['passed','warning'].includes(lal.state.setup.check.status),
          checks:lal.state.setup.check.checks.length===4, write:lal.state.setup.check.change==='write'}))()""")
        shoot('01-blender-ready')
    # Arrow keys move within a radio-card group, like native radios.
    ui.js("(async()=>{lal.setupNext();await until(()=>$('setup-wizard').dataset.step==='formats');await frame();"
          "const first=$('setup-engine-hint').querySelector('[data-value=godot]');first.click();await frame();return true})()")
    ui.check('engine_hint_preselects_formats', """(async()=>({formats:lal.state.setup.draft.formats.join()==='gltf',
      reason:$('setup-hint-reason').textContent.includes('Godot’s recommended'),
      boxes:$('setup-format-gltf').getAttribute('aria-checked')==='true'&&$('setup-format-fbx').getAttribute('aria-checked')==='false'}))()""")
    ui.js("(async()=>{$('setup-engine-hint').querySelector('[data-value=unsure]').click();await frame();return true})()")
    ui.check('not_sure_selects_every_format', "lal.state.setup.draft.formats.join()==='fbx,gltf,obj'")
    shoot('02-formats')
    ui.js("(async()=>{$('setup-skip-step').click();await until(()=>$('setup-wizard').dataset.step==='storage');await frame();return true})()")
    ui.check('skip_step_is_recorded', "lal.state.setup.draft.skipped.includes('formats')")
    ui.js("(async()=>{$('setup-back').click();await until(()=>$('setup-wizard').dataset.step==='formats');lal.setupNext();"
          "await until(()=>$('setup-wizard').dataset.step==='storage');return true})()")
    ui.check('next_after_back_unskips', "!lal.state.setup.draft.skipped.includes('formats')")
    ui.js("$('setup-measure-storage').click()")
    wait("lal.state.setup.storage&&!lal.state.setup.measuring&&lal.state.setup.storage.status!=='receipt'", 120)
    ui.check('measure_now_reads_current_use', "lal.state.setup.storage.status==='measured'")
    ui.js("(async()=>{$('setup-budget-presets').querySelector('button').click();await frame();return true})()")
    ui.check('budget_recommendation_from_measured_use', """(async()=>({measured:lal.state.setup.storage.allocated_gib>=0,
      recommended:lal.state.setup.draft.budget===String(lal.state.setup.storage.recommended.gib),
      text:document.body.innerText.includes('current use plus 20 GiB')}))()""")
    shoot('03-storage')
    ui.js("(async()=>{lal.setupNext();await until(()=>$('setup-wizard').dataset.step==='descriptions');await frame();return true})()")
    wait("$('setup-readiness')")
    # Search has its own card and checklist since decision 0018 (GPU or CPU; the CPU list has no GPU item).
    ui.check('builtin_readiness_lists_copyable_commands', """(async()=>({items:$('setup-readiness').querySelectorAll('li').length===3,
      search:[3,4].includes($('setup-search-readiness').querySelectorAll('li').length)&&$('setup-search-device').querySelectorAll('[role=radio]').length===2,
      model:document.body.innerText.includes('Qwen3-VL-2B-Instruct'), honest:document.body.innerText.includes('on an NVIDIA GPU or on the CPU')}))()""")
    shoot('04-descriptions-builtin')
    ui.js("""(async()=>{const group=$('setup-engine');const first=group.querySelector('[role=radio]');first.focus();
      first.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));await frame();return true})()""")
    ui.check('arrow_keys_choose_engine', "lal.state.setup.draft.engine==='local-server'&&document.activeElement.dataset.value==='local-server'")
    with server() as url:
        ui.js(f"(async()=>{{type('setup-server-url',{json.dumps(url)});type('setup-server-model','');await frame();$('setup-test-server').click();"
              "await until(()=>$('setup-server-result').textContent.startsWith('Connected'));await frame();return true})()")
        ui.js("(async()=>{[...document.querySelectorAll('button')].find(b=>b.textContent==='Use “synthetic-vision”').click();await frame();return true})()")
        ui.check('test_connection_lists_models_without_generating', """(async()=>({model:lal.state.setup.draft.serverModel==='synthetic-vision',
          url:lal.state.setup.draft.serverUrl.startsWith('http://127.0.0.1:')}))()""")
        from test_engines import FakeServer
        assert FakeServer.requests == []
        shoot('04-descriptions-server')
        ui.js("(async()=>{type('setup-server-url','http://192.168.1.5:8080/v1');await frame();$('setup-test-server').click();"
              "await until(()=>$('setup-server-result').classList.contains('text-fault'));return true})()")
        ui.check('other_computers_are_refused', "$('setup-server-result').textContent.includes('this computer')")
        ui.js(f"(async()=>{{type('setup-server-url',{json.dumps(url)});await frame();lal.setupNext();"
              "await until(()=>$('setup-wizard').dataset.step==='review');await frame();return true})()")
        ui.check('batch_step_not_needed_for_a_server', """(async()=>({skippedOver:$('setup-wizard').dataset.step==='review',
          listed:document.querySelector('nav [data-step=batch]').textContent.includes('Not needed')}))()""")
        shoot('06-review-server')
    ui.js("(async()=>{lal.goToSetupStep(4);await until(()=>$('setup-engine'));$('setup-engine').querySelector('[data-value=builtin]').click();"
          "lal.setupNext();await until(()=>$('setup-wizard').dataset.step==='batch');await frame();return true})()")
    ui.check('batch_step_offers_benchmark_and_recommendation', """(async()=>({rows:$('setup-batch').querySelectorAll('[role=radio]').length===4,
      measured:document.body.innerText.includes('RTX 5070 (12 GiB)')}))()""")
    ui.js("(async()=>{$('setup-batch').querySelector('[data-value=\"4\"]').click();await frame();return true})()")
    shoot('05-batch')
    ui.js("(async()=>{lal.setupNext();await until(()=>$('setup-wizard').dataset.step==='review');await frame();return true})()")
    shoot('06-review')
    assert not (FIXTURE / 'data/library/settings.json').exists()  # Nothing is saved before Save.
    ui.js("$('setup-save').click()")
    wait("lal.state.setup.result&&$('setup-saved-title')", 60)
    settings = json.loads((FIXTURE / 'data/library/settings.json').read_text(encoding='utf-8'))
    record = json.loads((FIXTURE / 'data/library/setup.json').read_text(encoding='utf-8'))
    assert settings['processing_formats'] == ['fbx', 'gltf', 'obj'] and settings['caption_batch_size'] == 4
    assert settings['description_engine'] == 'builtin' and settings['descriptions_enabled'] is True
    assert record['state'] == 'completed' and record['by'] == 'user' and record['values']['caption_batch_size']['set_by'] == 'user'
    if found:  # A discovered Blender is saved: the speed test and render pool use the saved one only.
        assert setup_core.configured_blender(config)[1] == found[0] and record['values']['blender']['set_by'] == 'user'
        ui.check('saved_blender_is_reported', "$('setup-blender-result').textContent.includes('saved to config.local.toml')")
    else:
        assert not (FIXTURE / 'config.local.toml').exists()
    report['checks']['save_writes_settings_setup_record_and_blender'] = True
    shoot('07-saved')
    ui.js("(async()=>{$('setup-go-sources').click();await until(()=>!$('setup-wizard')&&$('sources-view'));return true})()")
    ui.check('next_step_opens_asset_sources', "$('nav-sources').closest('[inert]')===null&&$('nav-sources').getAttribute('aria-current')==='page'")
    if found:  # The app was launched without a saved Blender; no restart is needed for the speed test.
        ui.js("(async()=>{lal.navigate({page:'settings',tab:'general'});await until(()=>$('blender-status')&&$('render-test-start')"
              "&&lal.state.render.values&&lal.state.render.values.blender);await frame();return true})()")
        ui.check('settings_shows_saved_blender_and_speed_test_is_available', """(async()=>({saved:$('blender-status').dataset.status==='Saved',
          path:$('blender-status').textContent.includes(%s), closed:!$('settings-blender-choice'),
          test:!$('render-test-start').disabled}))()""" % json.dumps(found[0]))
        ui.js("(async()=>{$('blender-card').scrollIntoView({block:'start'});await frame();return true})()")
        shoot('07b-settings-blender-saved')
        ui.js("(async()=>{$('change-blender').click();await until(()=>$('settings-blender-choice'));await frame();return true})()")
        ui.check('change_blender_opens_the_picker_with_a_way_back', "!!$('keep-blender')&&!$('change-blender')")
        ui.js("(async()=>{$('keep-blender').click();await until(()=>!$('settings-blender-choice'));return true})()")
    ui.js("(async()=>{await lal.loadSetupState();return true})()")
    ui.check('does_not_reopen_after_saving', "lal.state.setup.info.auto_open===false")
    ui.js("(async()=>{await lal.openSetup();await until(()=>$('setup-skip-all'));$('setup-skip-all').click();await until(()=>!$('setup-wizard'));return true})()")
    assert json.loads((FIXTURE / 'data/library/setup.json').read_text(encoding='utf-8'))['state'] == 'skipped'
    assert json.loads((FIXTURE / 'data/library/settings.json').read_text(encoding='utf-8')) == settings
    report['checks']['skip_setup_records_a_skip_and_keeps_settings'] = True
    window.resize(680, 820)
    ui.js("(async()=>{await lal.openSetup();await until(()=>$('setup-environment'));return true})()")
    ui.check('narrow_window_has_no_horizontal_scroll', "innerWidth<761&&document.querySelector('#setup-wizard main').scrollWidth<=document.querySelector('#setup-wizard main').clientWidth+1")
    shoot('08-welcome-narrow')
    ui.js("(async()=>{lal.closeSetup();return true})()")


def existing():
    ui.wait_ready(extra='lal.state.sources.length===2')
    ui.js("(async()=>{await lal.loadSetupState();await frame();return true})()")
    ui.check('existing_install_is_not_interrupted', "!$('setup-wizard')&&lal.state.setup.info.auto_open===false")
    ui.js("(async()=>{$('nav-settings').click();await until(()=>$('setup-card')&&$('descriptions-card')&&lal.state.general.values&&$('blender-status'));await frame();return true})()")
    ui.check('settings_explains_missing_blender_with_the_picker_open', """(async()=>({missing:$('blender-status').dataset.status==='Missing',
      explained:$('blender-card').textContent.includes('no longer exists'), picker:!!$('settings-blender-choice')&&!!$('settings-check-blender'),
      noKeep:!$('keep-blender')}))()""")
    shoot('10-settings-general')
    ui.js("(async()=>{$('blender-card').scrollIntoView({block:'start'});await frame();return true})()")
    shoot('10b-settings-blender-missing')
    ui.js("(async()=>{$('run-setup').click();await until(()=>$('setup-wizard')&&!lal.state.setup.loading);return true})()")
    ui.check('run_setup_prefills_current_values', """(async()=>({budget:lal.state.setup.draft.budget==='40',
      formats:lal.state.setup.draft.formats.join()==='gltf,obj', batch:lal.state.setup.draft.batch==='4'}))()""")
    step('blender')
    wait("lal.state.setup.blender")
    ui.check('missing_configured_blender_is_explained', "document.body.innerText.includes('no longer exists')")
    found = ui.js("lal.state.setup.blender.candidates.filter(c=>!c.origin.startsWith('configured')).map(c=>c.path)")
    if found:
        ui.js(f"(async()=>{{lal.updateSetupDraft({{blenderPath:{json.dumps(found[0])}}});await frame();$('setup-check-blender').click();return true}})()")
        wait("lal.state.setup.check&&!lal.state.setup.checking", 180)
        ui.check('changing_blender_asks_to_confirm_rerendering', """(async()=>({write:lal.state.setup.check.change==='write',
          count:lal.state.setup.check.rerender>0, confirm:!!$('setup-confirm-rerender')}))()""")
        shoot('11-blender-rerender')
        step('review')
        ui.js("$('setup-save').click()")
        wait("lal.state.setup.error&&lal.state.setup.error.includes('rendered again')")
        report['checks']['unconfirmed_rerender_is_refused'] = True
        step('blender')
        ui.js("(async()=>{await until(()=>$('setup-confirm-rerender'));$('setup-confirm-rerender').click();await frame();return true})()")
    step('descriptions')
    ui.js("(async()=>{document.querySelector('#setup-wizard [role=switch]').click();await frame();return true})()")
    ui.check('descriptions_off_explains_what_is_kept', "$('setup-descriptions-off').textContent.includes('stay stored and searchable')")
    shoot('12-descriptions-off')
    step('review')
    ui.js("$('setup-save').click()")
    wait("lal.state.setup.result", 60)
    if found:
        assert setup_core.configured_blender(config)[1] == found[0]
        report['checks']['confirmed_blender_saved_to_config_local'] = True
        wait("lal.state.blender.report&&lal.state.blender.report.configured===%s" % json.dumps(found[0]))
        ui.check('settings_card_follows_the_wizard_save', "!lal.state.blender.editing&&lal.state.blender.path===%s" % json.dumps(found[0]))
    ui.js("(async()=>{$('setup-close').click();await until(()=>!$('setup-wizard'));$('nav-processing').click();"
          "await until(()=>$('processing-view')&&lal.state.queue);await frame();return true})()")
    one = ui.js("lal.state.sources[0].key")
    # Descriptions off (decision 0008): nothing offers Generate descriptions, and the queue refuses it with the reason.
    queued = ui.js(f"lal.state.api.queue_add('descriptions',{{key:{json.dumps(one)}}},false)")
    assert queued['status'] == 'faulty' and 'turned off' in queued['reason'], queued
    ui.check('descriptions_off_removes_generate_descriptions', "!document.querySelector('[data-action=describe]')")
    refused = bridge.source_action('describe', one)
    assert refused['status'] == 'faulty' and 'turned off' in refused['reason'], refused
    report['checks']['backend_refuses_describe_when_off'] = True
    shoot('13-processing-descriptions-off')


def verify():
    try:
        fresh() if args.phase == 'fresh' else existing()
        assert not bridge._gateway.model_requested
        report['programs_run_by_setup'] = probes
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture(prefix + 'failure.png')
        except Exception:
            pass
    finally:
        atomic_json(OUT / f'report-{args.phase}.json', report)
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
if args.phase == 'fresh':
    child = subprocess.run([sys.executable, __file__, '--run-name', args.run_name, '--phase', 'existing'])
    phases = {phase: json.loads((OUT / f'report-{phase}.json').read_text(encoding='utf-8')) for phase in ('fresh', 'existing')}
    summary = {'status': 'passed' if all(p['status'] == 'passed' for p in phases.values()) else 'faulty',
               'phases': {k: {'status': v['status'], 'reason': v.get('reason'), 'checks': len(v['checks'])} for k, v in phases.items()},
               'screenshots': sum((v['screenshots'] for v in phases.values()), []), 'owner_visual_review': 'pending'}
    atomic_json(OUT / 'report.json', summary)
    print(json.dumps(summary, indent=2))
    raise SystemExit(summary['status'] != 'passed')
print(json.dumps({k: report[k] for k in ('status', 'phase')} | {'reason': report.get('reason')}))
