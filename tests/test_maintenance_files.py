import pytest

from local_asset_library.config import ConfigError
from local_asset_library.maintenance_files import contained, manifest, remove_manifest, remove_empty_parents


def test_removal_preserves_changed_files_and_unlisted_evidence(tmp_path):
    root = tmp_path / 'metadata'
    target = root / 'inspection/retired'
    target.mkdir(parents=True)
    (target / 'preview.png').write_bytes(b'synthetic preview')
    (target / 'changed.log').write_text('old log')
    evidence = root / 'evidence'
    evidence.mkdir()
    (evidence / 'fault.json').write_text('retained fault')
    rows = manifest(root, [target])
    (target / 'changed.log').write_text('changed log')
    result = remove_manifest(root, rows)
    assert result['removed'] == ['inspection/retired/preview.png']
    assert len(result['faults']) == 1
    remove_empty_parents(root, rows)
    assert (target / 'changed.log').read_text() == 'changed log'
    assert (evidence / 'fault.json').read_text() == 'retained fault'


def test_containment_rejects_root_and_parent_traversal(tmp_path):
    root = tmp_path / 'metadata'
    root.mkdir()
    for target in (root, root.parent, root / '../original.obj'):
        with pytest.raises(ConfigError):
            contained(root, target)


def test_tree_validation_checks_links_before_deletion(tmp_path, monkeypatch):
    root = tmp_path / 'metadata'
    target = root / 'inspection'
    target.mkdir(parents=True)
    secret = target / 'redirected'
    secret.mkdir()
    keep = target / 'preview.png'
    keep.write_bytes(b'keep')
    original = type(secret).is_junction
    monkeypatch.setattr(type(secret), 'is_junction', lambda p: p == secret or original(p))
    with pytest.raises(ConfigError, match='links'):
        manifest(root, [target])
    assert keep.read_bytes() == b'keep'
