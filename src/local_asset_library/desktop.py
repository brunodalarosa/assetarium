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
import uuid

from .catalog import encoded
from .config import ConfigError, load_project_config
from .desktop_service import DesktopService
from .mcp_assets import error_payload, validate
from .mcp_server import Gateway
from .search_policy import DEFAULT_MODE


def show_in_explorer(path):
    """Open Explorer with ``path`` selected. Windows only (decision 0013); no shell, and Explorer's exit code is meaningless."""
    if os.name != 'nt':
        raise ConfigError('Show in Explorer is only available on Windows')
    subprocess.Popen(['explorer.exe', '/select,' + os.path.normpath(path)], creationflags=subprocess.CREATE_NO_WINDOW)


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
        self._pending_prints = {}
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
        def retain_runs():
            from .retention import retire_gui_runs
            try:
                retire_gui_runs(self._config)  # Keeps the ten newest launch audits, including this one.
            except Exception:
                logging.exception('Launch audit retention fault')
        self._loop.call_soon(lambda: self._loop.run_in_executor(None, retain_runs))
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

    def save_general_settings(self, storage_budget_gib, processing_formats=None, caption_batch_size=None,
                              descriptions_enabled=None, description_engine=None, description_server=None,
                              search_device=None):
        from .settings import save_general_settings
        return self._wait(self._present(save_general_settings, self._config, storage_budget_gib, processing_formats,
                                        caption_batch_size, descriptions_enabled, description_engine, description_server,
                                        search_device, guarded=False))

    # Setup wizard (decision 0014): thin calls into setup_core; nothing here starts at launch.
    def setup_state(self):
        from .setup_core import setup_state
        return self._wait(self._present(setup_state, self._config, guarded=False))

    def setup_environment(self):
        from .setup_core import environment_report
        return self._wait(self._present(environment_report, self._config, guarded=False))

    def setup_blender(self):
        from .setup_core import blender_report
        return self._wait(self._present(blender_report, self._config, guarded=False))

    def setup_check_blender(self, path):
        from .setup_core import check_blender
        return self._wait(self._present(check_blender, self._config, path, guarded=False))

    def setup_cancel_blender(self):
        from .setup_core import cancel_blender_checks
        return cancel_blender_checks()

    def setup_storage_use(self, measure=False):
        from .setup_core import storage_use
        return self._wait(self._present(storage_use, self._config, bool(measure), guarded=False))

    def setup_check_server(self, url, model=''):
        from .setup_core import check_server
        return self._wait(self._present(check_server, self._config, url, model or '', guarded=False))

    def save_setup(self, choices):
        from .setup_core import save_setup
        return self._wait(self._present(save_setup, self._config, choices, guarded=False))

    def skip_setup(self):
        from .setup_core import skip_setup
        return self._wait(self._present(skip_setup, self._config, guarded=False))

    # Agent setup (decision 0016): only these user-driven calls open a session or decide a proposal.
    def agent_setup_state(self):
        from .setup_agent import app_state
        return self._wait(self._present(app_state, self._config, guarded=False))

    def open_agent_setup(self):
        from .setup_agent import open_session
        return self._wait(self._present(open_session, self._config, 'app', guarded=False))

    def end_agent_setup(self):
        from .setup_agent import end_session
        return self._wait(self._present(end_session, self._config, guarded=False))

    def decide_setup_proposal(self, proposal_id, decision, confirm_rerender=False):
        from .setup_agent import decide
        return self._wait(self._present(decide, self._config, proposal_id, decision, confirm_rerender is True, guarded=False))

    def choose_blender_executable(self):
        import webview
        try:
            types = ('Blender (blender.exe)',) if os.name == 'nt' else ()
            selected = self._window.create_file_dialog(webview.FileDialog.OPEN, file_types=types)
            return {'status': 'selected', 'path': selected[0]} if selected else {'status': 'cancelled'}
        except Exception as exc:
            return {'status': 'faulty', 'reason': str(exc)}

    def interface_settings(self):
        from .settings import interface_settings
        return self._wait(self._present(interface_settings, self._config, guarded=False))

    def save_interface_settings(self, appearance=None, inspector_width=None):
        from .settings import save_interface_settings
        return self._wait(self._present(save_interface_settings, self._config, appearance, inspector_width,
                                        guarded=False))

    def importing_failures(self):
        from .sources import importing_failures
        return self._wait(self._present(importing_failures, self._config, guarded=False))

    def _sources(self):
        from .sources import registry, source_status, revision
        from .source_operations import operation_status
        from .notifications import reconcile
        statuses = [source_status(self._config, s) for s in registry(self._config)['sources']]
        # Notices follow the statuses already read for this call; no extra scans.
        return {'status': 'ready', 'sources': statuses, 'revision': revision(self._config),
                'scan': operation_status(self._config), 'notifications': reconcile(self._config, statuses)['items']}

    def notification_action(self, action, identifier=None):
        return self._wait(self._present(self._notification_action, action, identifier, guarded=False))

    def _notification_action(self, action, identifier):
        from .notifications import act
        return {'status': 'saved', 'notifications': act(self._config, action, identifier)['items']}

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
        if action == 'images':
            sources.set_import_types(self._config, key, enabled)
            return self._start_source_operation('scan', key)
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
        if action in {'process', 'describe'}:
            return self._start_source_operation(action, key)
        if action == 'cancel':
            return cancel(sources.bound(self._config, sources.get_source(self._config, key)))
        raise ConfigError('Unknown asset source action')

    # Excluded folders and duplicate export folders (decision 0019): each change rescans the source.
    def source_exclusions(self, key, patterns):
        return self._wait(self._present(self._source_setting, 'set_excluded_folders', key, patterns, guarded=False))

    def source_export(self, key, suggestion_id, decision):
        return self._wait(self._present(self._source_setting, 'decide_export', key, suggestion_id, decision, guarded=False))

    def source_export_undo(self, key, decision_id):
        return self._wait(self._present(self._source_setting, 'forget_export', key, decision_id, guarded=False))

    # Texture folder for models missing textures (decision 0021): each change rescans the source.
    def source_textures(self, key, folder, single_copies):
        return self._wait(self._present(self._source_setting, 'set_texture_folder', key, folder, single_copies, guarded=False))

    def source_textures_undo(self, key):
        return self._wait(self._present(self._source_setting, 'forget_texture_folder', key, guarded=False))

    # Recheck of failures from the file/dependency check (decision 0020): preview reads; retry needs its preview.
    def recheck_failures(self, key):
        from .recheck import preview
        return self._wait(self._present(preview, self._config, key, guarded=False))

    def retry_failures(self, key, preview_id):
        return self._wait(self._present(self._retry_failures, key, preview_id, guarded=False))

    def _retry_failures(self, key, preview_id):
        from .recheck import release
        result = release(self._config, key, preview_id)
        self._start_source_operation('scan', key)
        return result

    def _source_setting(self, name, key, *args):
        from . import sources
        if not self._config.sources_registry:
            raise ConfigError('Configure asset sources before using source settings')
        getattr(sources, name)(self._config, key, *args)
        return self._start_source_operation('scan', key)

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

    def source_image_view(self, key, asset_id, edge=None, expected_version=None):
        return self._wait(self._present(self._source_browser.call, 'image_view', key, asset_id, edge, expected_version))

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

    def image_view(self, asset_id, edge=None, expected_version=None):
        return self._wait(self._present(self._service.image_view, asset_id, edge, expected_version))

    def reveal(self, asset_id, source_format=None):
        return self._wait(self._present(self._reveal, self._service.reveal, asset_id, source_format))

    def source_reveal(self, key, asset_id, source_format=None):
        return self._wait(self._present(self._reveal, self._source_browser.call, 'reveal', key, asset_id, source_format))

    def _reveal(self, locate, *args):
        # The path comes from the source boundary, never from the client. A fault is reported once and not retried.
        located = locate(*args)
        show_in_explorer(located['path'])
        return {'status': 'revealed', 'format': located['format']}

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
        sources.append(stamp(config.project_root / 'data/library/setup.json'))
        sources.append(stamp(config.project_root / 'data/library/notifications.json'))
        from .asset_collections import path as collections_path
        from .asset_tags import path as tags_path
        # Agent edits arrive through this token; the views reload only their own data.
        organized = [stamp(collections_path(config)), stamp(tags_path(config))]
        from .setup_agent import connection_token, store_path
        # Connection records carry liveness, so a client that died flips the token without touching a file.
        agent = [stamp(store_path(config)), stamp(config.project_root / 'data/library/setup.json'), connection_token(config.project_root)]
        return {'status': 'ready', 'library': digest(library)[:16], 'sources': digest(sources)[:16],
                'collections': digest(organized)[:16], 'agent': digest(agent)[:16],
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

    # Collections and tags are owner organization data (decision 0012); originals are never touched.
    def collections(self, query='', containing=None):
        from .asset_collections import summaries
        return self._wait(self._present(summaries, self._config, query, containing, guarded=False))

    def collection(self, collection_id, query=''):
        from .asset_collections import detail
        return self._wait(self._present(detail, self._config, collection_id, query, guarded=False))

    def collection_action(self, action, collection_id=None, options=None):
        return self._wait(self._present(self._collection_action, action, collection_id, options or {}, guarded=False))

    def _collection_action(self, action, collection_id, options):
        from . import asset_collections as collections
        if not isinstance(options, dict):
            raise ConfigError('Collection options must be an object')
        if action == 'create':
            return collections.create(self._config, options.get('name'), options.get('description', ''),
                                      options.get('asset_ids', []), options.get('source_key'))
        if action == 'update':
            return collections.update(self._config, collection_id, options.get('name'), options.get('description'))
        if action == 'delete':
            return collections.delete(self._config, collection_id)
        if action == 'add':
            return collections.add(self._config, collection_id, options.get('asset_ids', []), options.get('source_key'))
        if action == 'remove':
            return collections.remove(self._config, collection_id, options.get('asset_ids', []))
        if action == 'restore':
            return collections.restore(self._config, collection_id, options.get('removed', []))
        if action == 'set_item':
            return collections.set_item(self._config, collection_id, options.get('asset_id'), options.get('label'), options.get('notes'))
        raise ConfigError('Unknown collection action')

    def asset_tags(self, asset_id=None):
        return self._wait(self._present(self._asset_tags, asset_id, guarded=False))

    def _asset_tags(self, asset_id):
        from .asset_tags import known, load, tags_for
        value = load(self._config)
        return {'status': 'ready', 'tags': tags_for(self._config, asset_id, value) if asset_id else [],
                'known': known(self._config, value), 'revision': value.get('revision', 0)}

    def set_asset_tags(self, asset_id, tags):
        from .asset_tags import change
        return self._wait(self._present(lambda: change(self._config, [asset_id], replace=tags), guarded=False))

    async def _collection_search(self, collection_id, settings):
        """Owner text (names, labels, notes, tags) first, then the ranked search limited to members."""
        from .asset_collections import detail
        if not isinstance(settings, dict):
            raise ConfigError('Search settings must be an object')
        query = settings.get('query', '') if isinstance(settings.get('query', ''), str) else ''
        value = await asyncio.to_thread(detail, self._config, collection_id, query)
        items, ranked = value.pop('items'), None
        texts = [dict(e, match='text') for e in items if e.get('text_match')]
        if query.strip() and any(e['in_library'] for e in items):
            arguments = {'query': query, 'mode': settings.get('mode', DEFAULT_MODE), 'limit': 40,
                         'filters': {'collection': collection_id}}
            ranked = await self._search(arguments)
        order = {e['asset_id']: e for e in items}
        results = list(texts)
        seen = {e['asset_id'] for e in texts}
        payload = (ranked or {}).get('payload') or {}
        if ranked and not ranked['is_error'] and payload.get('status') != 'faulty':
            for result in payload.get('results', []):
                if result['asset_id'] in order and result['asset_id'] not in seen:
                    results.append(dict(order[result['asset_id']], match='search', score=result.get('score'),
                                        matching_channels=result.get('matching_channels')))
                    seen.add(result['asset_id'])
        search = None if ranked is None else {
            'status': 'faulty' if ranked['is_error'] or payload.get('status') == 'faulty' else payload.get('status'),
            'reason': payload.get('reason'), 'mode': ranked['arguments']['mode'],
            'elapsed_seconds': ranked['elapsed_seconds'], 'arguments': ranked['arguments']}
        return dict(value, status='results', items=results, query=query, search=search)

    def collection_search(self, collection_id, settings):
        return self._wait(self._collection_search(collection_id, settings))

    def collection_export(self, collection_id, kind, target=None):
        """Save dialog (or a scripted target under data/exports), then write the chosen export."""
        from .asset_collections import detail
        from .collection_export import KINDS, checked_target, default_directory, file_name
        if kind not in KINDS:
            return {'status': 'faulty', 'reason': 'Unknown export kind'}
        extension, description = KINDS[kind]
        try:
            name = detail(self._config, collection_id)['name']
            if target is not None:
                path = checked_target(self._config, target, kind)
            else:
                import webview
                directory = default_directory(self._config)
                directory.mkdir(parents=True, exist_ok=True)
                selected = self._window.create_file_dialog(webview.FileDialog.SAVE, directory=str(directory),
                    save_filename=file_name(name) + extension, file_types=(description,))
                if not selected:
                    return {'status': 'cancelled'}
                path = Path(selected[0] if isinstance(selected, (list, tuple)) else selected)
                if path.suffix.lower() != extension:
                    path = path.with_name(path.name + extension)
        except Exception as exc:
            return {'status': 'faulty', 'reason': str(exc)}
        return self._wait(self._present(self._export, collection_id, kind, path))

    def _export(self, collection_id, kind, path):
        from .asset_collections import detail
        from .collection_export import member_thumbnails, package, report_html, write_export
        def read(entry):
            return (self._service.thumbnail(entry['asset_id']) if entry['in_library'] else
                    self._source_browser.call('thumbnail', entry['source_key'], entry['asset_id']))
        if kind != 'pdf':
            return write_export(self._config, collection_id, kind, path, read)
        value = detail(self._config, collection_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        self._pending_prints[token] = path
        return {'status': 'print', 'token': token, 'path': str(path),
                'html': report_html(value, package(self._config, value), member_thumbnails(value, read))}

    def collection_print(self, token):
        """Print the report the page has placed in #print-root to the chosen PDF with WebView2."""
        path = self._pending_prints.pop(token, None) if isinstance(token, str) else None
        if path is None:
            return {'status': 'faulty', 'reason': 'This PDF export expired; export it again.'}
        try:
            self._print_pdf(path)
        except Exception as exc:
            return {'status': 'faulty', 'reason': 'PDF printing failed: ' + (str(exc) or type(exc).__name__)}
        if not path.is_file() or path.stat().st_size == 0:
            return {'status': 'faulty', 'reason': 'WebView2 reported success but wrote no PDF'}
        return {'status': 'exported', 'kind': 'pdf', 'path': str(path), 'files': 1}

    def _print_pdf(self, path):
        from System import Action, Boolean, Func, Type
        from System.Threading.Tasks import Task
        form = self._window.native
        done, outcome = threading.Event(), {}
        def finished(task):
            outcome['ok'] = not task.IsFaulted and not task.IsCanceled and bool(task.Result)
            outcome['reason'] = str(task.Exception.InnerException.Message) if task.IsFaulted else None
            done.set()
        def start():
            core = form.browser.webview.CoreWebView2
            settings = core.Environment.CreatePrintSettings()
            settings.ShouldPrintBackgrounds = True
            settings.ShouldPrintHeaderAndFooter = False
            core.PrintToPdfAsync(str(path), settings).ContinueWith(Action[Task[Boolean]](finished))
        form.Invoke(Func[Type](start))
        if not done.wait(120):
            raise ConfigError('WebView2 did not finish printing within 120 s')
        if not outcome['ok']:
            raise ConfigError(outcome['reason'] or 'WebView2 could not write the PDF')

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


WINDOW_BACKGROUND = {'light': '#f1f5f9', 'dark': '#10151e'}


def windows_prefers_dark():
    """Read-only check of the Windows app theme, so the first frame matches it."""
    if os.name != 'nt':
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] == 0
    except OSError:
        return False


def page_html(config):
    """The built React bundle inlined into the CSP-restricted shell, themed before first paint."""
    from .settings import interface_settings
    ui = Path(__file__).resolve().parent / 'ui'
    interface = interface_settings(config)
    resolved = interface['appearance'] if interface['appearance'] != 'system' else (
        'dark' if windows_prefers_dark() else 'light')
    boot = {'appearance': interface['appearance'], 'inspector_width': interface['inspector_width']}
    # "</" cannot close the inline script; JSON keeps every other character literal.
    boot_json = json.dumps(boot, ensure_ascii=False).replace('</', '<\\/')
    html = (ui / 'index.html').read_text(encoding='utf-8')
    html = html.replace('data-theme="light"', f'data-theme="{resolved}" data-appearance="{interface["appearance"]}"', 1)
    html = html.replace('/* BOOT_DATA */', 'window.LAL_BOOT=' + boot_json + ';')
    html = html.replace('/* BUNDLED_STYLE */', (ui / 'build/app.css').read_text(encoding='utf-8'))
    html = html.replace('/* INTERACTIVE_PREVIEW_SCRIPT */', (ui / 'interactive-preview.js').read_text(encoding='utf-8'))
    html = html.replace('/* BUNDLED_SCRIPT */', (ui / 'build/app.js').read_text(encoding='utf-8'))
    return html, resolved


def create_window(config, bridge):
    """Shared shell construction for the normal launcher and real bridge verification."""
    import webview
    webview.settings.update({'ALLOW_DOWNLOADS': False, 'ALLOW_FILE_URLS': False,
        'OPEN_EXTERNAL_LINKS_IN_BROWSER': False, 'SHOW_DEFAULT_MENUS': False})
    html, theme = page_html(config)
    window = webview.create_window('Assetarium', html=html, js_api=bridge,
        width=1280, height=860, min_size=(640, 480), resizable=True, background_color=WINDOW_BACKGROUND[theme])
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
            ctypes.windll.user32.MessageBoxW(None, 'Assetarium could not start.\n' + str(exc)[:400]
                + '\nDetails: ' + str(log_dir / 'gui.log'), 'Assetarium — startup fault', 0x10)
        return 1
    finally:
        if bridge:
            bridge._close()
            if profile is not None:
                record_profile_outcome(bridge, profile)
    return 0
