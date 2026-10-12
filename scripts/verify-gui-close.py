"""Close an app-owned embedding worker during a pending first search; touch no other process."""
import asyncio
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.config import load_config
from local_asset_library.desktop import DesktopBridge

target = ROOT / 'data/gui/close-pending.json'
with target.open('x', encoding='utf-8') as stream:
    json.dump({'status': 'running'}, stream)
bridge = DesktopBridge(load_config(ROOT / 'config.example.toml', ROOT))
report = {'status': 'running', 'scope': 'One new app-owned pending search; no historical asset processing faults retried'}
try:
    future = asyncio.run_coroutine_threadsafe(bridge._search({'query': 'a small red apple with a leaf'}), bridge._loop)
    deadline = time.perf_counter() + 10
    while bridge._gateway.worker is None and time.perf_counter() < deadline:
        time.sleep(.025)
    assert bridge._gateway.worker is not None
    report['owned_worker_pid'] = bridge._gateway.worker.pid
    started = time.perf_counter()
    bridge._close()
    report['close_seconds'] = time.perf_counter() - started
    report['lifecycle'] = json.loads((bridge._gateway.audit_root / 'lifecycle.json').read_text())
    assert not bridge._thread.is_alive()
    assert report['lifecycle']['closed'] and report['lifecycle']['worker_returncode'] is not None
    assert future.done()
    report['status'] = 'passed'
except Exception as exc:
    report.update(status='faulty', reason=str(exc))
finally:
    bridge._close()
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
sys.exit(report['status'] != 'passed')
