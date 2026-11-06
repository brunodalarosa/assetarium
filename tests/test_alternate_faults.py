"""A broken alternate file fails alone; owner-requested recheck of check failures (decision 0020)."""
from contextlib import closing
import json

import pytest

from local_asset_library import recheck, retrieval, sources
from local_asset_library.config import ConfigError
from local_asset_library.incremental import checkpoint, ledger, update_record, working
from local_asset_library.mcp_assets import source_variants
from local_asset_library.settings import save_general_settings
from local_asset_library.sources import read_records
from test_sources import managed  # noqa: F401 (fixture)

NAMES = ('crate', 'barrel', 'lantern')


def kit(root, broken=True):
    """Recognized FBX / gLTF / OBJ folders; the OBJ materials point outside the source like an author's desktop."""
    for name in NAMES:
        for folder, suffix, data in (('FBX', '.fbx', b'fbx ' + name.encode()),
                                     ('gLTF', '.gltf', b'{"asset":{"version":"2.0"}}')):
            path = root / 'Set' / folder / (name + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        obj = root / 'Set' / 'OBJ' / (name + '.obj')
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_text(f'mtllib {name}.mtl\nv 0 0 0\n')
        texture = 'C:/Users/author/Desktop/atlas.png' if broken else 'atlas.png'
        (obj.parent / (name + '.mtl')).write_text(f'newmtl m\nmap_Kd {texture}\n')
    (root / 'Set' / 'OBJ' / 'atlas.png').write_bytes(b'png')
    return root


@pytest.fixture
def source(managed, tmp_path):
    config = managed[0]
    added = sources.add(config, str(kit(tmp_path / 'kit')))
    sources.scan_source(config, added)
    return config, added, working(sources.bound(config, added))


def crate(work):
    return next(r for r in read_records(work) if r['display_name'] == 'crate')


def test_a_broken_alternate_fails_alone_and_is_recorded(source):
    _, _, work = source
    record = crate(work)
    assert sorted(f['format'] for f in record['files']) == ['fbx', 'gltf', 'obj']
    problems = retrieval.file_problems(work, record)
    [(path, reason)] = problems.items()
    assert path.endswith('/OBJ/crate.obj') and 'Absolute or remote dependency is not permitted' in reason
    with pytest.raises(ConfigError):
        retrieval._source_check(work, record)  # The old whole-asset rule.
    assert retrieval.used_file(work, record).endswith('/gLTF/crate.gltf')
    usable = retrieval.source_check(work, record)
    assert usable and usable == retrieval.source_check(work, record)  # Stable fingerprint, no reprocessing loop.


def test_a_broken_file_the_asset_is_rendered_from_still_fails_it(source):
    config, _, work = source
    save_general_settings(config, 8, ['obj'])
    with pytest.raises(ConfigError, match='Dependency unavailable or unresolved'):
        retrieval.source_check(work, crate(work))  # No switching to another file.


def test_healthy_assets_keep_exactly_their_fingerprint(managed, tmp_path):
    config = managed[0]
    added = sources.add(config, str(kit(tmp_path / 'healthy', broken=False)))
    sources.scan_source(config, added)
    work = working(sources.bound(config, added))
    for record in read_records(work):
        assert retrieval.file_problems(work, record) == {}
        assert retrieval.source_check(work, record) == retrieval._source_check(work, record)


def test_dependencies_belong_to_their_file_through_materials(source):
    _, _, work = source
    record = crate(work)
    owners = retrieval.dependency_owners(record)
    by_reference = {d['reference']: owners[i] for i, d in enumerate(record['dependencies']) if i in owners}
    assert by_reference['crate.mtl'].endswith('/OBJ/crate.obj')
    assert by_reference['C:/Users/author/Desktop/atlas.png'].endswith('/OBJ/crate.obj')


def test_get_asset_never_offers_an_unusable_file(source):
    _, _, work = source
    record = crate(work)
    detail = retrieval.resolved_detail(work, record['asset_id'])
    assert detail['selected_source']['format'] == 'gltf' and list(detail['unusable_files'])[0].endswith('/OBJ/crate.obj')
    assert not any(d.get('from', '').endswith(('.obj', '.mtl')) for d in detail['dependencies'])
    with pytest.raises(ConfigError, match='not usable: Dependency unavailable'):
        retrieval.resolved_detail(work, record['asset_id'], 'obj')
    with pytest.raises(ConfigError, match='not usable'):
        retrieval.resolved_detail(work, record['asset_id'], None, 'OBJ')
    variants = {v['variant']: v for v in source_variants(record, detail['unusable_files'])['source_variants']}
    assert variants['OBJ']['usable'] is False and 'Absolute' in variants['OBJ']['reason'] and variants['gLTF']['usable']


def fail(work, record, stage, error):
    with closing(ledger(work)) as db:
        checkpoint(db, record['asset_id'], stage, 'f' * 64, 'failed', {'error': error, 'status': 'failed', 'type': 'ConfigError'})
    record['processing'][stage] = 'failed'
    record.setdefault('stage_faults', {})[stage] = {'error': error, 'status': 'failed', 'type': 'ConfigError'}
    update_record(work, record)


def test_recheck_releases_only_check_failures_that_now_pass_after_the_owner_confirms(source):
    config, added, work = source
    records = sorted(read_records(work), key=lambda r: r['display_name'])
    fail(work, records[0], 'inspection', 'Dependency unavailable or unresolved: C:/Users/author/Desktop/atlas.png')
    fail(work, records[1], 'inspection', 'Missing, rejected or unresolved texture dependencies: atlas')  # Blender: never released.
    found = recheck.preview(config, added['key'])
    assert found['retry'] == 1 and found['examples'] == [records[0]['display_name']] and found['still_failing'] == 0
    with pytest.raises(ConfigError, match='changed since this recheck'):
        recheck.release(config, added['key'], 'a' * 64)
    result = recheck.release(config, added['key'], found['preview_id'])
    assert result['retried'] == 1
    released = next(r for r in read_records(work) if r['asset_id'] == records[0]['asset_id'])
    assert released['processing']['inspection'] == 'pending' and 'inspection' not in released.get('stage_faults', {})
    assert released['released_faults']['inspection']['error'].startswith('Dependency unavailable')
    with closing(ledger(work)) as db:
        status, evidence = db.execute("SELECT status,evidence FROM jobs WHERE asset_id=? AND stage='inspection'",
                                      (records[0]['asset_id'],)).fetchone()
        history = db.execute("SELECT count(*) FROM history WHERE asset_id=?", (records[0]['asset_id'],)).fetchone()[0]
    assert status == 'released' and json.loads(evidence)['previous']['error'].startswith('Dependency unavailable') and history == 2
    assert recheck.preview(config, added['key'])['retry'] == 0  # Released once; the Blender failure stays recorded.
    with pytest.raises(ConfigError, match='Nothing to retry'):
        recheck.release(config, added['key'], found['preview_id'])


def test_a_check_failure_that_still_fails_stays_recorded(source):
    config, added, work = source
    save_general_settings(config, 8, ['obj'])
    record = crate(work)
    fail(work, record, 'inspection', 'Dependency unavailable or unresolved: C:/Users/author/Desktop/atlas.png')
    found = recheck.preview(config, added['key'])
    assert found['retry'] == 0 and found['still_failing'] == 1
    assert 'Dependency unavailable' in found['still_failing_examples'][0]['reason']
