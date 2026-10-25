"""Owner commands for a terminal: sources, processing, settings, failures and collections.

Thin wrappers over the backend calls the desktop app makes, so no rule lives here
(decision 0011: the backend is the authority). Works the same in PowerShell and a
POSIX shell. Removing a source or deleting a collection needs an interactive
terminal: agents can run commands, and only the owner deletes (decision 0012).
"""
import argparse
import json
from pathlib import Path
import sys
import time

from .config import ConfigError, load_config, project_config_path

COMMANDS = {'sources', 'settings', 'process', 'describe', 'cancel', 'failures', 'collections', 'setup'}
ENDED_OK = {'complete'}


def wanted(argv):
    """True when argv names an owner command (``process --stage`` stays the stage-level maintenance command)."""
    words = [w for i, w in enumerate(argv) if not w.startswith('-') and (i == 0 or argv[i - 1] != '--config')]
    return bool(words) and words[0] in COMMANDS and not (words[0] == 'process' and ({'--stage', '--dry-run'} & set(argv)))


def parser():
    root = argparse.ArgumentParser(prog='local-assets', description=__doc__.split('\n')[0])
    root.add_argument('--config', type=Path)
    root.add_argument('--json', action='store_true', help='Print the backend result as JSON (for scripts)')
    commands = root.add_subparsers(dest='command', required=True)
    sources = commands.add_parser('sources', help='List, add, remove, enable or disable asset sources').add_subparsers(dest='action', required=True)
    sources.add_parser('list')
    sources.add_parser('add', help='Register a folder and scan it').add_argument('path')
    sources.add_parser('remove', help='Stop listing a source (files and results stay on disk)').add_argument('key')
    for action in ('enable', 'disable'):
        sources.add_parser(action).add_argument('key')
    images = sources.add_parser('images', help='Include 2D images from this source')
    images.add_argument('key')
    images.add_argument('state', choices=['on', 'off'])
    settings = commands.add_parser('settings', help='Show or change Settings → General').add_subparsers(dest='action', required=True)
    settings.add_parser('show')
    change = settings.add_parser('set')
    change.add_argument('--formats', help='Comma-separated: fbx,gltf,obj (glb counts as gltf); "none" pauses processing')
    change.add_argument('--budget-gib', type=int, help='Storage budget in whole GiB')
    change.add_argument('--batch-size', type=int, choices=[1, 2, 4, 8], help='Description batch size')
    change.add_argument('--descriptions', choices=['on', 'off'], help='Generate descriptions (off keeps existing ones)')
    change.add_argument('--engine', choices=['builtin', 'local-server'], help='How descriptions are generated')
    change.add_argument('--server-url', help='Local model server address, e.g. http://127.0.0.1:8080/v1')
    change.add_argument('--server-model', help='Model name the local server lists')
    change.add_argument('--search-device', choices=['cuda', 'cpu'], help='Where semantic and image search run (switching re-indexes)')
    setup =commands.add_parser('setup', help='Guided setup in this terminal, or its parts').add_subparsers(dest='action')
    setup.add_parser('status', help='This computer, Blender, engines and what is missing (runs nothing)')
    setup.add_parser('skip', help='Record that setup was skipped')
    agent = setup.add_parser('agent', help='Let your AI agent set up Assetarium (interactive terminal only)')
    agent.add_argument('agent_action', nargs='?', choices=['open', 'proposals', 'end'], default='open',
                       help='open a 60-minute setup session (default), apply or reject Blender proposals, or end the session')
    blender = setup.add_parser('blender', help='Check or save the Blender executable').add_subparsers(dest='blender_action', required=True)
    blender.add_parser('check').add_argument('path')
    save = blender.add_parser('set', help='Check, then save to config.local.toml')
    save.add_argument('path')
    save.add_argument('--confirm-rerender', action='store_true',
                      help='Accept that finished 3D previews are rendered again with the new Blender')
    for name, text in (('process', 'Process assets: previews, search data, publish'),
                       ('describe', 'Generate missing descriptions with the configured engine')):
        command = commands.add_parser(name, help=text)
        command.add_argument('--asset-source', required=True, metavar='KEY')
        command.add_argument('--follow', action='store_true', help='Watch the running operation instead of starting one')
    commands.add_parser('cancel', help='Cancel the running operation safely').add_argument('--asset-source', required=True, metavar='KEY')
    commands.add_parser('failures', help='Original paths of assets whose import failed')
    collections = commands.add_parser('collections', help='List, export or delete collections').add_subparsers(dest='action', required=True)
    collections.add_parser('list').add_argument('query', nargs='?', default='')
    export = collections.add_parser('export', help='Write JSON, a PNG sample sheet or Markdown (PDF: desktop app)')
    export.add_argument('collection_id')
    export.add_argument('--format', required=True, choices=['json', 'png', 'md'])
    export.add_argument('--output', help='File under data/exports (default: data/exports/collections/<name>)')
    collections.add_parser('delete').add_argument('collection_id')
    return root


def say(args, text):
    if not args.json:
        print(text, flush=True)


def confirm(question):
    """Deletions are owner-only: an interactive terminal must answer; there is no bypass flag."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise ConfigError('This deletes or detaches data and needs an interactive terminal; run it yourself')
    return input(question + ' Type "yes" to confirm: ').strip().lower() == 'yes'


def progress_line(operation):
    line = f"[{round(100 * (operation.get('progress') or 0)):3d}%] {operation.get('phase') or operation.get('status')}"
    if operation.get('total'):
        line += f" · {operation.get('completed', 0)}/{operation['total']}"
    return line


def follow(args, config, scoped):
    """Print progress until the operation ends. Ctrl+C cancels safely; a second Ctrl+C only stops watching."""
    from .source_operations import RUNNING, cancel, operation_status
    last, cancelling = None, False
    while True:
        try:
            operation = operation_status(scoped)
            line = progress_line(operation)
            if line != last:
                say(args, line)
                last = line
            if operation.get('status') not in RUNNING:
                return operation
            time.sleep(.5)
        except KeyboardInterrupt:
            if cancelling:
                say(args, 'Stopped watching; the operation keeps cancelling. Watch it again with --follow.')
                return dict(operation_status(scoped), watching='stopped')
            cancelling = True
            cancel(scoped)
            say(args, 'Cancelling: the current asset finishes and saved work is kept '
                      '(descriptions finish their batch). Press Ctrl+C again to stop watching.')


def run_operation(args, config, operation, key):
    from .source_operations import RUNNING, operation_status, start
    from .sources import bound, get_source, source_status
    source = get_source(config, key)
    scoped = bound(config, source)
    if not args.follow and operation_status(scoped).get('status') not in RUNNING:
        started = start(config, operation, key)
        if started.get('status') == 'busy':
            raise ConfigError(started['reason'] + '; watch it with --follow')
    elif args.follow and operation_status(scoped).get('status') not in RUNNING:
        ended = operation_status(scoped)
        say(args, 'No operation is running for ' + source['name'] + '; last: ' + str(ended.get('status')))
        return ended
    else:
        say(args, 'An operation is already running for ' + source['name'] + '; watching it.')
    ended = follow(args, config, scoped)
    status = source_status(config, source)
    if ended.get('reason'):
        say(args, 'Reason: ' + ended['reason'])
    say(args, f"{source['name']}: {ended.get('status')} · {status['pending']} pending · {status.get('failed', 0)} failed"
              + (f" · {status['descriptions']['missing']} without a description" if status.get('descriptions') else ''))
    if (ended.get('status') == 'complete' and operation == 'process' and status.get('descriptions_enabled')
            and (status.get('descriptions') or {}).get('missing')):
        say(args, f"Optional: describe --asset-source {key} writes descriptions with the configured engine.")
    if status.get('failed'):
        say(args, 'Failed imports are kept with their evidence; list them with: failures')
    return dict(ended, source=status)


def sources_command(args, config):
    from . import sources
    from .source_operations import operation_status
    if args.action == 'list':
        result = {'status': 'ready', 'sources': [sources.source_status(config, s) for s in sources.registry(config)['sources']]}
        for s in result['sources']:
            say(args, f"{s['key']}  {'enabled ' if s['enabled'] else 'disabled'}  {s['pending']} pending · "
                      f"{s.get('failed', 0)} failed  {s['path']}\n    {s['reason']}")
        if not result['sources']:
            say(args, 'No asset sources yet. Add one with: sources add PATH')
        return result
    if args.action == 'add':
        source = sources.add(config, args.path)
        say(args, f"Added {source['name']} as {source['key']}; scanning (no rendering or models).")
        args.follow = False
        return run_operation(args, config, 'scan', source['key'])
    source = sources.get_source(config, args.key)
    if args.action == 'remove':
        if not confirm(f"Remove “{source['name']}”? Assetarium stops listing this source and its assets. Its files and "
                       "processing results stay on disk; adding the folder again brings them back."):
            say(args, 'Not removed.')
            return {'status': 'cancelled'}
        sources.remove(config, args.key)
        say(args, f"Removed {source['name']}.")
        return {'status': 'saved'}
    if args.action in {'enable', 'disable'}:
        sources.set_enabled(config, args.key, args.action == 'enable')
        say(args, f"{source['name']} {args.action}d.")
        if args.action == 'disable':
            return {'status': 'saved'}
        args.follow = False
        return run_operation(args, config, 'scan', args.key)
    sources.set_import_types(config, args.key, args.state == 'on')
    say(args, f"2D images {args.state} for {source['name']}; scanning.")
    args.follow = False
    return run_operation(args, config, 'scan', args.key)


def settings_command(args, config):
    from .settings import general_settings, save_general_settings
    current = general_settings(config)
    if args.action == 'set':
        options = (args.formats, args.budget_gib, args.batch_size, args.descriptions, args.engine, args.server_url,
                   args.server_model, args.search_device)
        if all(value is None for value in options):
            raise ConfigError('Give at least one of --formats, --budget-gib, --batch-size, --descriptions, --engine, '
                              '--server-url, --server-model or --search-device')
        formats = None if args.formats is None else (
            [] if args.formats.strip().lower() == 'none' else [f.strip().lower() for f in args.formats.split(',') if f.strip()])
        server = None if args.server_url is None and args.server_model is None else {
            'url': args.server_url if args.server_url is not None else current['description_server']['url'],
            'model': args.server_model if args.server_model is not None else current['description_server']['model']}
        save_general_settings(config, args.budget_gib if args.budget_gib is not None else current['storage_budget_gib'],
                              formats, args.batch_size, None if args.descriptions is None else args.descriptions == 'on',
                              args.engine, server, args.search_device)
        current = general_settings(config)
        say(args, 'Saved. Changing settings never deletes results or retries faults.')
    engine = current['description_engine']
    say(args, f"Processing formats: {', '.join(current['processing_formats']) or 'none (processing paused)'}\n"
              f"Storage budget: {current['storage_budget_gib']:g} GiB\n"
              f"Descriptions: {'on' if current['descriptions_enabled'] else 'off (existing descriptions are kept)'}\n"
              f"Description engine: {engine}" + (f" ({current['description_server']['url']}, model "
                                                 f"{current['description_server']['model'] or 'not set'})" if engine == 'local-server' else '')
              + f"\nDescription batch size: {current['caption_batch_size']}" + (' (not used by a local server)' if engine == 'local-server' else '')
              + f"\nSearch runs on: {'CPU' if current['search_device'] == 'cpu' else 'NVIDIA GPU (CUDA)'}")
    return current


def show_checks(args, result):
    for check in result['checks']:
        mark = {'passed': 'ok  ', 'warning': 'warn', 'failed': 'FAIL'}[check['status']]
        say(args, f"  [{mark}] {check['label']}" + (f": {check['detail']}" if check.get('detail') else ''))
    say(args, {'passed': 'Blender is ready.', 'warning': 'Blender works; see the warning.',
               'failed': 'Blender cannot be used.', 'cancelled': 'Check cancelled.'}[result['status']])


def status_lines(args, config):
    from . import setup_core
    env = setup_core.environment_report(config)
    blender = setup_core.blender_report(config)
    gpu = env['gpu']
    devices = [f"{d['name']}, {d['vram_gib']:g} GiB, driver {d['driver']}" for d in gpu['nvidia']] + gpu['other']
    say(args, f"This computer: {env['os']['name']} · {'; '.join(devices) or 'no GPU detected'} · "
              f"{env['disk']['free_gib']:g} GiB free on {env['disk']['drive']}")
    say(args, f"Blender: {blender['used'] or 'not found (install Blender ' + blender['tested_version'] + ' from ' + blender['download_url'] + ')'}"
              + (f" ({blender['candidates'][0]['origin']})" if blender['candidates'] else ''))
    for key, value in env['engines'].items():
        say(args, f"Engine {key}:")
        for item in value['items'] + (value['search'] if key == 'builtin' else []):
            say(args, f"  [{'ok  ' if item['ready'] else 'miss'}] {item['label']}"
                      + (f"\n         {item['command']}" if item.get('command') else '')
                      + (f" — {item['detail']}" if item.get('detail') and not item['ready'] else ''))
    return {'status': 'ready', 'environment': env, 'blender': blender}


def ask(question, default=''):
    answer = input(f"{question}{f' [{default}]' if default != '' else ''}: ").strip()
    return answer or str(default)


def wizard(args, config):
    """The desktop wizard's steps in a terminal; the same setup_core rules decide everything."""
    from . import engines, setup_core
    from .settings import general_settings
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise ConfigError('Guided setup needs an interactive terminal; use setup status / setup blender / settings set instead')
    say(args, 'Assetarium setup. It only records your choices and checks Blender when you ask; nothing is downloaded, '
              'installed, processed or started. Every choice can be changed later.\n')
    status = status_lines(args, config)
    current, choices, skipped = general_settings(config), {}, []
    blender = status['blender']
    say(args, '\n1. Blender renders previews in the background with scripts and add-ons turned off.')
    for i, candidate in enumerate(blender['candidates'], 1):
        say(args, f"   {i}. {candidate['path']} ({candidate['origin']})")
    answer = ask('Number or full path of blender, or Enter to skip', '1' if blender['candidates'] else '')
    if answer:
        path = blender['candidates'][int(answer) - 1]['path'] if answer.isdigit() and 0 < int(answer) <= len(blender['candidates']) else answer
        result = setup_core.validate_blender(config, path)
        show_checks(args, result)
        if result['status'] in {'passed', 'warning'}:
            choices['blender_path'] = path
            if setup_core.blender_change(config, path) == 'write' and blender['processed_models']:
                say(args, f"   Changing Blender marks {blender['processed_models']:,} finished 3D inspections as needing processing again.")
                choices['confirm_rerender'] = ask('   Accept that? (yes/no)', 'no').lower() == 'yes'
                if not choices['confirm_rerender']:
                    choices.pop('blender_path')
    else:
        skipped.append('blender')
    say(args, '\n2. Formats to process. Which engine do you target?')
    for i, hint in enumerate(setup_core.ENGINE_HINTS, 1):
        say(args, f"   {i}. {hint['label']} — {', '.join(hint['formats'])}: {hint['reason']}")
    answer = ask('Number, or Enter to keep ' + (','.join(current['processing_formats']) or 'none'), '')
    if answer.isdigit() and 0 < int(answer) <= len(setup_core.ENGINE_HINTS):
        hint = setup_core.ENGINE_HINTS[int(answer) - 1]
        choices.update(engine_hint=hint['id'], processing_formats=list(hint['formats']))
    formats = ask('Formats (fbx,gltf,obj)', ','.join(choices.get('processing_formats', current['processing_formats'])))
    choices['processing_formats'] = [f.strip().lower() for f in formats.split(',') if f.strip()]
    use = setup_core.storage_use(config)
    budget = setup_core.recommended_budget(use.get('allocated_gib'), status['environment']['disk']['free_gib'])
    say(args, '\n3. The storage budget caps the disk space Assetarium uses (its folder plus each source’s metadata-lal; '
              'originals and shared models are not counted).' + (f" Current use: {use['allocated_gib']:g} GiB." if use.get('allocated_gib') else ''))
    choices['storage_budget_gib'] = int(ask('Budget in GiB', budget['gib'] if budget else int(current['storage_budget_gib'])))
    say(args, '\n4. Descriptions are optional AI-written texts per asset; without them names, filters, keyword and image search still work.')
    choices['descriptions_enabled'] = ask('Generate descriptions? (on/off)', 'on' if current['descriptions_enabled'] else 'off').lower() == 'on'
    if choices['descriptions_enabled']:
        engine = ask('Engine: builtin (NVIDIA CUDA) or local-server (any GPU the server supports, experimental)', current['description_engine'])
        choices['description_engine'] = engine
        if engine == 'local-server':
            url = ask('Server address', current['description_server']['url'])
            probe = setup_core.check_server(config, url)
            say(args, '   ' + (f"Connected; models: {', '.join(probe['models']) or 'none listed'}" if probe['status'] == 'connected' else probe['reason']))
            choices['description_server'] = {'url': url, 'model': ask('Model name', current['description_server']['model'] or
                                                                         ((probe.get('models') or [''])[0]))}
        else:
            recommended = status['environment']['recommended_batch']
            choices['caption_batch_size'] = int(ask('5. Description batch size (1, 2, 4, 8)', recommended['size'] if recommended
                                                    else current['caption_batch_size']))
    nvidia = bool(engines.gpu_bf16(status['environment']['gpu']))
    say(args, '\nSearch by description and by image runs EmbeddingGemma on an NVIDIA GPU (cuda) or on the CPU (cpu, '
              'slower to index, same results).' + ('' if nvidia else ' No NVIDIA GPU with BF16 was found, so cpu is suggested.'))
    choices['search_device'] = ask('Search device (cuda/cpu)', current['search_device'] if nvidia or current['search_device'] == 'cpu'
                                   else 'cpu').lower()
    say(args, '\nReview:\n' + json.dumps({k: v for k, v in choices.items() if k != 'confirm_rerender'}, indent=2, ensure_ascii=False))
    if ask('Save these choices? (yes/no)', 'yes').lower() != 'yes':
        say(args, 'Nothing was saved.')
        return {'status': 'cancelled'}
    choices['skipped_steps'] = skipped
    result = setup_core.save_setup(config, choices)
    say(args, 'Saved.' + (f" {result['blender']['reason']}" if result['blender']['status'] == 'faulty' else '')
              + ' Next: sources add PATH, then process --asset-source KEY.')
    return result


def agent_command(args, config):
    """Opening a session and deciding proposals are user gestures: interactive terminal only, no flag (decision 0016)."""
    from . import setup_agent
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise ConfigError('Agent setup is opened and approved by you in an interactive terminal (or in the app); run it yourself')
    if args.agent_action == 'end':
        result = setup_agent.end_session(config)
        say(args, 'Agent setup access ended. Agents can still read the setup status.')
        return result
    if args.agent_action == 'open':
        result = setup_agent.open_session(config, 'cli')
        say(args, f"Agent setup access is open for {result['minutes_left']} minutes. Add Assetarium to your agent:")
        for snippet in setup_agent.snippets(config.project_root):
            say(args, f"\n{snippet['label']} — {snippet['where']}\n{snippet['text']}")
        say(args, '\nThen ask it:\n' + setup_agent.SETUP_PROMPT + '\n\nApprove its Blender proposal with: setup agent proposals')
        return result
    value, fault = setup_agent.load(config)
    if fault:
        raise ConfigError(fault)
    pending = [item for item in value['proposals'] if item['state'] == 'pending']
    if not pending:
        say(args, 'No proposal is waiting.')
    decided = []
    for item in pending:
        say(args, f"Your agent proposes: Blender → {item['path']}, checked as Blender {item['version']}.")
        answer = ask('Apply, reject or skip? (apply/reject/skip)', 'skip').lower()
        if answer not in {'apply', 'reject'}:
            continue
        rerender = False
        if answer == 'apply' and item['rerender']:
            say(args, f"Changing Blender marks {item['rerender']:,} finished 3D inspections as needing processing again.")
            rerender = ask('Accept that? (yes/no)', 'no').lower() == 'yes'
            if not rerender:
                say(args, 'Not applied; the proposal is still waiting.')
                continue
        result = setup_agent.decide(config, item['id'], answer, rerender)
        say(args, {'applied': 'Applied: saved to config.local.toml.', 'rejected': 'Rejected.'}.get(result['status'],
                   'Not applied: ' + str(result['proposal']['reason'])))
        decided.append(result)
    return {'status': 'ready', 'decided': decided}


def setup_command(args, config):
    from . import setup_core
    if args.action is None:
        return wizard(args, config)
    if args.action == 'agent':
        return agent_command(args, config)
    if args.action == 'status':
        return status_lines(args, config)
    if args.action == 'skip':
        result = setup_core.skip_setup(config)
        say(args, 'Setup skipped. Run it any time with: setup')
        return result
    result = setup_core.validate_blender(config, args.path)
    show_checks(args, result)
    if args.blender_action == 'check' or result['status'] not in {'passed', 'warning'}:
        return dict(result, status='ready' if result['status'] in {'passed', 'warning'} else 'faulty')
    saved = setup_core.set_blender(config, result['path'], args.confirm_rerender)
    say(args, 'Saved to config.local.toml; the next Process assets run uses it.' if saved['status'] == 'saved'
        else 'Already the Blender Assetarium uses; nothing was written.')
    return saved


def collections_command(args, config):
    from . import asset_collections
    if args.action == 'list':
        result = asset_collections.summaries(config, args.query)
        for c in result['collections']:
            say(args, f"{c['collection_id']}  {c['name']} · {c['asset_count']} assets")
        if not result['collections']:
            say(args, 'No collections' + (' match.' if args.query else ' yet.'))
        return result
    value = asset_collections.detail(config, args.collection_id)
    if args.action == 'delete':
        count = len(value['items'])
        if not confirm(f"Delete “{value['name']}”? This deletes the collection with its labels and notes"
                       f"{f' for {count} assets' if count else ''}. The assets themselves, their files and their tags are not affected."):
            say(args, 'Not deleted.')
            return {'status': 'cancelled'}
        result = asset_collections.delete(config, args.collection_id)
        say(args, f"Deleted “{value['name']}”. The assets remain in the library.")
        return result
    from .collection_export import KINDS, checked_target, default_directory, file_name, write_export
    path = (checked_target(config, args.output, args.format) if args.output else
            default_directory(config) / (file_name(value['name']) + KINDS[args.format][0]))
    if path.exists() and not confirm(f'{path} exists. Replace it?'):
        say(args, 'Not exported.')
        return {'status': 'cancelled'}
    try:
        result = write_export(config, args.collection_id, args.format, path, thumbnails_reader(config))
    except ImportError as exc:
        raise ConfigError(f'{args.format} exports need Pillow ({exc.name}); run this through scripts/local-assets.ps1 '
                          'or scripts/local-assets.sh, which use the mcp environment') from None
    say(args, f"Exported {result['files']} file(s): {result['path']}")
    return result


def thumbnails_reader(config):
    """The desktop's verified card images, for exports, without a window."""
    services = []
    def read(entry):
        if not services:  # Built on the first visual member only.
            from .desktop_service import DesktopService
            from .interactive_preview import InteractivePreviewService
            from .source_browser import SourceBrowser
            service = DesktopService(config)
            services.extend((service, SourceBrowser(config, InteractivePreviewService(service))))
        service, browser = services
        return (service.thumbnail(entry['asset_id']) if entry['in_library'] else
                browser.call('thumbnail', entry['source_key'], entry['asset_id']))
    return read


def main(argv, config=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')  # A narrow console code page must never crash a command.
    args = parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        config = config or load_config(args.config or project_config_path(root), root)
        if not config.sources_registry:
            raise ConfigError('Owner commands need managed asset sources (schema_version 2 configuration)')
        if args.command == 'sources':
            result = sources_command(args, config)
        elif args.command == 'settings':
            result = settings_command(args, config)
        elif args.command == 'setup':
            result = setup_command(args, config)
        elif args.command in {'process', 'describe'}:
            result = run_operation(args, config, args.command, args.asset_source)
        elif args.command == 'cancel':
            from .source_operations import cancel
            from .sources import bound, get_source
            result = cancel(bound(config, get_source(config, args.asset_source)))
            say(args, result.get('reason') or 'Nothing is running for this source.')
        elif args.command == 'failures':
            from .sources import importing_failures
            result = importing_failures(config)
            say(args, f"{result['assets']} assets failed to import ({len(result['paths'])} original files):")
            for path in result['paths']:
                say(args, '  ' + path)
            for item in result['unavailable']:
                say(args, f"  Unavailable: {item['source']}: {item['reason']}")
        else:
            result = collections_command(args, config)
    except KeyboardInterrupt:
        print('Interrupted.', file=sys.stderr)
        return 130
    except (ConfigError, OSError, ValueError) as exc:
        if args.json:
            print(json.dumps({'status': 'faulty', 'reason': str(exc)}, ensure_ascii=False))
        else:
            print('Error: ' + str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    ended = result.get('status')
    return 0 if ended in ENDED_OK | {'ready', 'saved', 'exported', 'deleted', 'cancelled', 'idle', 'cancelling',
                                     'skipped', 'unchanged'} else 1
