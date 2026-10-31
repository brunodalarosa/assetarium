"""Verify Check my model (decision 0024) in the real WebView2 shell against a fake local model server.

The fake server (tests/test_engines.FakeServer, loopback only) lists one model and answers every request with text
and no tool calls, like a model that does nothing. Checks List models, the running progress, the verdict (only the
families that need no change pass: 2 of 8, "Not recommended"), the saved report, the narrow layout and that the
owner's library is untouched. Writes data/gui/<run-name>/verification.json.
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
from test_engines import server  # noqa: E402
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
before = sorted(str(p) for p in Path(one['path']).rglob('*'))


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)
CARD = "$('model-check-card')"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        with server() as url:
            ui.wait_ready()
            ui.js("$('nav-settings').click()")
            wait(f"{CARD}&&$('model-check-url')")
            ui.js(f"(async()=>{{type('model-check-url',{json.dumps(url)});await frame();"
                  f"[...{CARD}.querySelectorAll('button')].find(b=>b.textContent.includes('List models')).click();return true}})()")
            wait("$('model-check-model')&&$('model-check-start')&&!$('model-check-start').disabled", 30)
            report['checks'].append('List models reads the server and enables Check my model')
            ui.js(f"{CARD}.scrollIntoView();$('model-check-start').click()")
            wait("lal.state.modelCheck&&lal.state.modelCheck.running", 30)
            report['checks'].append('The check runs in the background with progress')
            wait("$('model-check-result')&&!lal.state.modelCheck.running", 300)
            result = ui.js("({text:$('model-check-result').textContent,verdict:$('model-check-result').dataset.verdict})")
            assert result['verdict'] == 'weak' and '2/8' in result['text'] and 'Not recommended' in result['text'], result
            ui.js(f"{CARD}.scrollIntoView()")
            ui.capture('01-result.png')
            report['checks'].append('A model that does nothing scores 2/8 ("Not recommended"): only the packs that were fine pass')
            saved = sorted((config.project_root / 'data/evidence/model-check').glob('*.json'))
            assert len(saved) == 2 and not (config.project_root / 'scratch/model-check').exists() or not any(
                (config.project_root / 'scratch/model-check').iterdir())
            report['checks'].append('The report and transcripts are saved; the disposable library is removed')
            window.resize(680, 900)
            wait('innerWidth<761')
            wait(f"{CARD}.getBoundingClientRect().right<=innerWidth+1", 10)
            ui.capture('02-narrow.png')
            report['checks'].append('The card fits the narrow window')
        assert sorted(str(p) for p in Path(one['path']).rglob('*')) == before
        assert not bridge._gateway.model_requested
        report['checks'].append("The owner's library folders are untouched; no embedding model was loaded")
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        atomic_json(OUT / 'verification.json', report)
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(dict(report, report=str(OUT / 'verification.json')), indent=2))
raise SystemExit(report['status'] != 'passed')
