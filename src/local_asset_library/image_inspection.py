"""Static image inspection: decode once, measure, and write bounded derived images.

No Blender and no original copies. Derived thumbnails, SVG rasters and model
inputs live in the source's generated data and are hash-verified before reuse.
Animated/external-resource content is recorded unsupported, not retried.
"""
import hashlib
import os
from pathlib import Path

from .catalog import digest
from .config import ConfigError
from .retrieval import source_check, preview_file

VERSION = 'image-inspection-v2'


def code_files(config):
    # Only the code that produces facts and derived pixels; this orchestration and the
    # scanner rules can change without re-inspecting images (VERSION marks semantic changes).
    return {name: Path(__file__).with_name(name + '.py') for name in ('image_media', 'svg_worker')}


def renderer_version():
    import importlib.metadata
    try:
        return importlib.metadata.version('resvg-py')
    except importlib.metadata.PackageNotFoundError:
        return None


def inspection_input(config, record, content_only=False, recorded=None):
    from .image_media import ACTIVE, POLICIES, PREFERENCE, image_format
    from .incremental import recorded_fingerprint
    from .publication import verified_hash
    source_check(config, record)  # Refuses stale or unavailable files; the key below holds content only.
    available = [f for f in record['files'] if f['availability'] == 'available' and image_format(f['path'])]
    if not available:
        raise ConfigError('No decodable image file is recorded for this asset')
    source = min(available, key=lambda f: (PREFERENCE.index(image_format(f['path'])), f['path']))
    reason = 'Preferred raster export' if source['format'] != 'svg' else 'Self-contained SVG export'
    # Content, never the path (decision 0023): a moved or duplicated image keeps its derived images.
    value = {'adapter': VERSION, 'files': sorted(f['sha256'] for f in record['files'] if f['availability'] == 'available'),
             'format': source['format'], 'sha256': source['sha256']}
    if content_only:
        return {'asset_id': record['asset_id'], 'files': record['files']}, source, reason, digest(value)
    files = code_files(config)
    value.update(policy=POLICIES[ACTIVE], **{name: verified_hash(path) for name, path in files.items()})
    if source['format'] == 'svg':
        value['renderer'] = renderer_version()
    fingerprint = recorded_fingerprint(value, files, recorded)
    return {'asset_id': record['asset_id'], 'files': record['files']}, source, reason, fingerprint


def validate_result(config, record):
    inspection_input(config, record)
    if not record['previews']:
        raise ConfigError('Completed image inspection has no verified derived image')
    for preview in record['previews']:
        preview_file(config, preview)


def save(config, relative, name, image):
    from .image_media import png_bytes
    blob = png_bytes(image)
    path = config.output_path('data', f'{relative}/{name}')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(blob)
    os.replace(temporary, path)
    return {'path': f'data/{relative}/{name}', 'sha256': hashlib.sha256(blob).hexdigest()}


def run(config, record, fingerprint):
    from .image_media import UnsupportedMedia, decode, model_input, thumbnail
    from .incremental import update_record
    _, source, reason, current = inspection_input(config, record, recorded=fingerprint)
    if current != fingerprint:
        raise ConfigError('Image input changed before inspection')
    path = config.source_file(source['path'])
    try:
        rgba, measured = decode(path, source['format'])
    except UnsupportedMedia as exc:
        record.update(primary_inspection_path=source['path'], primary_inspection_reason=reason, previews=[])
        record['processing'].update(inspection='unsupported', previews='unsupported')
        record.setdefault('stage_faults', {})['inspection'] = {'status': 'unsupported', 'kind': 'unsupported_media', 'reason': str(exc)}
        record['inspection_run'] = {'status': 'unsupported', 'fingerprint': fingerprint, 'adapter': VERSION,
                                    'source_faults': [], 'errors': [str(exc)]}
        update_record(config, record)
        return {'status': 'unsupported', 'adapter': VERSION, 'reason': str(exc)}
    from .result_store import result_path
    relative = result_path('inspection', fingerprint)
    previews = []
    if source['format'] == 'svg':
        previews.append({**save(config, relative, 'display.png', rgba), 'view_label': 'image', 'origin': 'derived',
                         'role': 'display', 'derivation': {'kind': 'svg-raster', **measured['vector']}})
    else:
        previews.append({'source_path': source['path'], 'sha256': source['sha256'], 'view_label': 'image',
                         'origin': 'source', 'role': 'original'})
    image, info = thumbnail(rgba)
    previews.append({**save(config, relative, 'thumbnail.png', image), 'view_label': 'thumbnail', 'origin': 'derived',
                     'role': 'thumbnail', 'derivation': {'kind': 'thumbnail', **info}})
    fault = None
    try:
        image, derivation = model_input(rgba)
        previews.append({**save(config, relative, 'model-input.png', image), 'view_label': 'model_input',
                         'origin': 'derived', 'role': 'model_input', 'derivation': derivation})
    except ConfigError as exc:
        fault = str(exc)
    # Recheck the source after decoding; a change during inspection is a fault, not a result.
    if inspection_input(config, record, recorded=fingerprint)[3] != fingerprint:
        raise ConfigError('Image source changed during inspection')
    technical = {'version': 2, 'kind': 'image', **measured, 'inspected_path': source['path'],
                 'inspected_sha256': source['sha256'], 'inspected_format': source['format'], 'adapter': VERSION}
    record.update(technical=technical, primary_inspection_path=source['path'], primary_inspection_reason=reason,
                  previews=previews)
    record['processing'].update(inspection='complete', previews='partial' if fault else 'complete')
    faults = record.setdefault('stage_faults', {})
    faults.pop('previews', None)
    if fault:
        faults['previews'] = faults['embeddings'] = {'status': 'failed', 'kind': 'model_input', 'reason': fault}
        record['processing']['embeddings'] = 'failed'
    record['inspection_run'] = {'status': 'complete', 'fingerprint': fingerprint, 'adapter': VERSION,
                                'source_faults': [], 'errors': [fault] if fault else []}
    update_record(config, record)
    return {'status': 'complete', 'adapter': VERSION, 'source_path': source['path']}
