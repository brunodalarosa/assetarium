"""Windows desktop shell. All UI resources are bundled; worker inference stays offline."""
import asyncio
from concurrent.futures import TimeoutError as FutureTimeout
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

from .catalog import encoded
from .config import ConfigError, load_project_config
from .desktop_service import DesktopService
from .mcp_assets import error_payload, validate
from .mcp_server import Gateway
from .search_policy import DEFAULT_MODE


class DesktopBridge:
    """pywebview dispatches API calls on threads; one loop owns the private gateway."""
    def __init__(self, config, prestart_worker=True):
        self._config = config
        self._prestart_worker = prestart_worker
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._presentation_lock = threading.Lock()
        self._closed = False
        self._owned_source_operations = set()
        self._thread = threading.Thread(target=self._run, name='asset-gateway', daemon=True)
        self._thread.start()
        if not self._ready.wait(10):
            raise ConfigError('Desktop gateway initialization timed out')
        if hasattr(self, '_init_error'):
            raise ConfigError(self._init_error)

    def _run(self):
        asyncio.set_event_loop(self._loop)
        try:
            log = self._config.output_path('logs', 'gui-worker.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            self._diagnostics = log.open('a', encoding='utf-8')
            self._gateway = Gateway(self._config, audit_namespace='gui', diagnostic_stream=self._diagnostics,
                subprocess_flags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if self._config.sources_registry and not self._config.output_path('data','catalog.sqlite').exists():
                from .sources import aggregate
                aggregate(self._config)
            self._service = DesktopService(self._config)
            from .interactive_preview import InteractivePreviewService
            self._interactive_preview = InteractivePreviewService(self._service)
            from .source_browser import SourceBrowser
            self._source_browser = SourceBrowser(self._config, self._interactive_preview)
            self._gateway.attach(self._service)
        except Exception as exc:
            self._init_error = str(exc)
            self._ready.set()
            return
        if self._prestart_worker:
            # Libraries only (decision 0005); the model still loads on the first semantic search.
            self._loop.call_soon(lambda: self._loop.create_task(self._gateway.prestart()))
        self._ready.set()
        self._loop.run_forever()
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self._loop.run_until_complete(self._loop.shutdown_default_executor())
        self._loop.close()
        self._diagnostics.close()

    def _wait(self, coroutine):
        if self._closed:
            coroutine.close()
            return {'status': 'faulty', 'reason': 'App is closing; request not executed'}
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=110)
        except Exception as exc:
            if isinstance(exc, FutureTimeout):
                future.cancel()
            payload = error_payload(exc)
            with (self._gateway.audit_root / 'desktop-faults.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(encoded(payload) + '\n')
            return {'status': 'faulty', 'reason': payload['reason'], 'payload': payload}

    async def _present(self, operation, *args, guarded=True):
        started = time.perf_counter()
        # Source/detail work is independent of the serialized GPU search queue. The lock
        # protects DesktopService state only; settings, sources and change polls skip it.
        try:
            def run():
                if not guarded:
                    return operation(*args)
                with self._presentation_lock:
                    return operation(*args)
            result = await asyncio.to_thread(run)
        except Exception as exc:
            result = {'status': 'faulty', 'reason': str(exc)}
        audit = {'operation': operation.__name__, 'elapsed_seconds': time.perf_counter() - started,
                 'status': result.get('status', result.get('payload', {}).get('status')),
                 'asset_id': args[0] if operation.__name__ == 'asset' else None,
                 'reason': result.get('reason'),
                 'faults': result.get('faults', result.get('evidence'))}
        with (self._gateway.audit_root / 'desktop.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(encoded(audit) + '\n')
        return result

    def context(self):
        return self._wait(self._present(self._service.context))

    def sources(self):
        return self._wait(self._present(self._sources, guarded=False))

    def general_settings(self):
        from .settings import general_settings
        return self._wait(self._present(general_settings, self._config, guarded=False))

    def save_general_settings(self, storage_budget_gib, processing_formats=None):
        from .settings import save_general_settings
        return self._wait(self._present(save_general_settings, self._config, storage_budget_gib, processing_formats, guarded=False))

    def importing_failures(self):
        from .sources import importing_failures
        return self._wait(self._present(importing_failures, self._config, guarded=False))

    def _sources(self):
        from .sources import registry, source_status, revision
        from .source_operations import operation_status
        return {'status': 'ready', 'sources': [source_status(self._config, s) for s in registry(self._config)['sources']],
                'revision': revision(self._config), 'scan': operation_status(self._config)}

    def source_action(self, action, key=None, directory=None, enabled=None):
        if not self._config.sources_registry:
            return {'status': 'faulty', 'reason': 'Configure asset sources before using source settings'}
        return self._wait(self._present(self._source_action, action, key, directory, enabled, guarded=False))

    def _source_action(self, action, key, directory, enabled):
        from . import sources
        from .source_operations import cancel
        if action == 'add':
            source = sources.add(self._config, directory)
            return self._start_source_operation('scan', source['key'])
        if action == 'enabled':
            source = sources.set_enabled(self._config, key, enabled)
            if enabled:
                self._start_source_operation('scan', key)
            return {'status': 'saved'}
        if action == 'remove':
            sources.remove(self._config, key)
            return {'status': 'saved'}
        if action == 'scan':
            return self._start_source_operation('scan', key)
        if action == 'process':
            return self._start_source_operation('process', key)
        if action == 'cancel':
            return cancel(sources.bound(self._config, sources.get_source(self._config, key)))
        raise ConfigError('Unknown asset source action')

    def _start_source_operation(self, operation, key):
        from .source_operations import start
        result = start(self._config, operation, key)
        if result.get('token'):
            self._owned_source_operations.add(result['token'])
        return result

    def choose_source_directory(self):
        import webview
        try:
            selected = self._window.create_file_dialog(webview.FileDialog.FOLDER)
            return {'status': 'selected', 'directory': selected[0]} if selected else {'status': 'cancelled'}
        except Exception as exc:
            return {'status': 'faulty', 'reason': str(exc)}

    def browse(self, filters=None, offset=0, page_size=40):
        return self._wait(self._present(self._service.browse, filters, offset, page_size))

    def source_browse(self, key, offset=0, page_size=40):
        return self._wait(self._present(self._source_browser.call, 'browse', key, offset, page_size))

    def source_asset(self, key, asset_id, source_format=None, preview_view='three_quarter', expected_version=None):
        return self._wait(self._present(self._source_browser.call, 'asset', key,
                                      asset_id, source_format, preview_view, expected_version))

    def source_thumbnail(self, key, asset_id, expected_version=None):
        return self._wait(self._present(self._source_browser.call, 'thumbnail', key, asset_id, expected_version))

    def source_preview_prepare(self, key, asset_id, source_format, expected_version):
        return self._wait(self._present(self._source_browser.call, 'prepare', key,
                                      asset_id, source_format, expected_version))

    def source_preview_file(self, key, ticket, index):
        return self._wait(self._present(self._source_browser.call, 'file', key, ticket, index))

    def source_preview_fault(self, key, ticket, reason, missing_files=None):
        return self._wait(self._present(self._source_browser.call, 'fault', key, ticket, reason, missing_files))

    def source_preview_release(self, key, ticket):
        return self._wait(self._present(self._source_browser.call, 'release', key, ticket))

    def asset(self, asset_id, source_format=None, preview_view='three_quarter', expected_version=None):
        return self._wait(self._present(self._service.asset, asset_id, source_format, preview_view, expected_version))

    def thumbnail(self, asset_id, expected_version=None):
        return self._wait(self._present(self._service.thumbnail, asset_id, expected_version))

    def preview_shell(self):
        from .interactive_preview import viewer_shell
        return viewer_shell()

    def preview_prepare(self, asset_id, source_format, expected_version):
        return self._wait(self._present(self._interactive_preview.prepare, asset_id, source_format, expected_version))

    def preview_file(self, ticket, index):
        return self._wait(self._present(self._interactive_preview.file, ticket, index))

    def preview_fault(self, ticket, reason, missing_files=None):
        return self._wait(self._present(self._interactive_preview.fault, ticket, reason, missing_files))

    def preview_release(self, ticket):
        return self._wait(self._present(self._interactive_preview.release, ticket))

    def changes(self):
        return self._wait(self._present(self._changes, guarded=False))

    def _changes(self):
        """Cheap stat-only tokens; views fetch heavy data only when a token changes."""
        from .catalog import digest
        def stamp(path):
            try:
                value = path.stat()
                return value.st_size, value.st_mtime_ns
            except FileNotFoundError:
                return None
        config = self._config
        library = [stamp(config.project_root / 'data/library/active.json'),
                   stamp(config.output_path('data', 'library/processing-status.json'))]
        sources = [stamp(config.output_path('data', 'library/source-operation.json')),
                   stamp(config.output_path('data', 'library/source-cancel.json'))]
        if config.sources_registry:
            from .sources import registry, bound, revision
            library.append(revision(config))
            sources.append(stamp(config.sources_registry))
            for source in registry(config)['sources']:
                scoped = bound(config, source)
                sources.append([stamp(scoped.output_path('data', 'library/' + name)) for name in
                                ('source-status.json', 'source-operation.json', 'source-cancel.json', 'active.json')]
                               + [stamp(config.project_root / 'data/library/source-faults' / (source['id'] + '.json'))])
        sources.append(stamp(config.project_root / 'data/library/settings.json'))
        return {'status': 'ready', 'library': digest(library)[:16], 'sources': digest(sources)[:16],
                'worker': self._gateway.worker_phase if hasattr(self, '_gateway') else 'not_started'}

    async def _search(self, arguments):
        validate('search_assets', arguments)
        arguments = dict(arguments)
        arguments.setdefault('mode', DEFAULT_MODE)
        arguments.setdefault('filters', {})
        arguments.setdefault('limit', 20)
        validate('search_assets', arguments)
        started = time.perf_counter()
        result = await self._gateway.call('search_assets', arguments)
        return {'payload': json.loads(result.content[0].text), 'arguments': arguments,
                'is_error': bool(result.model_dump(by_alias=True).get('isError', False)),
                'elapsed_seconds': time.perf_counter() - started}

    def search(self, settings):
        # Do not call a public bridge parameter "arguments": it shadows JavaScript's arguments object.
        return self._wait(self._search(settings))

    def copy_text(self, text):
        result = self._clipboard(text)
        if result['status'] == 'faulty':
            with (self._gateway.audit_root / 'desktop-faults.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(encoded({'item': 'clipboard', **result}) + '\n')
        return result

    def _clipboard(self, text):
        if type(text) is not str or len(text) > 16384:
            return {'status': 'faulty', 'reason': 'Clipboard text is invalid or too long'}
        # Explicit copy actions only; clipboard never reads originals or copies asset files.
        import ctypes
        from ctypes import wintypes
        user = ctypes.WinDLL('user32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        user.OpenClipboard.argtypes = [wintypes.HWND]
        user.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user.SetClipboardData.restype = wintypes.HANDLE
        kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel.GlobalAlloc.restype = wintypes.HANDLE
        kernel.GlobalLock.argtypes = [wintypes.HANDLE]
        kernel.GlobalLock.restype = ctypes.c_void_p
        kernel.GlobalUnlock.argtypes = [wintypes.HANDLE]
        kernel.GlobalFree.argtypes = [wintypes.HANDLE]
        kernel.GlobalFree.restype = wintypes.HANDLE
        data = (text + '\0').encode('utf-16-le')
        handle = kernel.GlobalAlloc(0x0002, len(data))
        if not handle:
            return {'status': 'faulty', 'reason': 'Clipboard allocation failed'}
        pointer = kernel.GlobalLock(handle)
        if not pointer:
            kernel.GlobalFree(handle)
            return {'status': 'faulty', 'reason': 'Clipboard allocation could not be locked'}
        ctypes.memmove(pointer, data, len(data))
        kernel.GlobalUnlock(handle)
        if not user.OpenClipboard(None):
            kernel.GlobalFree(handle)
            return {'status': 'faulty', 'reason': 'Clipboard is busy; no automatic retry'}
        try:
            user.EmptyClipboard()
            if not user.SetClipboardData(13, handle):
                kernel.GlobalFree(handle)
                return {'status': 'faulty', 'reason': 'Clipboard write failed'}
        finally:
            user.CloseClipboard()
        return {'status': 'copied'}

    def _close(self):
        if self._closed:
            return
        self._closed = True
        if self._config.sources_registry:
            from .sources import registry, bound
            from .source_operations import cancel, operation_status
            for source in registry(self._config)['sources']:
                scoped = bound(self._config, source)
                if operation_status(scoped).get('token') in self._owned_source_operations:
                    cancel(scoped)
            if operation_status(self._config).get('token') in self._owned_source_operations:
                cancel(self._config)
        future = asyncio.run_coroutine_threadsafe(self._gateway.close(), self._loop)
        try:
            future.result(timeout=15)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=15)


def create_window(config, bridge):
    """Shared shell construction for the normal launcher and real bridge verification."""
    import webview
    webview.settings.update({'ALLOW_DOWNLOADS': False, 'ALLOW_FILE_URLS': False,
        'OPEN_EXTERNAL_LINKS_IN_BROWSER': False, 'SHOW_DEFAULT_MENUS': False})
    ui = Path(__file__).resolve().parent / 'ui'
    html = (ui / 'index.html').read_text(encoding='utf-8')
    html = html.replace('/* BUNDLED_STYLE */', (ui / 'style.css').read_text(encoding='utf-8'))
    html = html.replace('/* BUNDLED_SCRIPT */', (ui / 'app.js').read_text(encoding='utf-8'))
    html = html.replace('/* INTERACTIVE_PREVIEW_SCRIPT */', (ui / 'interactive-preview.js').read_text(encoding='utf-8'))
    window = webview.create_window('Local Asset Library', html=html, js_api=bridge,
        width=1280, height=860, min_size=(640, 480), resizable=True, background_color='#f4f3ef')
    bridge._window = window
    return window


def profile_path(config, bridge, window):
    """One profile per owned window; review containment before renderer cleanup."""
    import webview
    profile = config.output_path('cache', 'gui-webview/' + bridge._gateway.run_id)
    expected_parent = config.output_path('cache', 'gui-webview')
    def review_cleanup():
        faults = []
        try:
            if profile.resolve().parent != expected_parent.resolve() or profile.is_symlink() or profile.is_junction():
                raise ConfigError('Browser profile is outside its owned session directory or is a link')
            for directory, dirs, files in os.walk(profile, followlinks=False):
                for name in dirs + files:
                    path = Path(directory) / name
                    if path.is_symlink() or path.is_junction():
                        faults.append(str(path.relative_to(profile)))
            if faults:
                raise ConfigError('Browser profile contains links; retained: ' + ', '.join(faults[:5]))
            result = {'status': 'passed', 'target': str(profile), 'contains_links': False,
                      'purpose': 'Only this window browser profile; no reports, previews or original assets'}
        except Exception as exc:
            # Pinned pywebview uses this setting to decide whether to remove its profile.
            # Retain the entire directory instead of allowing recursive deletion through links.
            webview._state['private_mode'] = False
            result = {'status': 'faulty', 'target': str(profile), 'reason': str(exc), 'retained': True}
        (bridge._gateway.audit_root / 'profile-cleanup-review.json').write_text(encoded(result) + '\n', encoding='utf-8')
    window.events.closing += review_cleanup
    return profile


def record_profile_outcome(bridge, profile):
    retained = profile.exists()
    outcome = {'status': 'faulty' if retained else 'passed', 'target': str(profile), 'retained': retained,
        'reason': 'Renderer left browser cache files; preserved without an automatic cleanup retry' if retained else None,
        'evidence': 'Renderer closing event reviewed containment; warnings remain in the app log when cleanup is locked',
        'scope': 'App-owned browser cache only; originals and asset results are outside this directory'}
    (bridge._gateway.audit_root / 'profile-cleanup-outcome.json').write_text(encoded(outcome) + '\n', encoding='utf-8')


def main():
    root = Path(__file__).resolve().parents[2]
    log_dir = root / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_dir / 'gui.log', level=logging.INFO, encoding='utf-8')
    bridge = None
    profile = None
    try:
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
            WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--force-renderer-accessibility',
            TEMP=str(root / 'scratch/tmp-mcp'), TMP=str(root / 'scratch/tmp-mcp'), PYTHONNET_RUNTIME='netfx')
        (root / 'scratch/tmp-mcp').mkdir(parents=True, exist_ok=True)
        config = load_project_config(root)
        bridge = DesktopBridge(config)
        import webview
        window = create_window(config, bridge)
        profile = profile_path(config, bridge, window)
        renderer_fault = []
        def verify_renderer():
            if webview.renderer != 'edgechromium':
                renderer_fault.append('Expected WebView2; no alternate renderer accepted')
                window.destroy()
        # Inline resources avoid a local HTTP listener. Shell profiles contain no evidence.
        webview.start(verify_renderer, gui='edgechromium', debug=False, private_mode=True,
            storage_path=str(profile))
        if renderer_fault:
            raise ConfigError(renderer_fault[0])
    except Exception as exc:
        logging.exception('Desktop startup/runtime fault')
        receipt = {'status': 'faulty', 'item': 'desktop runtime', 'reason': str(exc), 'traceback': traceback.format_exc()}
        folder = root / 'data/gui'
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / 'startup-faults.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(encoded(receipt) + '\n')
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'Local Asset Library could not start.\n' + str(exc)[:400]
                + '\nDetails: ' + str(log_dir / 'gui.log'), 'Local Asset Library — startup fault', 0x10)
        return 1
    finally:
        if bridge:
            bridge._close()
            if profile is not None:
                record_profile_outcome(bridge, profile)
    return 0
