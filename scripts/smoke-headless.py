"""Portable headless smoke check, CLI and STDIO MCP only, in an isolated throwaway project.

Copies this checkout's code into scratch/smoke/<run-name>/project and links its
prepared base and mcp environments (nothing is installed, the owner's library is
never touched), registers a synthetic source and drives everything through
scripts/local-assets.ps1 or .sh: settings, sources, Process assets with real
Blender, failures, refresh, collection exports and the deletion guard, plus
search_assets / get_asset / edit_collection over STDIO. The embedding environment
is deliberately not linked, so the image-vector stage stays a recorded fault and
the report says so. Report: data/smoke/<run-name>/report.json
"""
import argparse
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not re.fullmatch('[a-z0-9-]{1,40}', args.run_name):
    raise SystemExit('Invalid run name')
out = ROOT / 'data/smoke' / args.run_name
out.mkdir(parents=True, exist_ok=False)
base = ROOT / 'scratch/smoke' / args.run_name
project, assets = base / 'project', base / 'assets'
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
report = {'status': 'running', 'platform': sys.platform, 'project': str(project), 'checks': [], 'unverified': [], 'commands': []}


def build():
    skip = shutil.ignore_patterns('__pycache__', '*.pyc')
    for name in ('src', 'scripts', 'runtime', 'prompts'):
        shutil.copytree(ROOT / name, project / name, ignore=skip)
    (project / 'docs').mkdir()
    for name in ('pyproject.toml', 'uv.lock', 'config.example.toml',
                 'docs/caption-model.json', 'docs/embedding-model.json'):  # What a fresh clone has.
        shutil.copy2(ROOT / name, project / name)
    # Nothing is installed. .venv is a storage area that must resolve inside the project, so
    # it is a hard-linked copy (same files, read only by convention); .venv-mcp is a directory link.
    shutil.copytree(ROOT / '.venv', project / '.venv', symlinks=True, copy_function=os.link)
    if os.name == 'nt':
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(project / '.venv-mcp'), str(ROOT / '.venv-mcp')], capture_output=True)
        if made.returncode:
            raise RuntimeError(made.stderr.decode(errors='replace'))
    else:
        (project / '.venv-mcp').symlink_to(ROOT / '.venv-mcp', target_is_directory=True)
    assets.mkdir()
    cube = 'v -1 -1 -1\nv 1 -1 -1\nv 1 1 -1\nv -1 1 -1\nv -1 -1 1\nv 1 -1 1\nv 1 1 1\nv -1 1 1\nf 1 4 3 2\nf 5 6 7 8\nf 1 2 6 5\nf 2 3 7 6\nf 3 4 8 7\nf 4 1 5 8\n'
    # Unrelated synthetic names (decision 0009).
    (assets / 'lantern-quartz.obj').write_text(cube, encoding='utf-8')
    (assets / 'pebble-marsh.obj').write_text(cube.replace('1 1 1', '1 1 2'), encoding='utf-8')


def cli(*words, expect=0, owner=True):
    wrapper = (['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(project / 'scripts/local-assets.ps1')]
               if os.name == 'nt' else ['sh', str(project / 'scripts/local-assets.sh')])
    done = subprocess.run([*wrapper, *(['--json'] if owner else []), *words], cwd=project, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', stdin=subprocess.DEVNULL, timeout=1200, creationflags=NO_WINDOW)
    record = {'command': ' '.join(words), 'exit': done.returncode, 'stderr': done.stderr[-400:]}
    report['commands'].append(record)
    try:
        value = json.loads(done.stdout)
    except ValueError:
        value = {'raw': done.stdout[-800:]}
    record['status'] = value.get('status')
    if done.returncode != expect:
        raise RuntimeError(f'{record["command"]}: exit {done.returncode}, expected {expect}: {done.stdout[-400:]} {done.stderr[-400:]}')
    return value


class Wire:
    """The real client launch: the mcp interpreter running scripts/asset-mcp.py over STDIO."""
    def __init__(self, log):
        python = project / ('.venv-mcp/Scripts/python.exe' if os.name == 'nt' else '.venv-mcp/bin/python')
        self.stderr = log.open('w', encoding='utf-8')
        self.process = subprocess.Popen([str(python), str(project / 'scripts/asset-mcp.py')], cwd=project,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, text=True, encoding='utf-8', creationflags=NO_WINDOW)
        self.lines, self.sequence = queue.Queue(), 0
        threading.Thread(target=lambda: [self.lines.put(l) for l in self.process.stdout] + [self.lines.put(None)], daemon=True).start()
        self.send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'lal-smoke', 'version': '1'}})
        self.send('notifications/initialized', notification=True)

    def send(self, method, params=None, notification=False):
        message = {'jsonrpc': '2.0', 'method': method, **({'params': params} if params is not None else {})}
        if not notification:
            self.sequence += 1
            message['id'] = self.sequence
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()
        while not notification:
            line = self.lines.get(timeout=120)
            if line is None:
                raise RuntimeError('MCP server exited; see mcp-stderr.log')
            reply = json.loads(line)
            if reply.get('id') == self.sequence:
                return reply['result']

    def call(self, name, arguments):
        result = self.send('tools/call', {'name': name, 'arguments': arguments})
        if result.get('isError'):
            raise RuntimeError(f'{name} returned an error: {result}')
        return json.loads(result['content'][0]['text'])

    def close(self):
        self.process.stdin.close()
        code = self.process.wait(timeout=30)
        self.stderr.close()
        if code:
            raise RuntimeError(f'MCP server exit code {code}')


try:
    build()
    original = {p.name: p.read_bytes() for p in assets.iterdir()}
    cli('settings', 'set', '--formats', 'obj,gltf')
    added = cli('sources', 'add', str(assets))
    key = added['source']['key']
    assert added['status'] == 'complete', added
    report['checks'].append('settings set and sources add (scan) through the CLI')
    listed = cli('sources', 'list')
    assert listed['sources'][0]['pending'] == 2, listed
    processed = cli('process', '--asset-source', key, expect=1)  # The unlinked embedding stage must fail visibly.
    report['process'] = {k: processed.get(k) for k in ('status', 'phase', 'reason')}
    report['unverified'].append({'stage': 'embeddings', 'status': processed['status'], 'reason': processed.get('reason'),
                                 'why': 'embedding environment deliberately not linked'})
    report['checks'].append(f"process ran real Blender inspection; operation ended {processed['status']} (recorded, not hidden)")
    cli('refresh', '--asset-source', key, owner=False)  # Publish usable partial results (the app's Refresh published view).
    status = cli('sources', 'list')['sources'][0]
    report['source_status'] = {k: status.get(k) for k in ('pending', 'failed', 'reason', 'descriptions')}
    previews = sorted((project / 'data/library-store/results').rglob('*.png'))
    assert len(previews) >= 6 and all(p.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n' for p in previews), previews
    report['checks'].append(f'{len(previews)} preview PNGs rendered into the library store; published with refresh')
    failures = cli('failures')
    report['failures'] = {'assets': failures['assets'], 'paths': len(failures['paths'])}
    for word in ('disable', 'enable'):
        cli('sources', word, key)
    cli('packs', 'list', key)
    cli('queue', 'list')
    report['checks'].append('sources disable / enable, packs list, queue list and failures, through the CLI')
    wire = Wire(out / 'mcp-stderr.log')
    try:
        found = wire.call('search_assets', {'query': 'lantern', 'mode': 'keyword', 'limit': 5})
        asset = found['results'][0]['asset_id']
        assert found['results'][0]['name'] == 'lantern-quartz', found
        assert wire.call('get_asset', {'asset_id': asset})['asset_id'] == asset
        made = wire.call('edit_collection', {'action': 'create', 'name': 'Smoke shelf', 'asset_ids': [asset]})
        report['checks'].append('STDIO MCP: search_assets (keyword), get_asset, edit_collection create')
    finally:
        wire.close()
    collection = made['collection_id']
    assert any(c['collection_id'] == collection for c in cli('collections', 'list')['collections'])
    exported = {kind: cli('collections', 'export', collection, '--format', kind) for kind in ('json', 'md', 'png')}
    assert all(Path(e['path']).is_file() and Path(e['path']).stat().st_size for e in exported.values()), exported
    report['exports'] = {k: {'path': v['path'], 'files': v['files']} for k, v in exported.items()}
    report['checks'].append('collections list and export json / md / png through the CLI')
    cli('collections', 'delete', collection, expect=2)
    cli('sources', 'remove', key, expect=2)
    assert any(c['collection_id'] == collection for c in cli('collections', 'list')['collections'])
    report['checks'].append('Without an interactive terminal, collections delete and sources remove are refused (exit 2)')
    assert all(p.read_bytes() == original[p.name] for p in assets.iterdir() if p.is_file())
    report['checks'].append('Original fixture bytes unchanged')
    report['status'] = 'passed'
except BaseException as exc:
    report.update(status='faulty', reason=f'{type(exc).__name__}: {exc}')
    raise
finally:
    from scratch_links import release
    release(project / '.venv-mcp')  # scratch/ stays safe to delete (AGENTS.md).
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(out / 'report.json'), 'reason': report.get('reason'),
                      'unverified': report['unverified']}, indent=2), flush=True)
