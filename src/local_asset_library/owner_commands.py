"""Owner commands for a terminal: library folders, packs, the processing queue, settings, failures and collections.

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

COMMANDS = {'library', 'sources', 'packs', 'previews', 'queue', 'forget-missing', 'settings', 'rendering', 'process', 'describe',
            'cancel', 'failures', 'recheck', 'collections', 'setup'}
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
    for name in ('library', 'sources'):  # "sources" is the old name, kept for scripts.
        library_parser(commands.add_parser(name, help='List, add, remove, enable or disable library folders'
                                           if name == 'library' else argparse.SUPPRESS))
    packs = commands.add_parser('packs', help='Packs detected in a library folder: list, rename, merge or split'
                                ).add_subparsers(dest='action', required=True)
    packs.add_parser('list').add_argument('key')
    rename = packs.add_parser('rename', help='Give a pack a display name (empty restores the folder name)')
    rename.add_argument('key')
    rename.add_argument('folder', help='The pack folder inside the library folder ("" for the library folder itself)')
    rename.add_argument('name')
    for action, text in (('merge', 'Merge a pack into its parent pack'), ('split', 'Make a folder a pack of its own'),
                         ('reset', 'Forget a merge or split; detection decides again')):
        change = packs.add_parser(action, help=text)
        change.add_argument('key')
        change.add_argument('folder')
    for name, text in (('previews', 'Make previews (inspection, previews, search data) for a folder, pack or assets'),
                       ('describe', 'Generate missing descriptions for a folder, pack or assets with the configured engine')):
        command = commands.add_parser(name, help=text + '; it starts at once or waits in the queue')
        command.add_argument('target', nargs='?', metavar='KEY[/FOLDER]', help='A library folder, or a folder or pack inside it')
        command.add_argument('--asset', action='append', default=[], metavar='ID', help='Picked assets (repeatable; needs KEY)')
        command.add_argument('--asset-source', metavar='KEY', help=argparse.SUPPRESS)  # The old form: the whole folder.
        command.add_argument('--dry-run', action='store_true', help='Print what it would do and its estimate; queue nothing')
        command.add_argument('--yes', action='store_true', help='Accept the estimate of a long job (over 30 minutes)')
    queue = commands.add_parser('queue', help='The processing queue: list, move, remove, pause, resume, overnight'
                                ).add_subparsers(dest='action', required=True)
    queue.add_parser('list')
    move = queue.add_parser('move')
    move.add_argument('item')
    move.add_argument('position', type=int)
    queue.add_parser('remove', help='Remove a waiting item, or cancel the running one cleanly').add_argument('item')
    queue.add_parser('pause')
    queue.add_parser('resume')
    overnight = queue.add_parser('overnight', help='Hold descriptions until a window (for example 22:00-07:00)')
    overnight.add_argument('state', choices=['on', 'off'])
    overnight.add_argument('--window', metavar='HH:MM-HH:MM')
    forget = commands.add_parser('forget-missing', help='Forget assets whose files vanished (their history stays)')
    forget.add_argument('key')
    forget.add_argument('--pack', metavar='FOLDER', help='Only under this folder or pack')
    settings =commands.add_parser('settings', help='Show or change Settings → General').add_subparsers(dest='action', required=True)
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
    change.add_argument('--search-threads', help='"auto" (the speed test\'s choice) or how many CPU threads build search data')
    rendering = commands.add_parser('rendering', help='Render device, renders at a time, memory and the speed test'
                                    ).add_subparsers(dest='action', required=True)
    rendering.add_parser('show')
    change = rendering.add_parser('set', help='Limits only lower renders at a time or change their memory; never slower')
    change.add_argument('--device', help='"auto" (fastest tested), "cpu", or a GPU key that "rendering show" lists')
    change.add_argument('--processes', help='"auto" or 1 to 8: at most this many renders at a time')
    change.add_argument('--memory-gib', help='"auto" (70%% of free memory) or whole GiB rendering may use')
    test = rendering.add_parser('test', help='Run the render speed test now (about 2 minutes; synthetic shapes only)')
    test.add_argument('--follow', action='store_true', help='Watch a running test instead of starting one')
    rendering.add_parser('cancel', help='Cancel a running speed test (the previous result is kept)')
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
    command = commands.add_parser('process', help='Process a whole library folder now (previews, search data, publish)')
    command.add_argument('--asset-source', required=True, metavar='KEY')
    command.add_argument('--follow', action='store_true', help='Watch the running operation instead of starting one')
    commands.add_parser('cancel', help='Cancel the running operation safely').add_argument('--asset-source', required=True, metavar='KEY')
    commands.add_parser('failures', help='Original paths of assets whose import failed')
    recheck = commands.add_parser('recheck', help='Recheck failures from the file/dependency check; retry those that pass (asks first)')
    recheck.add_argument('--asset-source', dest='key', required=True)
    collections = commands.add_parser('collections', help='List, export or delete collections').add_subparsers(dest='action', required=True)
    collections.add_parser('list').add_argument('query', nargs='?', default='')
    export = collections.add_parser('export', help='Write JSON, a PNG sample sheet or Markdown (PDF: desktop app)')
    export.add_argument('collection_id')
    export.add_argument('--format', required=True, choices=['json', 'png', 'md'])
    export.add_argument('--output', help='File under data/exports (default: data/exports/collections/<name>)')
    collections.add_parser('delete').add_argument('collection_id')
    return root


def library_parser(command):
    sources = command.add_subparsers(dest='action', required=True)
    sources.add_parser('list')
    sources.add_parser('add', help='Watch a folder and scan it (one inside a library folder is refused; '
                                   'one around library folders replaces them, keeping their assets)').add_argument('path')
    sources.add_parser('remove', help='Stop watching a folder (its results stay in the library store)').add_argument('key')
    for action in ('enable', 'disable'):
        sources.add_parser(action).add_argument('key')
    for action, text in (('exclude', 'Skip a folder when scanning (name pattern like "Unity*" or a path inside the folder)'),
                         ('include', 'Stop excluding a folder pattern')):
        change = sources.add_parser(action, help=text)
        change.add_argument('key')
        change.add_argument('pattern')
    images = sources.add_parser('images', help='Treat the images in a folder as textures or as 2D assets (or forget the answer)')
    images.add_argument('key')
    images.add_argument('folder', help='A folder inside the library folder ("" for all of it)')
    images.add_argument('kind', choices=['textures', '2d', 'auto'])
    textures = sources.add_parser('textures', help='Models missing textures: list folder suggestions, or choose one')
    textures.add_argument('key')
    textures.add_argument('--use', metavar='FOLDER', help='A suggested texture folder (path inside the library folder)')
    textures.add_argument('--single-copies', action='store_true', help='Also use textures that exist only once in the folder')
    textures.add_argument('--undo', action='store_true', help='Remove the choice; its repairs are dropped on the rescan')
    exports = sources.add_parser('exports', help='Folders that look like other exports of the same models: list or answer')
    exports.add_argument('key')
    answer = exports.add_mutually_exclusive_group()
    answer.add_argument('--group', metavar='ID', help='Group the suggested folders as alternate files of the same assets')
    answer.add_argument('--separate', metavar='ID', help='Keep them separate; not suggested again')
    answer.add_argument('--exclude', metavar='ID', help='Exclude the extra folders from scanning')
    answer.add_argument('--undo', metavar='ID', help='Forget a saved answer; the folders are suggested again')


def packs_command(args, config):
    from . import packs, sources
    source = sources.get_source(config, args.key)
    if args.action == 'list':
        detected = packs.structure(config, source)
        names = packs.names_of(config, source)
        result = {'status': 'ready', 'packs': [{**p, 'name': names.get(p['path']) or p['name'] or source['name']}
                                              for p in sorted(detected['packs'].values(), key=lambda p: p['path'])],
                  'bundles': detected['bundles']}
        for pack in result['packs']:
            evidence = ', '.join(m['evidence'] for m in pack['markers'][:3]) or pack['basis']
            say(args, f"{pack['path'] or '(the library folder)'}  “{pack['name']}”  {len(pack['folders'])} folder(s) · {evidence}")
        for bundle in result['bundles']:
            say(args, f"{bundle}  (bundle)")
        if not result['packs']:
            say(args, 'No packs yet; scan the library folder first.')
        return result
    if args.action == 'rename':
        packs.rename(config, args.key, args.folder, args.name)
        say(args, f"Renamed {args.folder or 'the library folder'} to “{args.name}”." if args.name else 'Name reset.')
        return {'status': 'saved'}
    packs.answer(config, args.key, args.folder, {'merge': 'merge', 'split': 'make_pack', 'reset': None}[args.action])
    say(args, {'merge': 'Merged into its parent pack', 'split': 'Made a pack of its own', 'reset': 'Answer forgotten'}[args.action]
              + '; scanning (no rendering or models).')
    args.follow = False
    return run_operation(args, config, 'scan', args.key)


def queue_scope(args):
    target = args.target or args.asset_source
    if not target:
        raise ConfigError('Name a library folder (KEY), a folder in it (KEY/FOLDER), or KEY with --asset')
    key, _, folder = target.replace('\\', '/').partition('/')
    return {'key': key, 'path': folder.strip('/'), 'asset_ids': args.asset}


def queue_command(args, config):
    """Make previews and Generate descriptions as the app does: a queue item, an estimate, the same thresholds."""
    from . import processing_queue as queue
    action = 'previews' if args.command in {'previews', 'process'} else 'descriptions'
    scope = queue_scope(args)
    if args.dry_run:
        source, scope = queue.validate_scope(config, scope)
        found = queue.resolve(config, action, scope)
        estimate = queue.estimate(config, action, found) if found['ids'] else None
        say(args, (queue.describe_estimate(estimate) if estimate else 'Nothing to do here.')
            + ''.join(f"\n{n:,} blocked: {reason}" for reason, n in found['blocked'].items()))
        return {'status': 'ready', 'assets': len(found['ids']), 'blocked': found['blocked'], 'estimate': estimate}
    result = queue.add(config, action, scope, confirmed=args.yes)
    if result['status'] == 'confirm':
        say(args, result['body'])
        say(args, 'This is a long job. Run it again with --yes to start it, or --dry-run to look first.')
        return {**result, 'status': 'cancelled'}
    say(args, f"{result['title']}. {result['body']}")
    say(args, 'Follow it with: queue list')
    return {**result, 'status': 'saved'}


def queue_list(args, config):
    from . import processing_queue as queue
    if args.action == 'list':
        state = queue.state(config)
    elif args.action == 'move':
        state = queue.control(config, 'move', args.item, args.position)
    elif args.action == 'remove':
        state = queue.control(config, 'remove', args.item)
    elif args.action == 'overnight':
        start, _, end = (args.window or '').partition('-')
        state = queue.control(config, 'overnight', value={'enabled': args.state == 'on', **({'start': start, 'end': end} if args.window else {})})
    else:
        state = queue.control(config, args.action)
    running = state['running']
    if running:
        operation = running.get('operation') or {}
        say(args, f"Running: {running['action']} · {running['label']} ({running['id'][:8]}) {progress_line(operation)}")
    for index, item in enumerate(state['up_next']):
        say(args, f"{index}. {item['action']} · {item['label']} ({item['id'][:8]}){' · held for tonight' if item['held'] else ''}")
    if state['paused']:
        say(args, 'Paused: resume with "queue resume".')
    for group in state['blocked']:
        say(args, f"Blocked: {group['reason']} — {group['fix']}")
    if not running and not state['up_next']:
        say(args, 'Nothing running or waiting.')
    return state


def say(args, text):
    if not args.json:
        print(text, flush=True)


def recheck_command(args, config):
    """Recheck, then retry only after a typed yes (decision 0020); never from a script or an agent."""
    from . import recheck
    found = recheck.preview(config, args.key)
    say(args, f"{found['retry']:,} recorded failures came from the file check and pass it now"
              + (f" (e.g. {', '.join(found['examples'][:3])})" if found['examples'] else '') + '.'
              + (f" {found['still_failing']:,} still fail it and stay recorded." if found['still_failing'] else ''))
    if not found['retry']:
        say(args, 'Nothing to retry.')
        return found
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise ConfigError('Retrying recorded failures needs your answer in an interactive terminal; run it yourself')
    if input(f"Retry these {found['retry']:,} assets on the next Make previews? Type \"yes\" to confirm: ").strip().lower() != 'yes':
        say(args, 'Nothing was changed.')
        return {**found, 'status': 'cancelled'}
    result = recheck.release(config, args.key, found['preview_id'])
    say(args, result['reason'] + ' Scanning to refresh the source status.')
    args.follow = False
    run_operation(args, config, 'scan', args.key)
    return result


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
        result = {'status': 'ready', 'sources': sources.source_statuses(config)}
        for s in result['sources']:
            say(args, f"{s['key']}  {'enabled ' if s['enabled'] else 'disabled'}  {s['pending']} pending · "
                      f"{s.get('failed', 0)} failed  {s['path']}\n    {s.get('scan_fault') or s.get('reason', '')}")
        if not result['sources']:
            say(args, 'No library folders yet. Add one with: library add PATH')
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
    if args.action in {'exclude', 'include'}:
        current = sources.excluded_folders(sources.bound(config, source))
        pattern = sources.validate_exclusion(args.pattern)
        if args.action == 'include' and pattern not in current:
            raise ConfigError(f"“{pattern}” is not excluded. Excluded: {', '.join(current) or 'none'}")
        sources.set_excluded_folders(config, args.key, current + [pattern] if args.action == 'exclude'
                                     else [p for p in current if p != pattern])
        say(args, f"{'Excluding' if args.action == 'exclude' else 'No longer excluding'} “{pattern}” in {source['name']}; "
                  "scanning. Nothing on disk is deleted.")
        args.follow = False
        return run_operation(args, config, 'scan', args.key)
    if args.action == 'textures':
        if args.undo or args.use or args.single_copies:
            if args.undo:
                sources.forget_texture_folder(config, args.key)
            else:
                sources.set_texture_folder(config, args.key, args.use, args.single_copies)
            say(args, 'Saved; scanning. Repaired models wait for Make previews; originals are not changed.')
            args.follow = False
            return run_operation(args, config, 'scan', args.key)
        status = sources.source_status(config, source)
        found, chosen = status.get('texture_suggestion'), status.get('texture_folder')
        if chosen:
            say(args, f"Chosen: {chosen['folder'] or 'no folder'}{' + single copies' if chosen['single_copies'] else ''} "
                      f"({chosen['utc']}). Undo with --undo.")
        if not found:
            say(args, 'No models are waiting for textures.')
            return status
        say(args, f"{found['assets']:,} models can't find their textures (e.g. {', '.join(found['examples'][:3])}).")
        for option in found['folders']:
            say(args, f"  --use \"{option['folder']}\"  fixes {option['fixes_without_single_copies']:,}; "
                      f"with --single-copies {option['fixes']:,} ({option['unresolved']:,} stay unresolved)")
        single = found['single_copies_only']
        say(args, f"  --single-copies alone fixes {single['fixes']:,} ({single['unresolved']:,} stay unresolved)")
        return status
    if args.action == 'exports':
        answers = {'group': args.group, 'separate': args.separate, 'exclude': args.exclude}
        chosen = next(((d, i) for d, i in answers.items() if i), None)
        if args.undo:
            sources.forget_export(config, args.key, args.undo)
        elif chosen:
            sources.decide_export(config, args.key, chosen[1], chosen[0])
        if args.undo or chosen:
            say(args, 'Saved; scanning.')
            args.follow = False
            return run_operation(args, config, 'scan', args.key)
        status = sources.source_status(config, source)
        for s in status.get('export_suggestions', []):
            where = s['anchor'] or 'the source root'
            near = s.get('near') or {}
            differs = '; '.join(part for part in (
                near.get('only') and 'not in every folder: ' + ', '.join(f'{n} in {f}' for f, n in near['only'].items()),
                near.get('repeated') and 'repeated inside: ' + ', '.join(f'{n} in {f}' for f, n in near['repeated'].items())) if part)
            say(args, f"{s['id']}\n    In {where}: {', '.join(s['folders'])} {'share' if near else 'have the same'} {s['names']} model names "
                      f"(e.g. {', '.join(s['sample_names'][:3])})" + (f"; {differs} (those stay as they are)" if differs else '')
                      + f". Keeps {s['reference']}"
                      + (f"; already grouped: {', '.join(s['grouped_folders'])}" if s['grouped_folders'] else '') + '.')
        for d in status.get('export_decisions', []):
            say(args, f"{d['id']}  answered {d['decision']}: {d['anchor'] or 'root'} / {', '.join(d['folders'])}")
        if not status.get('export_suggestions') and not status.get('export_decisions'):
            say(args, 'No duplicate export folders found.')
        say(args, 'Answer with: library exports KEY --group ID | --separate ID | --exclude ID   (undo: --undo ID)')
        return status
    if args.action == 'images':
        value = {'textures': 'texture', '2d': 'image', 'auto': None}[args.kind]
        sources.answer_folder(config, args.key, args.folder, 'image_kind', value)
        say(args, f"Images in {args.folder or source['name']}: {args.kind}; scanning (no rendering or models).")
        args.follow = False
        return run_operation(args, config, 'scan', args.key)
    raise ConfigError('Unknown library command')


def settings_command(args, config):
    from .settings import general_settings, save_general_settings
    current = general_settings(config)
    if args.action == 'set':
        options = (args.formats, args.budget_gib, args.batch_size, args.descriptions, args.engine, args.server_url,
                   args.server_model, args.search_device, getattr(args, 'search_threads', None))
        if all(value is None for value in options):
            raise ConfigError('Give at least one of --formats, --budget-gib, --batch-size, --descriptions, --engine, '
                              '--server-url, --server-model, --search-device or --search-threads')
        formats = None if args.formats is None else (
            [] if args.formats.strip().lower() == 'none' else [f.strip().lower() for f in args.formats.split(',') if f.strip()])
        server = None if args.server_url is None and args.server_model is None else {
            'url': args.server_url if args.server_url is not None else current['description_server']['url'],
            'model': args.server_model if args.server_model is not None else current['description_server']['model']}
        save_general_settings(config, args.budget_gib if args.budget_gib is not None else current['storage_budget_gib'],
                              formats, args.batch_size, None if args.descriptions is None else args.descriptions == 'on',
                              args.engine, server, args.search_device, search_threads=getattr(args, 'search_threads', None))
        current = general_settings(config)
        say(args, 'Saved. Changing settings never deletes results or retries faults.')
    engine = current['description_engine']
    say(args, f"Processing formats: {', '.join(current['processing_formats']) or 'none (processing paused)'}\n"
              f"Storage budget: {current['storage_budget_gib']:g} GiB\n"
              f"Descriptions: {'on' if current['descriptions_enabled'] else 'off (existing descriptions are kept)'}\n"
              f"Description engine: {engine}" + (f" ({current['description_server']['url']}, model "
                                                 f"{current['description_server']['model'] or 'not set'})" if engine == 'local-server' else '')
              + f"\nDescription batch size: {current['caption_batch_size']}" + (' (not used by a local server)' if engine == 'local-server' else '')
              + f"\nSearch runs on: {'CPU' if current['search_device'] == 'cpu' else 'NVIDIA GPU (CUDA)'}"
              + (f"\nSearch CPU threads: {search_line(config)}" if current['search_device'] == 'cpu' else ''))
    return current


def rendering_command(args, config):
    from .render_devices import summary
    from .render_pool import save, saved
    from .source_operations import RUNNING, cancel, operation_status, start
    if args.action == 'set':
        if args.device is None and args.processes is None and args.memory_gib is None:
            raise ConfigError('Give at least one of --device, --processes or --memory-gib')
        current = saved(config)
        number = lambda value, name: None if value == 'auto' else int(value) if value.isdigit() else ConfigError(
            f'--{name} takes "auto" or a whole number')
        choice = {key: current[key] if value is None else number(value, key.replace('_', '-')) if key != 'device'
                  else None if value == 'auto' else value
                  for key, value in (('device', args.device), ('processes', args.processes), ('memory_gib', args.memory_gib))}
        for value in choice.values():
            if isinstance(value, ConfigError):
                raise value
        save(config, choice['processes'], choice['memory_gib'], choice['device'])
        say(args, 'Saved.')
    if args.action in {'test', 'cancel'}:
        running = operation_status(config).get('status') in RUNNING
        if args.action == 'cancel':
            result = cancel(config) if running and operation_status(config).get('operation') == 'render-test' else {'status': 'idle'}
            say(args, 'Cancelling the speed test; the previous result is kept.' if result['status'] != 'idle' else 'No speed test is running.')
            return result
        if not args.follow:
            started = start(config, 'render-test')
            if started.get('status') == 'busy':
                raise ConfigError(started['reason'] + '; watch a running test with: rendering test --follow')
        elif not running:
            say(args, 'No speed test is running.')
        ended = follow(args, config, config)
        if ended.get('reason'):
            say(args, 'Reason: ' + ended['reason'])
    current = summary(config)
    plan = current['plan']
    say(args, f"Now: {plan['device']}, {plan['processes']} at a time ({plan['reason']}"
              + (f"; {plan['best_reason']}: {plan['best']}" if plan['reason'] != plan['best_reason'] else '') + ')\n'
              f"Device: {current['device'] or 'auto'} · renders at a time: {current['processes'] or 'auto'} · "
              f"memory: {str(current['memory_gib']) + ' GiB' if current['memory_gib'] else 'auto'}"
              + (f" ({plan['allowance_gib']} GiB now)" if plan['allowance_gib'] is not None else ''))
    test = current['test']
    if test:
        say(args, f"Speed test {test['utc'][:16].replace('T', ' ')} UTC ({test['elapsed_seconds']:.0f} s):")
        for r in test['results']:
            best = r['best']
            say(args, f"  {r['label']}: " + (f"{best['seconds_per_asset']:.2f} s per test asset, {best['processes']} at a time"
                                             if best else 'not used') + f" ({r['stopped']})" + (' · fastest' if r['key'] == test['chosen'] else ''))
    else:
        say(args, 'Not speed-tested yet: it runs at the start of the next process, or now with: rendering test')
    say(args, 'Devices: ' + ', '.join(f"{d['key']} ({d['label']})" for d in current['devices']))
    return current


def search_line(config):
    from .search_speed import summary
    value = summary(config)
    return f"{value['threads']} of {value['cpu_threads']} ({value['reason']})"


def show_checks(args, result):
    for check in result['checks']:
        mark = {'passed': 'ok  ', 'warning': 'warn', 'failed': 'FAIL'}[check['status']]
        say(args, f"  [{mark}] {check['label']}" + (f": {check['detail']}" if check.get('detail') else ''))
    say(args, {'passed': 'Blender is ready.', 'warning': 'Blender works; see the warning.',
               'failed': 'Blender cannot be used.', 'cancelled': 'Check cancelled.'}[result['status']])


def checklist(args, items, indent='  '):
    for item in items:
        say(args, f"{indent}[{'ok  ' if item['ready'] else 'miss'}] {item['label']}"
                  + (f"\n{indent}       {item['command']}" if item.get('command') else '')
                  + (f" — {item['detail']}" if item.get('detail') and not item['ready'] else ''))


def status_lines(args, config):
    from . import engines, setup_core
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
        checklist(args, value['items'])
    # Search is needed whichever description engine is used, so it is listed on its own.
    device = engines.search_device(config)
    say(args, f"Search on {engines.SEARCH_DEVICES[device]['label']}:")
    checklist(args, env['search_devices'][device])
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
    say(args, '\n3. The storage budget caps the disk space Assetarium uses (its folder, including the library store; '
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
    if choices['search_device'] in status['environment']['search_devices']:
        say(args, '   What search needs on this device (setup installs nothing; run a missing command yourself):')
        checklist(args, status['environment']['search_devices'][choices['search_device']], '   ')
    say(args, '\nReview:\n' + json.dumps({k: v for k, v in choices.items() if k != 'confirm_rerender'}, indent=2, ensure_ascii=False))
    if ask('Save these choices? (yes/no)', 'yes').lower() != 'yes':
        say(args, 'Nothing was saved.')
        return {'status': 'cancelled'}
    choices['skipped_steps'] = skipped
    result = setup_core.save_setup(config, choices)
    say(args, 'Saved.' + (f" {result['blender']['reason']}" if result['blender']['status'] == 'faulty' else '')
              + ' Next: library add PATH, then previews KEY.')
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
    say(args, 'Saved to config.local.toml; the next Make previews uses it.' if saved['status'] == 'saved'
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
        if args.command in {'sources', 'library'}:
            result = sources_command(args, config)
        elif args.command == 'packs':
            result = packs_command(args, config)
        elif args.command in {'previews', 'describe'}:
            result = queue_command(args, config)
        elif args.command == 'queue':
            result = queue_list(args, config)
            result = {**result, 'status': 'ready'}
        elif args.command == 'forget-missing':
            from .library_store import forget_missing
            from .sources import get_source
            source = get_source(config, args.key)
            if not confirm(f"Forget the missing assets in {source['name']}{' under ' + args.pack if args.pack else ''}? Their "
                           "collection entries become unavailable; their results stay until you remove unreferenced results."):
                say(args, 'Nothing was forgotten.')
                return 0
            count = forget_missing(config, source['id'], args.pack)
            say(args, f"Forgot {count} missing asset(s); their recognition history is kept.")
            result = {'status': 'saved', 'forgotten': count}
        elif args.command == 'settings':
            result = settings_command(args, config)
        elif args.command == 'rendering':
            result = rendering_command(args, config)
        elif args.command == 'setup':
            result = setup_command(args, config)
        elif args.command == 'process':
            result = run_operation(args, config, args.command, args.asset_source)
        elif args.command == 'cancel':
            from .source_operations import cancel
            from .sources import bound, get_source
            result = cancel(bound(config, get_source(config, args.asset_source)))
            say(args, result.get('reason') or 'Nothing is running for this source.')
        elif args.command == 'recheck':
            result = recheck_command(args, config)
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
