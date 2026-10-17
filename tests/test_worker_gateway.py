"""The embedding worker only returns vectors; ranking stays in the caller (decision 0005)."""
import asyncio
import sys

import pytest

from test_retrieval import indexed  # noqa: F401  (fixture)
from local_asset_library import mcp_server
from local_asset_library.desktop import DesktopBridge
from local_asset_library.mcp_assets import AssetService, TransientFault
from local_asset_library.mcp_server import Gateway


def synthetic_embed(backend, requests):
    async def embed(request):
        requests.append(request['op'])
        if request['op'] == 'contract':
            return {'contract': backend.contract}
        vector = backend.text(request['text'], role=request['role']) if request['op'] == 'text' else backend.image(request['path'])
        return {'vector': [float(x) for x in vector], 'metrics': {'synthetic': True}, 'contract': backend.contract}
    return embed


def test_semantic_search_ranks_in_process_with_worker_query_vectors(indexed):
    config, backend, _ = indexed
    bridge = DesktopBridge(config, prestart_worker=False)
    requests = []
    try:
        bridge._gateway.embed = synthetic_embed(backend, requests)
        response = bridge.search({'query': 'red object'})
        expected, _, _ = AssetService(config, backend=backend).execute('search_assets', response['arguments'])
        assert response['payload'] == expected and not response['is_error']
        assert requests == ['contract', 'text']  # One query vector; vectors and ranking stay local.
        bridge.search({'query': 'red object', 'mode': 'keyword'})
        assert requests == ['contract', 'text']  # Keyword search never contacts the worker.
        bridge.search({'query': 'another object'})
        assert requests == ['contract', 'text', 'text']
    finally:
        bridge._close()


def test_busy_queue_is_not_retained_as_a_query_fault(indexed):
    config, backend, _ = indexed
    bridge = DesktopBridge(config, prestart_worker=False)
    requests, busy = [], [True]
    real = synthetic_embed(backend, requests)
    async def embed(request):
        if request['op'] == 'text' and busy[0]:
            raise TransientFault('Inference queue busy with an owned batch')
        return await real(request)
    try:
        bridge._gateway.embed = embed
        first = bridge.search({'query': 'red object'})
        assert first['is_error'] and 'queue busy' in first['payload']['reason']
        busy[0] = False
        second = bridge.search({'query': 'red object'})
        assert not second['is_error'] and second['payload']['results']
    finally:
        bridge._close()


FAKE_WORKER = r'''
import json, sys, time
print(json.dumps({"event": "ready"}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    if request["op"] == "contract":
        print(json.dumps({"result": {"contract": {"fake": 1}}, "is_error": False}), flush=True)
        continue
    for _ in range(MODE):
        print(json.dumps({"event": "heartbeat"}), flush=True); time.sleep(0.3)
    if MODE == 0:
        time.sleep(30)
    print(json.dumps({"result": {"vector": [1.0], "contract": {"fake": 1}}, "is_error": False}), flush=True)
'''


@pytest.mark.parametrize('mode', [6, 0])
def test_heartbeats_keep_slow_loads_alive_and_silence_faults(indexed, monkeypatch, mode):
    config, _, _ = indexed
    monkeypatch.setattr(mcp_server, 'WORKER_SILENCE_SECONDS', 1)
    gateway = Gateway(config)
    async def start_worker():
        gateway.loop = asyncio.get_running_loop()
        if gateway.worker and gateway.worker.returncode is None:
            return
        gateway.results = asyncio.Queue()
        gateway.worker = await asyncio.create_subprocess_exec(sys.executable, '-c', FAKE_WORKER.replace('MODE', str(mode)),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        asyncio.create_task(gateway._read_worker(gateway.worker, gateway.results))
    gateway.start_worker = start_worker
    async def run():
        assert (await gateway.embed({'op': 'contract'}))['contract'] == {'fake': 1}
        if mode:
            # 1.8 s of work with heartbeats survives a 1 s silence limit.
            assert (await gateway.embed({'op': 'text', 'text': 'x', 'role': 'query'}))['vector'] == [1.0]
            assert gateway.worker_fault is None and gateway.model_requested
        else:
            with pytest.raises(TransientFault, match='stopped responding'):
                await gateway.embed({'op': 'text', 'text': 'x', 'role': 'query'})
            assert gateway.worker_fault and gateway.worker_phase == 'faulty'
        await gateway.close()
    asyncio.run(run())
