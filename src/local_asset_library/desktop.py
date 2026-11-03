"""Windows desktop shell. All UI resources are bundled; worker inference stays offline."""
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
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
from .logs import kv
from .search_policy import DEFAULT_MODE

log = logging.getLogger(__name__)
SLOW_MS = 2000  # A call this slow is worth a line at the default level.


def show_in_explorer(path):
    """Open inside a directory, or select an original file using the Windows Shell."""
    if os.name != 'nt':
        raise ConfigError('Show in Explorer is only available on Windows')
    target = Path(path).resolve(strict=True)
    if target.is_dir():
        os.startfile(str(target))
    else:
        from .windows_shell import select_file
        select_file(str(target))


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
        self._shared = {}
        self._thread = threading.Thread(target=self._run, name='asset-gateway', daemon=True)
        self._thread.start()
        if not self._ready.wait(10):
            raise ConfigError('Desktop gateway initialization timed out')
        if hasattr(self, '_init_error'):
            raise ConfigError(self._init_error)

    def _run(self):
        asyncio.set_event_loop(self._loop)
        # A bounded pool: a slow read can hold a few threads, never the machine (identical reads share one, see _present).
        executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix='asset-present')
        self._loop.set_default_executor(executor)
        try:
            from .logs import session
            # The worker's raw stderr (library warnings) sits beside the session log, not in it.
            current = session()
            log = current.with_name(current.stem + '.worker.log') if current else self._config.output_path('logs', 'worker.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            self._diagnostics = log.open('a', encoding='utf-8')
            self._gateway = Gateway(self._config, audit_namespace='gui', diagnostic_stream=self._diagnostics,
                subprocess_flags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if self._config.sources_registry and not self._config.output_path('data','catalog.sqlite').exists():
                from .sources import aggregate
                aggregate(self._config)
            self._service = DesktopService(self._config)
            if self._config.sources_registry:
                from .processing_queue import after_restart
                try:
                    after_restart(self._config)  # A leftover queue is paused; it never resumes by itself.
                except (ConfigError, OSError, ValueError):
                    pass  # The Asset processing tab reads the queue again and shows what it can.
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
        # A read still running in the pool is abandoned, not awaited: closing never waits on it (the process exits).
        executor.shutdown(wait=False, cancel_futures=True)
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
            log.error('Call failed · %s', kv(reason=payload['reason']), exc_info=not isinstance(exc, FutureTimeout))
            with (self._gateway.audit_root / 'desktop-faults.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(encoded(payload) + '\n')
            return {'status': 'faulty', 'reason': payload['reason'], 'payload': payload}

    async def _present(self, operation, *args, guarded=True, shared=False):
        if shared:
            # Identical read-only calls in flight share one run: polls and a timed-out caller's retry never stack up.
            key = (operation, repr(args))
            task = self._shared.get(key)
            if task is None:
                task = self._shared[key] = asyncio.ensure_future(self._present(operation, *args, guarded=guarded))
                task.add_done_callback(lambda _: self._shared.pop(key, None))
            return await asyncio.shield(task)
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
        # Polls repeat every few seconds: debug only, one line per call name and repeat window.
        ms, name = round(audit['elapsed_seconds'] * 1000), operation.__name__.lstrip('_')
        if audit['status'] == 'faulty':
            log.warning('%s refused · %s', name, kv(reason=audit['reason'], ms=ms), extra={'repeat_key': ('fault', name, audit['reason'])})
        else:
            log.log(logging.INFO if ms >= SLOW_MS else logging.DEBUG, '%s · %s', name, kv(status=audit['status'], ms=ms),
                    extra={'repeat_key': ('call', name, ms >= SLOW_MS)})
        return result

    def context(self):
        return self._wait(self._present(self._service.context))

    def sources(self):
        return self._wait(self._present(self._sources, guarded=False, shared=True))

    def general_settings(self):
        from .settings import general_settings
        return self._wait(self._present(general_settings, self._config, guarded=False))

    def save_general_settings(self, storage_budget_gib, processing_formats=None, caption_batch_size=None,
                              descriptions_enabled=None, description_engine=None, description_server=None,
                              search_device=None, search_threads=None, image_formats=None):
        from .settings import save_general_settings
        return self._wait(self._present(save_general_settings, self._config, storage_budget_gib, processing_formats,
                                        caption_batch_size, descriptions_enabled, description_engine, description_server,
                                        search_device, 'user', search_threads, image_formats, guarded=False))

    # Rendering (decision 0022): device, parallel renders and memory; the speed test runs as an operation.
    def render_settings(self):
        from .render_devices import summary
        return self._wait(self._present(summary, self._config, guarded=False))

    def save_render_settings(self, device=None, processes=None, memory_gib=None):
        return self._wait(self._present(self._save_render_settings, device, processes, memory_gib, guarded=False))

    def _save_render_settings(self, device, processes, memory_gib):
        from .render_devices import summary
        from .render_pool import save
        save(self._config, processes, memory_gib, device)
        return dict(summary(self._config), status='saved')

    def render_test(self, action='start'):
        return self._wait(self._present(self._render_test, action, guarded=False))

    def search_check(self, action='status'):
        return self._wait(self._present(self._search_check, action, guarded=False))

    def _search_check(self, action):
        """Run check (decision 0026): start it, or read whether it passed, runs or failed (for Settings and setup)."""
        from . import engines
        from .source_operations import operation_status
        if action == 'start':
            return self._start_source_operation('search-check', None)
        if action != 'status':
            raise ConfigError('Unknown search check action')
        operation = operation_status(self._config)
        if operation.get('operation') == 'search-check' and operation.get('status') in {'queued', 'processing'}:
            return {'status': 'running', 'phase': operation.get('phase')}
        if engines.capability_ready(self._config, engines.search_device(self._config))['ready']:
            return {'status': 'ready'}
        if operation.get('operation') == 'search-check' and operation.get('status') == 'faulty':
            return {'status': 'failed', 'reason': operation.get('reason')}
        return {'status': 'missing', 'fault': engines.search_runtime_fault(self._config)}

    def _render_test(self, action):
        from .source_operations import cancel, operation_status
        if action == 'cancel':
            if operation_status(self._config).get('operation') != 'render-test':
                return {'status': 'idle'}
            return cancel(self._config)
        if action != 'start':
            raise ConfigError('Unknown render test action')
        return self._start_source_operation('render-test', None)

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

    def save_blender(self, path, confirm_rerender=False):
        """Settings → General → Blender installation: saves a checked Blender on its own."""
        from .setup_core import set_blender
        return self._wait(self._present(set_blender, self._config, path, confirm_rerender is True, guarded=False))

    def save_setup(self, choices):
        from .setup_core import save_setup
        return self._wait(self._present(save_setup, self._config, choices, guarded=False))

    def skip_setup(self):
        from .setup_core import skip_setup
        return self._wait(self._present(skip_setup, self._config, guarded=False))

    # Agent setup (decisions 0016, 0024): only the user decides a proposal; there is no session to open.
    def agent_setup_state(self):
        from .setup_agent import app_state
        return self._wait(self._present(app_state, self._config, guarded=False))

    def decide_setup_proposal(self, proposal_id, decision, confirm_rerender=False):
        from .setup_agent import decide
        return self._wait(self._present(decide, self._config, proposal_id, decision, confirm_rerender is True, guarded=False))

    def confirm_setup_review(self):
        """Looks good on the report of an agent's setup."""
        from .setup_core import confirm_review
        return self._wait(self._present(confirm_review, self._config, guarded=False))

    def undo_setup_value(self, key):
        from .setup_core import undo_value
        return self._wait(self._present(undo_value, self._config, key, guarded=False))

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
        return self._wait(self._present(importing_failures, self._config, guarded=False, shared=True))

    def _sources(self):
        from .sources import revision, source_statuses
        from .source_operations import operation_status
        from .notifications import reconcile
        statuses = source_statuses(self._config)
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
            try:
                source = sources.add(self._config, directory)
            except sources.Covered as exc:  # Inside a library folder: the app offers to show that folder.
                return {'status': 'faulty', 'reason': str(exc), 'covered_by': exc.folder['key']}
            return {**self._start_source_operation('scan', source['key']), 'replaced': source['replaced']}
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
            return cancel(sources.bound(self._config, sources.get_source(self._config, key)) if key else self._config)
        raise ConfigError('Unknown asset source action')

    # The Asset sources tab (decision 0023): library folders → bundles → packs → folders, read from saved data.
    def library_tree(self):
        from .library_view import tree
        return self._wait(self._present(tree, self._config, guarded=False, shared=True))

    def library_items(self, key, path='', offset=0, page_size=60, filters=None, show_files=True):
        from .library_view import folder_items
        return self._wait(self._present(folder_items, self._config, key, path, offset, page_size, filters, show_files,
                                        guarded=False, shared=True))

    def library_locate(self, asset_id):
        from .library_view import locate
        return self._wait(self._present(locate, self._config, asset_id, guarded=False, shared=True))

    def library_cover(self, key, relative):
        return self._wait(self._present(self._library_cover, key, relative, guarded=False))

    def _library_cover(self, key, relative):
        """A pack's cover: its own preview image, as a small thumbnail. Read only."""
        import base64
        from .config import _inside
        from .image_media import decode, image_format, png_bytes, thumbnail
        from .sources import bound, get_source
        scoped = bound(self._config, get_source(self._config, key))
        path = _inside(scoped.source_root, relative)
        fmt = image_format(str(path))
        if not fmt or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
            return {'status': 'faulty', 'reason': 'No cover image'}
        return {'status': 'ready', 'image': base64.b64encode(png_bytes(thumbnail(decode(path, fmt)[0])[0])).decode('ascii')}

    # The processing queue (decision 0023).
    def queue_state(self):
        from .processing_queue import state
        return self._wait(self._present(state, self._config, guarded=False, shared=True))

    def queue_add(self, action, scope, confirmed=False):
        from .processing_queue import add
        return self._wait(self._present(add, self._config, action, scope, bool(confirmed), guarded=False))

    def queue_remove(self, identifier):
        from .processing_queue import control
        return self._wait(self._present(control, self._config, 'remove', identifier, guarded=False))

    def queue_control(self, action, identifier=None, value=None):
        from .processing_queue import control
        return self._wait(self._present(lambda: {'status': 'saved', 'queue': control(self._config, action, identifier, value)}, guarded=False))

    def library_visit(self, key):
        from .library_view import record_visit
        return self._wait(self._present(record_visit, self._config, key, guarded=False))

    def folder_action(self, action, key, path='', value=None):
        return self._wait(self._present(self._folder_action, action, key, path, value, guarded=False))

    def folder_missing(self, key, path='', offset=0, page_size=30):
        from .library_view import unavailable
        return self._wait(self._present(unavailable, self._config, key, path, offset, page_size, guarded=False, shared=True))

    def _folder_action(self, action, key, path, value):
        from . import library_store, packs, sources
        source = sources.get_source(self._config, key)
        if action in {'make_pack', 'merge', 'clear_pack'}:
            packs.answer(self._config, key, path, None if action == 'clear_pack' else action)
        elif action == 'image_kind':
            sources.answer_folder(self._config, key, path, 'image_kind', value)
        elif action == 'rename_pack':
            packs.rename(self._config, key, path, value or '')
            return {'status': 'saved'}
        elif action in {'exclude', 'include'}:
            current = sources.excluded_folders(sources.bound(self._config, source))
            chosen = current + [path] if action == 'exclude' else [p for p in current if p != path]
            sources.set_excluded_folders(self._config, key, chosen)
        elif action == 'forget_missing':
            if not isinstance(value, dict) or not value.get('revision'):
                raise ConfigError('Review and confirm the missing entries before deleting.')
            return {'status': 'saved', 'forgotten': library_store.forget_missing(self._config, source['id'], path or None, value['revision'])}
        else:
            raise ConfigError('Unknown folder action')
        from .pack_profiles import record_change
        record_change(self._config, key, path, {'by': 'owner'})
        return self._start_source_operation('scan', key)

    # Pack profiles (decision 0024): a pack's rules, versions, signals and effect; apply, revert, review, export.
    def pack_profile(self, key, pack):
        return self._wait(self._present(self._pack_profile, key, pack, guarded=False, shared=True))

    def _pack_profile(self, key, pack):
        from . import pack_profiles, sources
        source = sources.get_source(self._config, key)
        return {'status': 'ready', 'key': key, 'pack': pack, 'rules': pack_profiles.current(self._config, source, pack),
                'history': pack_profiles.history(self._config, key, pack), 'signals': pack_profiles.signals(self._config, key).get(pack)}

    def pack_profile_action(self, action, key, pack, value=None):
        if action == 'export':
            return self._save_profile(key, pack)
        return self._wait(self._present(self._pack_profile_action, action, key, pack, value, guarded=False))

    def _pack_profile_action(self, action, key, pack, value):
        from . import pack_profiles, sources
        if action == 'effect':
            return pack_profiles.effect(self._config, key, pack, value)
        if action == 'review':
            return pack_profiles.review(self._config, key, pack, value)
        if action == 'separate_descriptions':
            # value: {group (library-folder relative), separate}; the pack holding the group is versioned.
            source = sources.get_source(self._config, key)
            owner = pack_profiles.pack_at(self._config, source, value['group'])
            group = pack_profiles._relative(value['group'], owner)
            rules = [r for r in pack_profiles.current(self._config, source, owner)
                     if not (r['kind'] == 'separate_descriptions' and r['group'] == group)]
            if value.get('separate'):
                rules.append({'kind': 'separate_descriptions', 'group': group})
            result = pack_profiles.apply(self._config, key, owner, rules, {'by': 'owner'})
        elif action == 'apply':
            result = pack_profiles.apply(self._config, key, pack, value, {'by': 'owner'})
        elif action == 'revert':
            result = pack_profiles.revert(self._config, key, pack, value)
        else:
            raise ConfigError('Unknown pack profile action')
        if result['rescan']:
            result['operation'] = self._start_source_operation('scan', key)
        return result

    # Agent activity and proposals (decision 0024): the feed from the MCP call logs; the owner decides proposals.
    def agent_activity(self, since=None):
        return self._wait(self._present(self._agent_activity, since, guarded=False, shared=True))

    def _agent_activity(self, since):
        from .agent_activity import recent
        from .pack_agent import proposals
        return {**recent(self._config, since), 'proposals': proposals(self._config, 'pending')}

    def agent_proposal(self, proposal_id, decision):
        return self._wait(self._present(self._agent_proposal, proposal_id, decision, guarded=False))

    def _agent_proposal(self, proposal_id, decision):
        from .pack_agent import decide
        result = decide(self._config, proposal_id, decision)
        if result.get('rescan'):
            result['operation'] = self._start_source_operation('scan', result['library_folder'])
        return result

    # Staged review: decide many proposals, save them together, then scan each library folder once.
    def agent_proposals_preview(self, decisions):
        from .pack_agent import preview
        return self._wait(self._present(preview, self._config, decisions, guarded=False))

    def agent_proposals_commit(self, decisions):
        return self._wait(self._present(self._agent_proposals_commit, decisions, guarded=False))

    def _agent_proposals_commit(self, decisions):
        from .pack_agent import commit
        result = commit(self._config, decisions)
        result['operations'] = [self._start_source_operation('scan', key) for key in result['rescan']]
        return result

    # Add library folder (decision 0024): a names-only quick look, then add, keep the names and scan.
    def quick_look_start(self, directory):
        from .quick_look import start
        from .sources import Covered
        try:
            return start(self._config, directory)
        except Covered as exc:
            return {'status': 'faulty', 'reason': str(exc), 'covered_by': exc.source['key']}
        except Exception as exc:
            return {'status': 'faulty', 'reason': str(exc)}

    def quick_look_status(self, job_id):
        from .quick_look import status
        return self._wait(self._present(status, job_id, guarded=False))

    def quick_look_add(self, job_id):
        return self._wait(self._present(self._quick_look_add, job_id, guarded=False))

    def _quick_look_add(self, job_id):
        from . import sources
        from .pack_agent import prompt
        from .quick_look import _jobs, save
        job = _jobs.get(job_id)
        if job is None or not job['done'] or job['error']:
            raise ConfigError('Choose the folder again; its quick look is gone')
        added = sources.add(self._config, job['path'])
        save(self._config, added, job_id)
        sources.aggregate(self._config)
        operation = self._start_source_operation('scan', added['key'])
        return {'status': 'added', 'key': added['key'], 'name': added['name'], 'prompt': prompt(added), 'operation': operation}

    def pack_signals(self, key):
        from .pack_agent import counts
        return self._wait(self._present(counts, self._config, key, guarded=False, shared=True))

    # Check my model (decision 0024): a local model works through synthetic packs; one check at a time.
    def model_check_state(self):
        from .model_check import latest
        job = getattr(self, '_model_check', None)
        return {'status': 'ready', 'running': bool(job and not job['done']), 'job': job and {k: v for k, v in job.items() if k != 'thread'},
                'last': latest(self._config)}

    def model_check_start(self, url, model, full=False):
        import threading
        from .engine_server import checked_model, checked_url
        from .model_check import run
        job = getattr(self, '_model_check', None)
        if job and not job['done']:
            return {'status': 'faulty', 'reason': 'A check is already running'}
        try:
            url, model = checked_url(url), checked_model(model)
        except ConfigError as exc:
            return {'status': 'faulty', 'reason': str(exc)}
        job = self._model_check = {'done': False, 'cancel': False, 'index': 0, 'total': 0, 'tree': None, 'report': None, 'reason': None,
                                   'model': model, 'url': url, 'full': bool(full)}

        def work():
            def progress(index, total, name):
                job.update(index=index, total=total, tree=name)
            try:
                job['report'] = run(self._config, url, model, bool(full), progress=progress, cancelled=lambda: job['cancel'])
            except Exception as exc:  # Shown in the card; the check never retries by itself.
                job['reason'] = str(exc)
            finally:
                job['done'] = True
        threading.Thread(target=work, name='model-check', daemon=True).start()
        return {'status': 'started'}

    def model_check_cancel(self):
        job = getattr(self, '_model_check', None)
        if job and not job['done']:
            job['cancel'] = True
        return {'status': 'cancelling' if job and not job['done'] else 'idle'}

    def _save_profile(self, key, pack):
        import webview
        from .pack_profiles import export
        try:
            body = self._wait(self._present(export, self._config, key, pack, guarded=False))
            if body.get('status') == 'faulty':
                return body
            name = ''.join(c if c.isalnum() or c in ' -_.' else '_' for c in body['pack']['name']).strip() or 'pack'
            selected = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=name + '.assetarium-profile.json',
                                                       file_types=('Pack profile (*.json)',))
            if not selected:
                return {'status': 'cancelled'}
            path = Path(selected[0] if isinstance(selected, (list, tuple)) else selected)
            from .sources import get_source
            if Path(get_source(self._config, key)['path']).resolve() in (path.resolve(), *path.resolve().parents):
                return {'status': 'faulty', 'reason': 'Nothing is written into a library folder; choose a place outside it'}
            path.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding='utf-8')
            return {'status': 'saved', 'path': str(path)}
        except Exception as exc:
            return {'status': 'faulty', 'reason': str(exc)}

    def path_action(self, action, key, relative=''):
        """Show a library file or folder in Explorer, open it with its default app, or copy its path."""
        return self._wait(self._present(self._path_action, action, key, relative, guarded=False))

    def _path_action(self, action, key, relative):
        from .config import _inside
        from .sources import bound, get_source
        scoped = bound(self._config, get_source(self._config, key))
        target = _inside(scoped.source_root, relative) if relative else scoped.source_root
        if not target.exists():
            raise ConfigError('That file or folder is not there any more')
        if action == 'reveal':
            show_in_explorer(str(target))
            return {'status': 'revealed'}
        if action == 'open':
            if os.name != 'nt':
                raise ConfigError('Opening files is only available on Windows')
            os.startfile(str(target))  # The owner's default app for that file; nothing here writes it.
            return {'status': 'opened'}
        if action == 'copy':
            return self._clipboard(str(target))
        raise ConfigError('Unknown path action')

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
        if name in {'decide_export', 'forget_export'}:  # Export answers belong to the pack holding them (decision 0024).
            from .pack_profiles import record_change
            anchor = next((d['anchor'] for d in sources.export_decisions(sources.bound(self._config, sources.get_source(self._config, key)))
                           if d['id'] == args[0]), '')
            record_change(self._config, key, anchor, {'by': 'owner'})
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
        return self._wait(self._present(self._changes, guarded=False, shared=True))

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
            from .library_store import database_path
            library.append(revision(config))
            sources.append(stamp(database_path(config)))
            for source in registry(config)['sources']:
                scoped = bound(config, source)
                sources.append([stamp(scoped.output_path('data', 'library/' + name)) for name in
                                ('source-status.json', 'source-operation.json', 'source-cancel.json', 'active.json')]
                               + [stamp(config.project_root / 'data/library/source-faults' / (source['id'] + '.json'))])
        sources.append(stamp(config.project_root / 'data/library/settings.json'))
        sources += [stamp(config.project_root / 'data/library' / name) for name in ('rendering.json', 'render-test.json', 'search-test.json')]
        sources.append(stamp(config.project_root / 'data/library/setup.json'))
        sources.append(stamp(config.project_root / 'data/library/notifications.json'))
        from .asset_collections import path as collections_path
        from .asset_tags import path as tags_path
        # Agent edits arrive through this token; the views reload only their own data.
        organized = [stamp(collections_path(config)), stamp(tags_path(config))]
        from .setup_agent import connection_token, store_path
        # Connection records carry liveness, so a client that died flips the token without touching a file.
        from .agent_activity import token as activity_token
        agent = [stamp(store_path(config)), stamp(config.project_root / 'data/library/setup.json'), connection_token(config.project_root),
                 activity_token(config)]
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
    """Run the window; when it closes, end the process even if a read is still running in a worker thread."""
    code = run()
    from .logs import stop
    stop()  # os._exit skips atexit: write the last repeat counts and "Session ended" now.
    logging.shutdown()
    for stream in (sys.stdout, sys.stderr):
        if stream:  # None under pythonw.
            stream.flush()
    os._exit(code)  # Closing already cancelled owned operations and stopped the worker; nothing else may keep it alive.


def run():
    from .logs import start
    root = Path(__file__).resolve().parents[2]
    argv = sys.argv[1:]
    level = 'debug' if '--verbose' in argv else argv[argv.index('--log-level') + 1] if '--log-level' in argv[:-1] else None
    session_log = start(root, 'app', level)
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
                + '\nDetails: ' + str(session_log), 'Assetarium — startup fault', 0x10)
        return 1
    finally:
        if bridge:
            bridge._close()
            if profile is not None:
                record_profile_outcome(bridge, profile)
    return 0
