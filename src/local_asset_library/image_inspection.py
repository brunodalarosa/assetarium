"""Bounded PNG proof of type dispatch. No source enrollment or image captioning."""
from .catalog import digest
from .config import ConfigError
from .retrieval import source_check, preview_file

VERSION = 'png-inspection-v1'


def inspection_input(config, record):
    source_check(config, record)
    source = next((f for f in record['files'] if f['format'] == 'png' and f['availability'] == 'available'), None)
    if source is None:
        raise ConfigError('The foundation image adapter supports explicit PNG records only')
    return {'asset_id': record['asset_id'], 'files': record['files']}, source, 'Explicit PNG source', digest({
        'adapter': VERSION, 'source': source_check(config, record), 'path': source['path']})


def validate_result(config, record):
    inspection_input(config, record)
    for preview in record['previews']:
        preview_file(config, preview)
    if not record['previews']:
        raise ConfigError('Completed image inspection has no verified still image')


def run(config, record, fingerprint):
    from PIL import Image
    from .incremental import update_record
    _, source, reason, current = inspection_input(config, record)
    if current != fingerprint:
        raise ConfigError('Image input changed before inspection')
    path = config.source_file(source['path'])
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ConfigError('PNG exceeds the 16 MiB decode cap')
    try:
        with Image.open(path) as image:
            if image.format != 'PNG' or image.width * image.height > 16000000:
                raise ConfigError('Unsupported image encoding or pixel cap exceeded')
            image.load()
            technical = {'version': 1, 'kind': 'image', 'width': image.width, 'height': image.height,
                         'mode': image.mode, 'inspected_path': source['path'],
                         'inspected_sha256': source['sha256'], 'inspected_format': 'png', 'adapter': VERSION}
    except Image.DecompressionBombError as exc:
        raise ConfigError('PNG exceeds the pixel decode cap') from exc
    # Recheck source/dependencies after decode; no original or derived image copy.
    inspection_input(config, record)
    record.update(technical=technical, primary_inspection_path=source['path'], primary_inspection_reason=reason,
                  previews=[{'source_path': source['path'], 'sha256': source['sha256'], 'view_label': 'image', 'origin': 'supplied'}])
    record['processing'].update(inspection='complete', previews='complete')
    record['inspection_run'] = {'status': 'complete', 'fingerprint': fingerprint, 'adapter': VERSION,
                                'source_faults': [], 'errors': []}
    update_record(config, record)
    return {'status': 'complete', 'adapter': VERSION, 'source_path': source['path']}
