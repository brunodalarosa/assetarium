"""Bounded, read-only delivery to the offline, sandboxed Online 3D Viewer frame."""
import base64
from functools import lru_cache
import hashlib
import json
from pathlib import Path, PurePosixPath
import secrets
import time

from .catalog import digest, encoded
from .config import ConfigError
from .publication import generation, pinned
from .retrieval import resolved_detail

FORMATS = frozenset({'glb', 'gltf', 'fbx', 'obj', 'dae', 'stl'})
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_FILES = 64
TICKET_SECONDS = 600


def basename(value):
    return PurePosixPath(value.replace('\\', '/')).name


@lru_cache(maxsize=1)
def viewer_shell():
    """Bundle unchanged upstream releases without a server or runtime downloads."""
    ui = Path(__file__).with_name('ui')
    vendor = ui / 'vendor'
    viewer = vendor / 'online3dviewer-0.18.0'
    shell = (ui / 'viewer.html').read_text(encoding='utf-8')
    environment = ['data:image/jpeg;base64,' + base64.b64encode(
        (viewer / 'envmaps/citadella' / (face + '.jpg')).read_bytes()).decode('ascii')
        for face in ('posx', 'negx', 'posy', 'negy', 'posz', 'negz')]
    replacements = {
        '/* VIEWER_LIBRARY */': (viewer / 'o3dv.min.js').read_text(encoding='utf-8'),
        '/* DRACO_LIBRARY */': (vendor / 'draco-1.5.7/draco_decoder.js').read_text(encoding='utf-8'),
        '/* VIEWER_SCRIPT */': (ui / 'viewer.js').read_text(encoding='utf-8'),
        '/* ENVIRONMENT_MAP */': json.dumps(environment),
        '/* DRACO_WASM */': json.dumps(base64.b64encode(
            (vendor / 'draco-1.5.7/draco_decoder.wasm').read_bytes()).decode('ascii')),
    }
    for marker, content in replacements.items():
        shell = shell.replace(marker, content.replace('</script', '<\\/script'))
    return {'status': 'ready', 'html': shell, 'viewer_version': '0.18.0'}


class InteractivePreviewService:
    def __init__(self, service):
        self.service = service
        self.config = service.config
        self.tickets = {}
        self.fault_path = self.config.output_path('data', 'gui/interactive-preview-faults.jsonl')
        self.faults = {}
        self.evidence_fault = None
        if self.fault_path.exists():
            try:
                for line in self.fault_path.read_text(encoding='utf-8').splitlines():
                    if line.strip():
                        fault = json.loads(line)
                        self.faults[fault['fingerprint']] = fault
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.evidence_fault = 'Saved 3D preview fault evidence could not be read: ' + str(exc)

    def _record_fault(self, identity, reason, missing_files=None):
        key = identity['fingerprint']
        if key not in self.faults:
            fault = {k: identity[k] for k in ('fingerprint', 'asset_id', 'format')}
            fault.update(status='faulty', channel='interactive_preview', reason=str(reason)[:1200],
                         missing_files=[str(p)[:500] for p in (missing_files or [])[:64]],
                         time=time.time(), originals_modified=False)
            self.fault_path.parent.mkdir(parents=True, exist_ok=True)
            with self.fault_path.open('a', encoding='utf-8') as stream:
                stream.write(encoded(fault) + '\n')
            self.faults[key] = fault
        return dict(self.faults[key], retained=True)

    @pinned
    def prepare(self, asset_id, source_format, expected_version):
        if self.evidence_fault:
            return {'status': 'faulty', 'reason': self.evidence_fault, 'retained': True}
        if expected_version != generation(self.config):
            return {'status': 'stale', 'reason': 'Library changed; refresh the inspection card.'}
        record = self.service.record(asset_id)
        if source_format not in {f['format'] for f in record['files']}:
            raise ConfigError('Requested source format is not available')
        identity = {'asset_id': asset_id, 'format': source_format,
                    'fingerprint': digest({'asset_id': asset_id, 'format': source_format,
                        'files': record['files'], 'dependencies': record.get('dependencies', []),
                        'texture_repair': record.get('texture_repair')})}
        if identity['fingerprint'] in self.faults:
            return dict(self.faults[identity['fingerprint']], retained=True)
        try:
            if source_format not in FORMATS:
                raise ConfigError(source_format.upper() + ' is not supported by the interactive viewer. Choose another source format.')
            resolved = resolved_detail(self.config, asset_id, source_format)
            source = resolved['selected_source']
            # Follow only dependencies of the selected export, including MTL -> textures.
            needed, dependencies = {source['path']}, []
            pending = list(resolved['dependencies'])
            while pending:
                added = False
                for dep in pending[:]:
                    if dep.get('from') and dep['from'] not in needed:
                        continue
                    pending.remove(dep)
                    if dep.get('required_for_render') is False:
                        continue
                    if dep.get('status') != 'available' or not dep.get('path'):
                        raise ConfigError('Interactive preview dependency is unavailable')
                    dependencies.append(dep)
                    needed.add(dep['path'])
                    added = True
                if not added:
                    break
            entries = [dict(source, aliases=[basename(source['path'])])]
            for dep in dependencies:
                aliases = [basename(dep['path'])]
                if dep.get('reference'):
                    aliases.append(basename(dep['reference']))
                for binding in dep.get('texture_overrides', []):
                    if binding.get('original_path'):
                        aliases.append(basename(binding['original_path']))
                entries.append(dict(dep, aliases=aliases))
            # Preserve approved mappings in memory; never rewrite an original model.
            for override in resolved.get('texture_overrides', []):
                if (record.get('texture_repair') or {}).get('source_path') == source['path']:
                    entries.append(dict(override, aliases=[basename(override['path']),
                        basename(override.get('original_path') or override['path'])]))
            files, aliases, by_path = [], {}, {}
            total = 0
            for entry in entries:
                path = self.config.source_file(entry['path'])
                size = path.stat().st_size
                if size > MAX_FILE_BYTES:
                    raise ConfigError('Interactive preview file exceeds the 64 MiB limit: ' + path.name)
                if entry['path'] not in by_path:
                    if len(files) >= MAX_FILES:
                        raise ConfigError('Interactive preview exceeds the 64-file limit')
                    total += size
                    if total > MAX_TOTAL_BYTES:
                        raise ConfigError('Interactive preview package exceeds the 128 MiB limit')
                    by_path[entry['path']] = len(files)
                    files.append({'path': entry['path'], 'sha256': entry['sha256'],
                                  'size': size, 'aliases': []})
                item = files[by_path[entry['path']]]
                for alias in entry['aliases']:
                    if not alias or len(alias) > 255:
                        raise ConfigError('Invalid interactive preview filename')
                    previous = aliases.get(alias.casefold())
                    if previous and previous != item['sha256']:
                        raise ConfigError('Ambiguous dependency filename in interactive preview: ' + alias)
                    aliases[alias.casefold()] = item['sha256']
                    if len(aliases) > 128:
                        raise ConfigError('Interactive preview exceeds the 128 filename-alias limit')
                    if alias not in item['aliases']:
                        item['aliases'].append(alias)
            # Only the active inspection owns a package; tickets never grant arbitrary paths.
            self.tickets = {k: v for k, v in self.tickets.items() if time.monotonic() - v['created'] < TICKET_SECONDS}
            if len(self.tickets) >= 4:
                self.tickets.pop(next(iter(self.tickets)))
            ticket = secrets.token_hex(24)
            self.tickets[ticket] = {**identity, 'generation': expected_version,
                                   'created': time.monotonic(), 'files': files}
            return {'status': 'ready', 'ticket': ticket, 'format': source_format,
                    'source_name': basename(source['path']), 'total_bytes': total,
                    'files': [{k: f[k] for k in ('size', 'sha256', 'aliases')} for f in files],
                    'texture_overrides': bool(resolved.get('texture_overrides')),
                    'dependency_completeness': 'Known dependencies only; the viewer reports unresolved references.'}
        except (OSError, ValueError, KeyError) as exc:
            return self._record_fault(identity, str(exc))

    def _ticket(self, ticket, allow_expired=False):
        item = self.tickets.get(ticket) if isinstance(ticket, str) else None
        if item is None or (not allow_expired and time.monotonic() - item['created'] >= TICKET_SECONDS):
            raise ConfigError('Interactive preview session expired; reopen the inspection card.')
        return item

    @pinned
    def file(self, ticket, index):
        item = self._ticket(ticket)
        if item['fingerprint'] in self.faults:
            return dict(self.faults[item['fingerprint']], retained=True)
        if item['generation'] != generation(self.config):
            return {'status': 'stale', 'reason': 'Library changed during preview loading; refresh the inspection card.'}
        # Recheck authorization after disabling/removing sources, even for an issued ticket.
        self.service.record(item['asset_id'])
        if type(index) is not int or not 0 <= index < len(item['files']):
            raise ConfigError('Invalid interactive preview file index')
        entry = item['files'][index]
        try:
            with self.config.open_source(entry['path']) as stream:
                content = stream.read(MAX_FILE_BYTES + 1)
            if len(content) != entry['size'] or hashlib.sha256(content).hexdigest() != entry['sha256']:
                raise ConfigError('Interactive preview source changed after publication: ' + basename(entry['path']))
            return {'status': 'ready', 'content': base64.b64encode(content).decode('ascii')}
        except (OSError, ValueError) as exc:
            return self._record_fault(item, str(exc))

    def fault(self, ticket, reason, missing_files=None):
        if not isinstance(reason, str) or not reason or len(reason) > 1200:
            raise ConfigError('Invalid interactive preview fault')
        if missing_files is not None and (not isinstance(missing_files, list) or
                len(missing_files) > 64 or any(not isinstance(p, str) for p in missing_files)):
            raise ConfigError('Invalid missing-file evidence')
        return self._record_fault(self._ticket(ticket, allow_expired=True), reason, missing_files)

    def release(self, ticket):
        if isinstance(ticket, str):
            self.tickets.pop(ticket, None)
        return {'status': 'released'}
