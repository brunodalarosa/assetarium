"""Read-only presentation operations; retrieval policy remains in AssetService/SearchEngine."""
from contextlib import closing
import hashlib
import time

from .catalog import read_database
from .caption_quality import caption_quality, caption_summary
from .config import ConfigError
from .mcp_assets import AssetService, FORMATS, MODES, VIEWS, error_payload, validate
from .retrieval import current_overlay, matches, observations, pilot_records, source_check
from .publication import pinned, generation,read_json


class DesktopService(AssetService):
    def __init__(self, config):
        super().__init__(config)
        self.preview_faults = {}
        self.item_faults = {}
        self.version = None
        self.preview_bindings = {}

    def preview_binding(self, identifier, view):
        from .catalog import digest
        from .captions import file_hash
        record=self.record(identifier)
        item=next((p for p in record['previews'] if p.get('view_label')==view),None)
        if item is None:
            return digest({'asset':identifier,'view':view,'missing':True})
        try:
            path=self.config.source_file(item['source_path']) if item.get('source_path') else self.config.output_path('data',item['path'].removeprefix('data/'))
            actual=file_hash(path)
        except (OSError,ValueError,KeyError) as exc:
            actual={'unavailable':str(exc)}
        return digest({'asset':identifier,'view':view,'path':item.get('path',item.get('source_path')),
                       'expected':item.get('sha256'),'actual':actual})

    def synchronize(self):
        version = generation(self.config)
        if version != self.version:
            for key in list(self.preview_faults):
                try:
                    unchanged=self.preview_bindings.get(key)==self.preview_binding(*key)
                except (OSError,ValueError):
                    unchanged=False
                if not unchanged:
                    self.preview_faults.pop(key,None)
                    self.preview_bindings.pop(key,None)
            self.item_faults.clear()
            self.query_faults.clear()
            self.version = version
        return version

    def _record_fault(self, identifier, channel, reason):
        fault = {'asset_id': identifier, 'status': 'faulty', 'channel': channel, 'reason': str(reason)}
        self.item_faults[(identifier, channel)] = fault
        return fault

    @pinned
    def context(self):
        version = self.synchronize()
        records = pilot_records(self.config)
        with closing(read_database(self.config)) as db:
            total = db.execute('SELECT COUNT(*) FROM assets').fetchone()[0]
        hashes = {}
        from .membership import membership
        scope=membership(self.config)
        membership_path='library/membership.json' if scope.get('scope')=='library' else 'pilot/selection-manifest.json'
        for name, relative in (('catalog', 'catalog.sqlite'), ('index', 'embeddings/index.sqlite'),
                               ('membership', membership_path)):
            hashes[name] = hashlib.sha256(self.config.output_path('data', relative).read_bytes()).hexdigest()
        hashes['pilot']=hashes['membership']  # Historical UI key; current membership digest is authoritative.
        from .incremental import coverage
        import json
        from .incremental import working
        progress_path = self.config.output_path('data','library/processing-status.json')
        progress = read_json(progress_path) if progress_path.exists() else {'status':'idle'}
        if progress.get('status') == 'running' and progress.get('pid'):
            from .gpu_queue import process_alive
            if not process_alive(progress['pid']):
                progress = {**progress, 'status':'interrupted',
                            'reason':'Worker stopped; use Process pending to resume completed checkpoints.'}
        pending_coverage = coverage(working(self.config)) if working(self.config).output_path('data','catalog.sqlite').exists() else None
        return {'pilot_count': len(records), 'inventory_count': total, 'generation': version,
                'coverage': coverage(self.config),
                'processing_status':progress,'working_coverage':pending_coverage,
                'packs': sorted({r['pack_id'] for r in records}),
                'formats': sorted({f['format'] for r in records for f in r['files'] if f['format'] in FORMATS}),
                'modes': MODES, 'views': VIEWS, 'versions': hashes}

    @pinned
    def browse(self, filters=None, offset=0, page_size=40):
        version = self.synchronize()
        if type(offset) is not int or offset < 0 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise ConfigError('Invalid browse page; page size must be 1–100')
        filters = {} if filters is None else filters
        # Same validation and measured-filter implementation as search; never an empty semantic query.
        validate('search_assets', {'query': 'browse', 'mode': 'keyword', 'filters': filters})
        records = pilot_records(self.config)
        items = []
        matching = [r for r in sorted(records, key=lambda r: (r['pack_id'], r['display_name'].casefold(), r['asset_id'])) if matches(r, filters)]
        for record in matching[offset:offset + page_size]:
            identifier = record['asset_id']
            faults = list((record.get('inspection_run') or {}).get('source_faults', []))
            faults.extend({'channel':stage,'reason':str(fault.get('error',fault))} for stage,fault in record.get('stage_faults',{}).items() if stage in {'inventory','inspection','previews'})
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
            items[-1]['processing']=record['processing']
        return {'status': 'browse', 'pilot_count': len(records), 'shown_count': len(items), 'items': items,
                'total_count': len(matching), 'offset': offset, 'page_size': page_size, 'generation': version,
                'faults': list(self.item_faults.values()), 'model_loaded': False}

    @pinned
    def thumbnail(self, identifier, expected_version=None):
        version=self.synchronize()
        if expected_version and version!=expected_version:
            return {'status':'stale','generation':version,'reason':'Published library changed; refresh this view.'}
        retained=self.preview_faults.get((identifier,'three_quarter'))
        args={'asset_id':identifier,'include_preview':not bool(retained),'preview_view':'three_quarter'}
        payload,image,evidence=self.execute('get_asset',args)
        if retained:
            payload['preview']=retained
        elif payload.get('preview',{}).get('status')=='faulty':
            self.preview_faults[(identifier,'three_quarter')]=payload['preview']
            self.preview_bindings[(identifier,'three_quarter')]=self.preview_binding(identifier,'three_quarter')
        return {'payload':payload,'image':image,'generation':version}

    @pinned
    def asset(self, identifier, source_format=None, view='three_quarter', expected_version=None):
        version = self.synchronize()
        if expected_version and expected_version != version:
            return {'status': 'stale', 'generation': version, 'reason': 'Published library changed; refresh this view.'}
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
            self.preview_bindings[cache_key]=self.preview_binding(identifier,view)
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
            'stage_faults':record.get('stage_faults',{}),
            'caption_faults': (record.get('caption_provenance') or {}).get('visual_faults', []),
            'dependencies': record.get('dependencies', []),
            'faults': [f for (asset, _), f in self.item_faults.items() if asset == identifier],
            'scale': 'Unknown physical scale; measurements apply only to the inspected format.'}
        return {'payload': payload, 'image': image, 'evidence': evidence, 'generation': version, 'elapsed_seconds': time.perf_counter() - started}
