"""Inference ports and adapters (decision 0015): contracts, composition root, the local server engine."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from local_asset_library import engines
from local_asset_library.config import ConfigError
from local_asset_library.description_engines import (DescriptionEngine, EngineStop, EngineUnavailableError,
                                                     MemoryLimitError)
from local_asset_library.engine_server import MODE, ServerEngine, checked_url, probe
from local_asset_library.incremental import caption_input, process, records, working
from local_asset_library.settings import save_general_settings
from test_captions import caption
from test_incremental import BatchBackend, library, pending_captions  # noqa: F401 (fixture)


class FakeServer(BaseHTTPRequestHandler):
    """A tiny OpenAI-compatible server; ``behaviour`` picks the reply."""
    behaviour, requests, models = 'ok', [], ['synthetic-vision']

    def log_message(self, *args):
        pass

    def reply(self, status, value):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/v1/models':
            return self.reply(200, {'data': [{'id': name, 'object': 'model'} for name in type(self).models]})
        if self.path == '/props':
            return self.reply(200, {'model_path': '/models/synthetic.gguf', 'build_info': 'b0000'})
        self.reply(404, {'error': 'not found'})

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).requests.append(payload)
        behaviour = type(self).behaviour
        if behaviour == 'refuse':
            return self.reply(400, {'error': 'image input is not supported by this model'})
        if behaviour == 'garbage':
            return self.reply(200, b'<html>not json</html>')
        text = json.dumps(caption())
        finish = 'length' if behaviour == 'truncated' else 'stop'
        self.reply(200, {'model': payload['model'], 'choices': [{'message': {'content': text}, 'finish_reason': finish}],
                         'usage': {'prompt_tokens': 900, 'completion_tokens': 120}})


@contextmanager
def server(behaviour='ok'):
    FakeServer.behaviour, FakeServer.requests = behaviour, []
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), FakeServer)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_address[1]}/v1'
    finally:
        httpd.shutdown()
        httpd.server_close()


def use_server(config, url, model='synthetic-vision'):
    save_general_settings(config, 8, None, None, True, 'local-server', {'url': url, 'model': model})


def test_only_loopback_http_addresses_are_accepted():
    assert checked_url(' http://127.0.0.1:8080/v1/ ') == 'http://127.0.0.1:8080/v1'
    assert checked_url('http://localhost:11434/v1') == 'http://localhost:11434/v1'
    assert checked_url('http://[::1]:1234/v1') == 'http://[::1]:1234/v1'
    for bad in ('http://192.168.1.20:8080/v1', 'https://api.example.com/v1', 'file:///etc/passwd', 'http://user:pw@127.0.0.1/v1',
                'http://127.0.0.1:99999/v1', 'http://127.0.0.1/v1?key=1', '', None):
        with pytest.raises(ConfigError):
            checked_url(bad)


def test_engine_table_and_port_contracts():
    assert set(engines.DESCRIPTION_ENGINES) == {'builtin', 'local-server'}
    assert engines.DESCRIPTION_ENGINES['local-server']['status'] == 'experimental'
    assert issubclass(MemoryLimitError, EngineStop) and issubclass(EngineUnavailableError, EngineStop)
    assert isinstance(BatchBackend([]), DescriptionEngine) is False  # Lacks generation_mode/close: not a full engine.


def test_composition_root_builds_the_configured_adapter(library, monkeypatch):
    config, _ = library
    built = []
    class Qwen:
        def __init__(self, scoped, contract):
            built.append(contract)
            self.contract, self.settings = {'model_id': 'synthetic'}, {'seed': 0}
    monkeypatch.setattr('local_asset_library.caption_backend.QwenBackend', Qwen)
    engine = engines.description_engine(config)
    assert type(engine).__name__ == 'TransformersQwenEngine' and isinstance(engine, DescriptionEngine)
    assert built == [{'revision': 'synthetic'}] and engine.contract is engine.backend.contract
    assert engines.batch_size(config) == 8 and engines.generation(config)[1] is None
    with server() as url:
        use_server(config, url)
        engine = engines.description_engine(config)
        assert isinstance(engine, ServerEngine) and isinstance(engine, DescriptionEngine)
        assert engine.contract['reported']['props'] == {'model_path': '/models/synthetic.gguf', 'build_info': 'b0000'}
        assert engines.batch_size(config) == 1
        assert engines.generation(config) == (MODE, {'engine': 'local-server', 'model': 'synthetic-vision'})


def test_probe_lists_models_and_never_generates():
    with server() as url:
        assert probe(url, 'missing') == {'status': 'connected', 'url': url, 'models': ['synthetic-vision'], 'model_found': False}
        assert FakeServer.requests == []
    result = probe(url)
    assert result['status'] == 'unreachable' and 'Could not reach' in result['reason']


def test_server_engine_stops_on_server_faults_and_fails_only_truncated_assets(library, monkeypatch):
    config, _ = library
    work = pending_captions(config)
    inputs = [__import__('local_asset_library.captions', fromlist=['image_inputs']).image_inputs(work, r) for r in records(work)[:2]]
    monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:9')  # Proxies are bypassed for loopback servers.
    with server() as url:
        engine = ServerEngine(work, url, 'synthetic-vision')
        results = engine.generate_batch(inputs, 'prompt', 1100)
        assert all(isinstance(r, tuple) and json.loads(r[0]) for r in results)
        sent = FakeServer.requests[0]
        assert sent['model'] == 'synthetic-vision' and sent['max_tokens'] == 1100 and sent['seed'] == 0
        images = [part for part in sent['messages'][0]['content'] if part['type'] == 'image_url']
        assert images and images[0]['image_url']['url'].startswith('data:image/png;base64,')
        FakeServer.behaviour = 'truncated'
        assert all(isinstance(r, RuntimeError) for r in engine.generate_batch(inputs, 'prompt', 1100))
        for behaviour in ('refuse', 'garbage'):
            FakeServer.behaviour = behaviour
            with pytest.raises(EngineUnavailableError):
                engine.generate_batch(inputs, 'prompt', 1100)
        with pytest.raises(EngineUnavailableError, match='does not list'):
            ServerEngine(work, url, 'another-model')
    with pytest.raises(EngineUnavailableError, match='not reachable'):
        ServerEngine(work, url, 'synthetic-vision')


def test_server_descriptions_record_their_engine_and_switching_redoes_nothing(library):
    config, _ = library
    work = pending_captions(config)
    builtin_pending = {r['asset_id']: caption_input(work, r) for r in records(work)}
    with server() as url:
        use_server(config, url)
        # Pending work follows the configured engine.
        assert all(caption_input(work, r) != builtin_pending[r['asset_id']] for r in records(work))
        engine = engines.description_engine(config)
        result = process(config, 'caption', 6, backend=engine)
        assert result['complete'] == 6 and len(FakeServer.requests) == 6  # One asset per request.
    done = records(work)
    assert all(r['caption_provenance']['generation_mode'] == MODE and
               r['caption_provenance']['engine'] == {'engine': 'local-server', 'model': 'synthetic-vision'}
               and r['caption_provenance']['batch']['size'] == 1 for r in done)
    save_general_settings(config, 8, None, None, True, 'builtin', None)
    assert process(config, 'caption', 6, dry_run=True)['pending'] == 0  # Finished work keeps its own engine.
    use_server(config, 'http://127.0.0.1:1/v1', 'another-model')
    assert process(config, 'caption', 6, dry_run=True)['pending'] == 0


def test_unreachable_server_leaves_assets_pending_with_no_failures(library):
    config, _ = library
    work = pending_captions(config)
    with server() as url:
        use_server(config, url)
        engine = engines.description_engine(config)
    with pytest.raises(EngineUnavailableError):
        process(config, 'caption', 6, backend=engine)
    assert all(r['processing']['caption'] == 'pending' for r in records(work))


def test_builtin_fingerprints_are_unchanged_by_the_engine_layer(library):
    config, _ = library
    work = pending_captions(config)
    from local_asset_library.caption_batching import MODE as BATCHED
    for record in records(work):
        assert caption_input(work, record) == caption_input(work, record, generation=BATCHED)
    save_general_settings(config, 8, None, 4)
    backend = BatchBackend([json.dumps(caption())] * 6)
    process(config, 'caption', 6, backend=backend)
    assert all(r['caption_provenance']['generation_mode'] == BATCHED and 'engine' not in r['caption_provenance']
               for r in records(working(config)))


def test_readiness_is_static(library):
    config, _ = library
    report = engines.readiness(config, 'builtin', {'nvidia': [{'name': 'x', 'vram_gib': 12, 'compute_capability': 7.5}]})
    gpu = report['items'][0]
    assert gpu['ready'] is False and 'BF16' in gpu['label']
    assert engines.readiness(config, 'builtin', {'nvidia': [{'compute_capability': 8.6}]})['items'][0]['ready']
    with pytest.raises(ConfigError):
        engines.readiness(config, 'cloud')
