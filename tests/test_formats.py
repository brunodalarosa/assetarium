"""Formats Assetarium uses (decision 0030): an asset only in formats that are off is hidden everywhere, never deleted."""
from pathlib import Path

import pytest

from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import library_view, processing_queue, settings, sources
from local_asset_library.config import ConfigError
from local_asset_library.settings import IMAGE_FORMATS, general_settings, save_general_settings, uses


def test_the_rule_hides_only_assets_whose_toggled_formats_are_all_off():
    on = ['gltf', 'png']
    assert uses('model_3d', ['glb'], on) and not uses('model_3d', ['fbx'], on) and uses('model_3d', ['fbx', 'gltf'], on)
    assert uses('model_3d', ['blend'], on)  # No toggle: listed as not processed, never hidden.
    assert uses('image', ['png'], on) and not uses('image', ['jpg'], on) and uses('image', ['jpg'], ['jpeg'])
    assert uses('material_texture', ['jpg'], []) and uses('audio', ['wav'], [])  # Textures follow their models.


def test_image_formats_are_saved_validated_and_on_by_default(managed):
    config = managed[0]
    assert general_settings(config)['image_formats'] == list(IMAGE_FORMATS)
    saved = save_general_settings(config, 24, ['gltf'], image_formats=['svg', 'png'])
    assert saved['image_formats'] == ['png', 'svg'] and saved['processing_formats'] == ['gltf']
    assert settings.used_formats(config) == ['gltf', 'png', 'svg']
    with pytest.raises(ConfigError, match='image formats'):
        save_general_settings(config, 24, image_formats=['jpg'])  # The toggle is jpeg; .jpg files count for it.


def test_turning_a_format_off_hides_its_assets_and_on_brings_them_back(managed, monkeypatch):
    config, backend, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    ready_source(config, backend, one)
    (Path(one['path']) / 'Copy.fbx').write_text('fbx')
    sources.scan_source(config, one)
    root = lambda: next(n for n in next(f for f in library_view.tree(config)['folders'] if f['key'] == one['key'])['nodes'] if n['path'] == '')
    names = lambda: {i['name'] for i in library_view.folder_items(config, one['key'], show_files=False)['items']}
    shown = root()
    save_general_settings(config, 24, ['obj', 'gltf'])
    assert 'Copy' not in names() and root()['hidden'] == 1 and root()['assets'] == shown['assets'] - 1
    assert root()['previews'] == shown['previews']  # Finished work of the other assets is untouched.
    found = processing_queue.resolve(config, 'previews', {'key': one['key'], 'path': ''})
    assert not any('Copy' in str(i) for i in found['ids']) and root()['pending'] == len(found['ids'])
    save_general_settings(config, 24, ['obj', 'gltf', 'fbx'])
    assert 'Copy' in names() and root()['hidden'] == 0


def test_search_and_collections_follow_the_formats(managed, monkeypatch):
    from local_asset_library import asset_collections, retrieval
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    record = next(r for r in retrieval.library_records(config))
    assert retrieval.matches(record, {}, None, settings.used_formats(config))
    assert not retrieval.matches(record, {}, None, ['fbx'])  # Its OBJ file's format is off.
    assert retrieval.matches(record, {}, None, None)
    asset_collections.create(config, 'Props', members=[record['asset_id']])
    save_general_settings(config, 24, ['fbx'])
    entry = asset_collections.resolve(config, asset_collections.load(config)['collections'][0]['items'])[0]
    assert entry['hidden_by_formats'] == 'Hidden: OBJ is off in Settings → General → Formats'
