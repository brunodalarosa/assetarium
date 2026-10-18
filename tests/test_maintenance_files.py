import os

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
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret.bin').write_bytes(b'never removed')
    keep = target / 'preview.png'
    keep.write_bytes(b'keep')
    import subprocess
    result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(target / 'redirected'), str(outside)], capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    with pytest.raises(ConfigError, match='links'):
        manifest(root, [target])
    assert keep.read_bytes() == b'keep' and (outside / 'secret.bin').read_bytes() == b'never removed'


def test_long_paths_are_validated_and_removed(tmp_path):
    from local_asset_library.maintenance_files import manifest, remove_empty_tree, remove_manifest
    from local_asset_library.publication import filesystem_path
    root = tmp_path / 'generated'
    deep = root / 'target' / ('a' * 90) / ('b' * 90) / ('c' * 90)
    os.makedirs(filesystem_path(deep))
    leaf = deep / 'file.bin'
    with open(filesystem_path(leaf), 'wb') as stream:
        stream.write(b'deep')
    assert len(str(leaf)) > 260
    rows = manifest(root, [root / 'target'])
    assert [r['bytes'] for r in rows] == [4]
    assert remove_manifest(root, rows)['removed'] == [rows[0]['path']]
    assert not remove_empty_tree(root, root / 'target') and not os.path.exists(filesystem_path(root / 'target'))
