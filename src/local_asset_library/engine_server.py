"""Experimental description engine adapter: a local OpenAI-compatible model server.

Assetarium never starts, installs or downloads the server. Only addresses on this
computer are accepted, proxies are bypassed, and one asset is sent per request.
The model identity is what the server reports, not a hash-verified file
(decision 0015). Server faults (unreachable, unknown model, refused request,
malformed reply) stop the run with the assets pending; a timed-out or truncated
generation fails only its asset, like the built-in engine's time limit.
"""
import base64
import io
import ipaddress
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .caption_backend import prepare_images
from .config import ConfigError
from .description_engines import EngineUnavailableError

MODE = 'server-v1'
POLICY = 'single-request-no-fault-retry-v1'
SETTINGS = {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'repeat_penalty': 1.1, 'seed': 0,
            'max_time_seconds': 120, 'image_edge': 448, 'image_encoding': 'png-base64',
            'preprocessing': 'rgba-gray-composite-rgb-lanczos-448-v1', 'assets_per_request': 1}
TIMEOUT = 125
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ADDRESS_HELP = 'Enter a server address on this computer, like http://127.0.0.1:8080/v1'


def checked_url(url):
    """Normalized base URL; refuses anything that is not a plain loopback http(s) address."""
    if not isinstance(url, str) or not url.strip() or len(url) > 300:
        raise ConfigError(ADDRESS_HELP)
    parsed = urllib.parse.urlsplit(url.strip())
    try:
        parsed.port
    except ValueError:
        raise ConfigError(ADDRESS_HELP) from None
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ConfigError(ADDRESS_HELP)
    try:
        local = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        local = parsed.hostname.lower() == 'localhost'
    if not local:
        raise ConfigError('Only a server on this computer is accepted (127.0.0.1, localhost or [::1])')
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', ''))


def checked_model(model):
    if not isinstance(model, str) or len(model) > 200 or any(ord(c) < 32 for c in model):
        raise ConfigError('Enter the model name the server lists (up to 200 characters)')
    return model.strip()


def _request(url, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'} if data else {})
    with OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read(64 * 1024 * 1024).decode('utf-8'))


def _reason(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f'HTTP {exc.code}'
    return str(getattr(exc, 'reason', None) or exc) or type(exc).__name__


def _models(url):
    value = _request(url + '/models')
    return [m for m in value.get('data', []) if isinstance(m, dict) and isinstance(m.get('id'), str)]


def probe(url, model=''):
    """List the server's models; never generates text. Used by setup's Test connection."""
    base = checked_url(url)
    try:
        models = _models(base)
    except (urllib.error.URLError, OSError, ValueError, AttributeError) as exc:
        return {'status': 'unreachable', 'url': base, 'reason': f'Could not reach the server at {base}: {_reason(exc)}'}
    names = [m['id'] for m in models][:50]
    model = checked_model(model or '')
    return {'status': 'connected', 'url': base, 'models': names,
            'model_found': (model in names) if model else None}


class ServerEngine:
    generation_mode = MODE
    settings = SETTINGS

    def __init__(self, config, url, model):
        self.config = config
        self.url = checked_url(url)
        model = checked_model(model or '')
        if not model:
            raise EngineUnavailableError('Choose the server model in Settings → General before generating descriptions')
        try:
            entry = next((m for m in _models(self.url) if m['id'] == model), None)
        except (urllib.error.URLError, OSError, ValueError, AttributeError) as exc:
            raise EngineUnavailableError(f'The local model server at {self.url} is not reachable ({_reason(exc)}). '
                                         'Start it, then generate descriptions again; nothing was recorded as failed.') from None
        if entry is None:
            raise EngineUnavailableError(f'The server at {self.url} does not list the model “{model}”')
        # Scalar facts only; "created" is a per-request timestamp on some servers, not identity.
        reported = {'model': {k: v for k, v in entry.items() if isinstance(v, (str, int, float, bool)) and k != 'created'}}
        try:  # llama.cpp also reports its model file and build; other servers simply lack /props.
            props = _request(self.url.removesuffix('/v1') + '/props', timeout=5)
            reported['props'] = {k: props[k] for k in ('model_path', 'build_info') if isinstance(props.get(k), str)}
        except (urllib.error.URLError, OSError, ValueError, AttributeError):
            pass
        self.identity = {'engine': 'local-server', 'model': model}
        self.contract = {'engine': 'local-server', 'backend': 'openai-compatible', 'url': self.url, 'model': model,
                         'identity': 'reported-by-server', 'reported': reported}
        self.requests = 0

    def generate_batch(self, inputs_list, prompt, max_new_tokens):
        results = []
        for inputs in inputs_list:
            try:
                results.append(self._one(inputs, prompt, max_new_tokens))
            except EngineUnavailableError:
                raise
            except Exception as exc:
                results.append(exc)
        return results

    def _one(self, inputs, prompt, max_new_tokens):
        images, processed = prepare_images(self.config, inputs)
        content = []
        for item, image in zip(inputs, images):
            buffer = io.BytesIO()
            image.save(buffer, 'PNG')
            content.extend([{'type': 'text', 'text': 'View: ' + item['view_label']},
                            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')}}])
        content.append({'type': 'text', 'text': prompt})
        payload = {'model': self.identity['model'], 'messages': [{'role': 'user', 'content': content}],
                   'max_tokens': max_new_tokens, 'temperature': 0.7, 'top_p': 0.8, 'top_k': 20,
                   'repeat_penalty': 1.1, 'seed': 0, 'stream': False}
        started = time.perf_counter()
        try:
            value = _request(self.url + '/chat/completions', payload, timeout=TIMEOUT)
        except urllib.error.HTTPError as exc:
            detail = exc.read(2000).decode('utf-8', 'replace').strip()
            raise EngineUnavailableError(f'The local model server refused the request (HTTP {exc.code}): {detail[:300]}') from None
        except TimeoutError:
            raise RuntimeError('Generation timed out or exhausted output token limit') from None
        except (urllib.error.URLError, OSError) as exc:
            raise EngineUnavailableError(f'Lost the connection to the local model server ({_reason(exc)})') from None
        except ValueError:
            raise EngineUnavailableError('The local model server returned a reply that is not JSON') from None
        choice = (value.get('choices') or [{}])[0] if isinstance(value, dict) else {}
        text = (choice.get('message') or {}).get('content') if isinstance(choice, dict) else None
        if not isinstance(text, str):
            raise EngineUnavailableError('The local model server replied without message text')
        if choice.get('finish_reason') == 'length':
            raise RuntimeError('Generation timed out or exhausted output token limit')
        self.requests += 1
        usage = value.get('usage') if isinstance(value.get('usage'), dict) else {}
        return text, {'elapsed_seconds': time.perf_counter() - started, 'input_tokens': usage.get('prompt_tokens'),
                      'generated_tokens': usage.get('completion_tokens'), 'processed_images': processed,
                      'max_new_tokens': max_new_tokens, 'server_model': value.get('model'), **self.resources()}

    def resources(self):
        return {'requests': self.requests}

    def close(self):
        pass
