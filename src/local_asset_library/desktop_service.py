"""Read-only presentation operations; retrieval policy remains in AssetService/SearchEngine."""
from contextlib import closing
import hashlib
import time

from .catalog import read_database
from .caption_quality import caption_quality, caption_summary
from .config import ConfigError
from .mcp_assets import AssetService, FORMATS, MODES, VIEWS, error_payload, validate
from .retrieval import current_overlay, matches, observations, pilot_records, source_check


class DesktopService(AssetService):
    def __init__(self, config):
        super().__init__(config)
        self.preview_faults = {}
        self.item_faults = {}

    def _record_fault(self, identifier, channel, reason):
        fault = {'asset_id': identifier, 'status': 'faulty', 'channel': channel, 'reason': str(reason)}
        self.item_faults[(identifier, channel)] = fault
        return fault

    def context(self):
        records = pilot_records(self.config)
        with closing(read_database(self.config)) as db:
            total = db.execute('SELECT COUNT(*) FROM assets').fetchone()[0]
        hashes = {}
        for name, relative in (('catalog', 'catalog.sqlite'), ('index', 'embeddings/index.sqlite'),
                               ('pilot', 'pilot/selection-manifest.json')):
            hashes[name] = hashlib.sha256(self.config.output_path('data', relative).read_bytes()).hexdigest()
        return {'pilot_count': len(records), 'inventory_count': total,
                'packs': sorted({r['pack_id'] for r in records}),
                'formats': sorted({f['format'] for r in records for f in r['files'] if f['format'] in FORMATS}),
                'modes': MODES, 'views': VIEWS, 'versions': hashes}

    def browse(self, filters=None):
        filters = {} if filters is None else filters
        # Same validation and measured-filter implementation as search; never an empty semantic query.
        validate('search_assets', {'query': 'browse', 'mode': 'keyword', 'filters': filters})
        records = pilot_records(self.config)
        items = []
        for record in sorted(records, key=lambda r: (r['pack_id'], r['display_name'].casefold(), r['asset_id'])):
            if not matches(record, filters):
                continue
            identifier = record['asset_id']
            faults = list((record.get('inspection_run') or {}).get('source_faults', []))
            available = True
            try:
                if (identifier, 'source') in self.item_faults:
                    raise ConfigError(self.item_faults[(identifier, 'source')]['reason'])
                source_check(self.config, record)
            except (OSError, ValueError) as exc:
                available = False
                faults.append(self._record_fault(identifier, 'source', exc))
            try:
                overlay = current_overlay(self.config, record) or {}
                owner_review = overlay.get('caption_review', 'pending')
            except (OSError, ValueError) as exc:
                owner_review = 'faulty'
                faults.append(self._record_fault(identifier, 'owner_correction', exc))
            items.append({'asset_id': identifier, 'name': record['display_name'], 'pack': record['pack_id'],
                'formats': sorted({f['format'] for f in record['files']}),
                'views': [v for v in VIEWS if any(p.get('view_label') == v for p in record['previews'])],
                'availability': 'available' if available else 'faulty', 'faults': faults,
                'source_faulty': bool(faults), **caption_summary(self.config, record),
                'caption_owner_review': owner_review})
        return {'status': 'browse', 'pilot_count': len(records), 'shown_count': len(items), 'items': items,
                'faults': list(self.item_faults.values()), 'model_loaded': False}

    def asset(self, identifier, source_format=None, view='three_quarter'):
        started = time.perf_counter()
        args = {'asset_id': identifier, 'include_metadata': True, 'include_preview': True, 'preview_view': view}
        if source_format is not None:
            args['source_format'] = source_format
        validate('get_asset', args)
        record = self.record(identifier)
        cache_key = (identifier, view)
        retained = self.preview_faults.get(cache_key)
        if retained:
            args['include_preview'] = False
        try:
            if (identifier, 'source') in self.item_faults:
                raise ConfigError(self.item_faults[(identifier, 'source')]['reason'])
            payload, image, evidence = self.execute('get_asset', args)
        except (OSError, ValueError) as exc:
            payload, image, evidence = error_payload(exc, identifier), None, {'fault': str(exc)}
            self._record_fault(identifier, 'detail', exc)
        if retained:
            payload['preview'] = retained
        elif payload.get('preview', {}).get('status') == 'faulty':
            self.preview_faults[cache_key] = payload['preview']
            self._record_fault(identifier, 'preview:' + view, payload['preview']['reason'])
        try:
            effective = observations(self.config, record)
            owner = current_overlay(self.config, record) or {}
        except (OSError, ValueError) as exc:
            effective, owner = None, {'caption_review': 'faulty'}
            self._record_fault(identifier, 'owner_correction', exc)
        technical = record.get('technical') or {}
        payload['presentation'] = {'name': record['display_name'], 'pack': record['pack_id'],
            'formats': sorted({f['format'] for f in record['files']}),
            'views': [v for v in VIEWS if any(p.get('view_label') == v for p in record['previews'])],
            'observations': effective,
            'suggested_uses': owner.get('suggested_uses') if owner.get('suggested_uses') is not None else record.get('suggested_uses'),
            'owner_review': owner.get('caption_review', 'pending'),
            'owner_artistic_approval': owner.get('artistic_suitability', 'pending'),
            **caption_summary(self.config, record),
            'caption_quality': caption_quality(self.config, record),
            'technical': {k: technical.get(k) for k in ('inspected_path', 'inspected_format', 'inspected_sha256',
                'original_geometry_totals', 'evaluated_instance_totals', 'unit_settings', 'armatures', 'actions',
                'world_bounds', 'objects', 'meshes', 'materials')},
            'processing': record['processing'], 'license_evidence': record.get('license_evidence'),
            'source_faults': (record.get('inspection_run') or {}).get('source_faults', []),
            'caption_faults': (record.get('caption_provenance') or {}).get('visual_faults', []),
            'dependencies': record.get('dependencies', []),
            'faults': [f for (asset, _), f in self.item_faults.items() if asset == identifier],
            'scale': 'Unknown physical scale; measurements apply only to the inspected format.'}
        return {'payload': payload, 'image': image, 'evidence': evidence, 'elapsed_seconds': time.perf_counter() - started}
