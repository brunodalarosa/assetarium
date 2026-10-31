"""Check my model (decision 0024): can a local model structure packs through Assetarium's pack tools?

Each synthetic pack tree (``model_check_trees``: names only, tiny stub files) becomes a library folder in a disposable
project under ``scratch/``; the model gets the copy-paste prompt and the six pack tools, and the owner's part is played
by applying what it proposes. The score is the **outcome** (packs, cards, excluded folders, image kinds, structure
status), never the rule text, since different rules can give the same result. The model runs on an OpenAI-compatible
server on this computer only; its history is trimmed so a 4,096-token context fits. Reports go to
``data/evidence/model-check/<run>.json``; nothing in the owner's library or settings is touched.
"""
from dataclasses import replace
import json
from pathlib import Path, PurePosixPath
import shutil
import time
import uuid

from .config import ConfigError

STEPS = 40
BUDGET = 3200  # Estimated prompt tokens kept per request (characters / 3.5), under a 4,096-token context.
RESULT_CHARS = 5000
QUICK = 8
SYSTEM = ('/no_think You organize asset packs in Assetarium with its tools. Follow this procedure: list_packs; for each pack '
          'that needs a structure, get_profile and get_pack_outline (one folder level at a time), then propose_profile with '
          'the whole rule list, or finish_structure when the pack is right as it is. Engine copies (Unity, Godot, URP '
          'folders repeating the same models): engine_copy on the copy. Numbered names are separate models unless the folder '
          'says they are variants. Folders of sprites or icons: image_kind image; folders of material maps: image_kind '
          'texture. A versioned subfolder (v1.2) inside a pack is not a pack of its own: pack merge. When list_packs shows '
          'nothing that needs a structure, answer DONE. Never invent folder names; use those the outline shows.')


def chat_server(url, model, timeout=120):
    """A ``chat(messages, tools)`` function for an OpenAI-compatible server on this computer."""
    from .engine_server import _request, checked_model, checked_url
    base, name = checked_url(url), checked_model(model)
    if not name:
        raise ConfigError('Choose the model the server lists')

    def chat(messages, tools):
        reply = _request(base + '/chat/completions', {'model': name, 'messages': messages, 'tools': tools, 'tool_choice': 'auto',
                                                      'temperature': 0.2, 'max_tokens': 700}, timeout=timeout)
        return reply['choices'][0]['message']
    return chat


def tool_specs():
    from .pack_agent import DESCRIPTIONS, SCHEMAS, TOOLS
    return [{'type': 'function', 'function': {'name': name, 'description': DESCRIPTIONS[name], 'parameters': SCHEMAS[name]}}
            for name in TOOLS]


def _tokens(messages):
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in messages) / 3.5


def trimmed(messages):
    """System and task first, then as many whole recent rounds as fit; older tool results shrink to a line."""
    head, rounds, current = messages[:2], [], []
    for message in messages[2:]:
        if message['role'] == 'assistant' and current:
            rounds.append(current)
            current = []
        current.append(message)
    if current:
        rounds.append(current)
    kept = []
    for index, chunk in enumerate(reversed(rounds)):
        if index >= 2:
            chunk = [dict(m, content='(older result omitted)') if m['role'] == 'tool' else m for m in chunk]
        if _tokens(head + chunk + kept) > BUDGET and kept:
            break
        kept = chunk + kept
    return head + kept


def project(root):
    """A disposable project with its own library store and sources registry (never the owner's)."""
    from .config import Config
    (root / 'project').mkdir(parents=True, exist_ok=True)
    (root / 'trees').mkdir(exist_ok=True)
    config = Config(root / 'project', root / 'trees', None)
    return replace(config, sources_registry=config.project_root / 'data/library/sources.json')


def materialize(config, root, tree):
    """Write a tree's stub files, quick-look them and add the folder; returns its library folder."""
    from . import quick_look, sources
    folder = root / 'trees' / tree['name']
    for path in tree['paths']:
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('v 0 0 0\n' if PurePosixPath(path).suffix.casefold() == '.obj' else 'stub\n', encoding='utf-8')
    job = quick_look.start(config, str(folder))['job']
    while quick_look.status(job)['status'] == 'running':
        time.sleep(0.02)
    source = sources.add(config, str(folder))
    quick_look.save(config, source, job)
    return source, job


def outcome(config, source, paths):
    """What the folder looks like now under its saved answers: packs, cards, excluded folders, image kinds, statuses."""
    from .catalog import IMAGES, MODELS, excluded_folder
    from .library_store import answers
    from .pack_profiles import signals
    from .packs import detect
    from .sources import bound, excluded_folders
    from .variant_groups import assign
    excluded = excluded_folders(bound(config, source))
    kept = [p for p in paths if not any(excluded_folder(f, x) for f in _folders(p) for x in excluded)]
    suffix = lambda p: PurePosixPath(p).suffix.casefold()
    models = [p for p in kept if suffix(p) in MODELS]
    images = [p for p in kept if suffix(p) in IMAGES or suffix(p) == '.svg']
    saved = answers(config, source['id'])
    packs = detect(kept, models + images, [{'path': a['path'], 'value': a['value']} for a in saved if a['kind'] == 'pack'])
    rules = {a['path']: a['value'] for a in saved if a['kind'] == 'variant_axis'}
    by_folder = {}
    for path in models:
        by_folder.setdefault(_parent(path), []).append(path)
    cards = len(images)
    for folder, files in by_folder.items():
        found, _ = assign([(f, folder, PurePosixPath(f).stem, 'model_3d') for f in files], rules)
        cards += len(files) - len(found) + len({k for k, _, _ in found.values()})
    kinds = {a['path']: a['value'] for a in saved if a['kind'] == 'image_kind'}
    status = {pack: value['status'] for pack, value in signals(config, source['key']).items()}
    return {'packs': sorted(packs['packs']), 'cards': cards, 'excluded': sorted(excluded), 'image_kinds': kinds, 'status': status}


def _parent(path):
    parent = PurePosixPath(path).parent.as_posix()
    return '' if parent == '.' else parent


def _folders(path):
    parts = PurePosixPath(path).parts[:-1]
    return ['/'.join(parts[:i]) for i in range(1, len(parts) + 1)]


def score(result, checks):
    """Each gold check against the outcome; a tree passes when every check does."""
    graded = []
    for check in checks:
        kind = check['check']
        if kind == 'packs':
            ok = result['packs'] == sorted(check['equals'])
        elif kind == 'cards':
            ok = result['cards'] == check['equals']
        elif kind == 'excluded':
            ok = any(_covers(result['excluded'], folder) for folder in check['any_of'])
        elif kind == 'kept':
            ok = not _covers(result['excluded'], check['folder'])
        elif kind == 'image_kind':
            ok = result['image_kinds'].get(check['folder']) == check['equals']
        elif kind == 'not_image_kind':
            ok = result['image_kinds'].get(check['folder']) != check['value']
        elif kind == 'settled':
            ok = all(status != 'needs_structure' for status in result['status'].values())
        else:
            raise ConfigError('Unknown check ' + kind)
        graded.append({**check, 'passed': ok})
    return graded


def _covers(excluded, folder):
    return any(folder == x or folder.startswith(x + '/') for x in excluded)


def run_tree(config, root, tree, chat, log):
    """One tree: the model works until it says DONE (or the step limit); pending proposals are applied as the owner would."""
    from .mcp_assets import validate
    from .pack_agent import decide, execute, prompt
    from . import quick_look
    source, job = materialize(config, root, tree)
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt(source)}]
    tools, calls, refused, started, ended = tool_specs(), 0, 0, time.monotonic(), 'step limit'
    for _ in range(STEPS):
        try:
            message = chat(trimmed(messages), tools)
        except Exception as exc:  # A server fault ends this tree; the next one runs (the report keeps the reason).
            ended = f'server fault: {exc}'
            break
        calls_made = message.get('tool_calls') or []
        messages.append({'role': 'assistant', 'content': message.get('content') or '', **({'tool_calls': calls_made} if calls_made else {})})
        log.append({'role': 'assistant', 'content': (message.get('content') or '')[:600], 'tool_calls': calls_made})
        if not calls_made:
            ended = 'answered'
            break
        for call in calls_made:
            calls += 1
            name = call.get('function', {}).get('name')
            try:
                args = json.loads(call['function'].get('arguments') or '{}')
                validate(name, args)
                result = execute(config, name, args, {'name': 'model-check'})
                if result.get('status') == 'pending':  # The owner's part: apply, then read the names again.
                    decide(config, result['proposal_id'], 'apply')
                    quick_look.save(config, source, job)
                    result = dict(result, owner='The owner applied it.')
            except (ConfigError, ValueError, KeyError, TypeError) as exc:
                refused += 1
                result = {'status': 'refused', 'reason': str(exc)[:400]}
            text = json.dumps(result, ensure_ascii=False)[:RESULT_CHARS]
            messages.append({'role': 'tool', 'tool_call_id': call.get('id', ''), 'content': text})
            log.append({'role': 'tool', 'name': name, 'arguments': call.get('function', {}).get('arguments'), 'result': text[:600]})
    found = outcome(config, source, tree['paths'])
    graded = score(found, tree['checks'])
    return {'name': tree['name'], 'family': tree['family'], 'passed': all(c['passed'] for c in graded), 'checks': graded,
            'outcome': found, 'calls': calls, 'refused': calls and refused, 'ended': ended, 'seconds': round(time.monotonic() - started, 1)}


def verdict(passed, total):
    share = passed / total if total else 0
    return ('good' if share >= 0.8 else 'review' if share >= 0.5 else 'weak',
            'Good enough to structure packs on its own' if share >= 0.8 else
            'Usable: review what it proposes' if share >= 0.5 else 'Not recommended for pack structure')


def latest(config):
    """The newest saved report (without its trees), or None."""
    from .publication import read_json
    folder = config.project_root / 'data/evidence/model-check'
    found = sorted((p for p in folder.glob('*.json') if not p.name.endswith('.transcripts.json')),
                   key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    for path in found:
        try:
            report = read_json(path)
        except (OSError, ValueError):
            continue
        return {k: report.get(k) for k in ('run', 'model', 'url', 'mode', 'passed', 'total', 'verdict', 'verdict_text', 'families',
                                           'seconds', 'utc')} | {'report': str(path)}
    return None


class Cancelled(ConfigError):
    """The owner stopped the check; the trees already run are not reported."""


def run(config, url, model, full=False, chat=None, progress=None, run_name=None, cancelled=None):
    """Run the check; returns the report (also saved under data/evidence/model-check/)."""
    from .model_check_trees import trees
    from .publication import atomic_json
    from .engine_server import checked_url
    chosen = trees() if full else [t for t in trees() if t['quick']][:QUICK]
    run_name = run_name or time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    root = config.project_root / 'scratch/model-check' / run_name
    if root.exists():
        raise ConfigError('This check run already exists; use a new name')
    chat = chat or chat_server(url, model)
    disposable = project(root)
    results, transcripts = [], {}
    started = time.monotonic()
    try:
        for index, tree in enumerate(chosen):
            if cancelled and cancelled():
                raise Cancelled('The check was stopped; nothing was saved')
            if progress:
                progress(index, len(chosen), tree['name'])
            log = []
            results.append(run_tree(disposable, root, tree, chat, log))
            transcripts[tree['name']] = log
    finally:
        shutil.rmtree(root, ignore_errors=True)  # scratch/ holds nothing that must last (AGENTS.md).
    passed = sum(r['passed'] for r in results)
    level, text = verdict(passed, len(results))
    report = {'schema_version': 1, 'run': run_name, 'model': model, 'url': checked_url(url) if url else None,
              'mode': 'full' if full else 'quick', 'passed': passed, 'total': len(results), 'verdict': level, 'verdict_text': text,
              'seconds': round(time.monotonic() - started, 1), 'trees': results,
              'families': {f: [sum(r['passed'] for r in results if r['family'] == f), sum(r['family'] == f for r in results)]
                           for f in sorted({r['family'] for r in results})},
              'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    out = config.project_root / 'data/evidence/model-check'
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(out / f'{run_name}.json', report)
    atomic_json(out / f'{run_name}.transcripts.json', transcripts)
    report['report'] = str(out / f'{run_name}.json')
    return report
