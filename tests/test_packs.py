"""Packs from folder structure and image kinds from layered evidence (decision 0023)."""
from pathlib import Path

import numpy as np
from PIL import Image

from test_sources import managed  # noqa: F401 -- fixture
from local_asset_library import image_kinds, packs, sources
from local_asset_library.incremental import working
from local_asset_library.membership import records

KENNEY = ['Kenney All-in-1/Readme.html', 'Kenney All-in-1/Visit Kenney.url',
          'Kenney All-in-1/2D assets/Tiny Dungeon/License.txt', 'Kenney All-in-1/2D assets/Tiny Dungeon/Preview.png',
          'Kenney All-in-1/2D assets/Tiny Dungeon/Tiles/tile_0001.png', 'Kenney All-in-1/2D assets/Tiny Dungeon/Tiles/tile_0002.png',
          'Kenney All-in-1/2D assets/Pixel Shmup/License.txt', 'Kenney All-in-1/2D assets/Pixel Shmup/Ships/ship.png',
          'Kenney All-in-1/3D assets/Car Kit/License.txt', 'Kenney All-in-1/3D assets/Car Kit/Models/GLB format/van.glb']
KAYKIT = [f'KayKit_Free_pack/KayKit_{name}_1.0_FREE/{file}' for name in ('Dungeon_Pack', 'Forest_Nature_Pack', 'Space_Base_Bits')
          for file in ('License.txt', 'Assets/gltf/crate.gltf', 'Assets/gltf/crate.png')]
CCMP = [f'Cartoon City Massive Pack/CCMP_{part}/Models/{n}.fbx' for part in ('1_Core', '2_Buildings', '5_Props') for n in ('a', 'b')]


def assets_of(paths):
    return [p for p in paths if p.endswith(('.glb', '.gltf', '.fbx', '.png')) and 'Preview' not in p]


def test_packs_are_the_marked_folders_nearest_the_assets_and_bundles_hold_them():
    found = packs.detect(KENNEY, assets_of(KENNEY))
    assert set(found['packs']) == {'Kenney All-in-1/2D assets/Tiny Dungeon', 'Kenney All-in-1/2D assets/Pixel Shmup',
                                   'Kenney All-in-1/3D assets/Car Kit'}
    tiny = found['packs']['Kenney All-in-1/2D assets/Tiny Dungeon']
    assert tiny['cover'] == 'Kenney All-in-1/2D assets/Tiny Dungeon/Preview.png' and tiny['basis'] == 'markers'
    assert {m['kind'] for m in tiny['markers']} == {'license', 'preview'}
    # A category inside a bundle is a bundle too: the packs below it, not the folder itself.
    assert set(found['bundles']) == {'Kenney All-in-1', 'Kenney All-in-1/2D assets'}
    kaykit = packs.detect(KAYKIT, assets_of(KAYKIT))
    assert sorted(kaykit['packs']) == sorted({'/'.join(p.split('/')[:2]) for p in KAYKIT})  # Versioned names and licenses.
    assert kaykit['bundles'] == ['KayKit_Free_pack']


def test_without_markers_the_first_folder_is_the_pack_and_owner_answers_win():
    found = packs.detect(CCMP, CCMP)
    assert list(found['packs']) == ['Cartoon City Massive Pack']  # The parts are one pack the owner can split.
    split = packs.detect(CCMP, CCMP, [{'path': f'Cartoon City Massive Pack/CCMP_{p}', 'value': 'make_pack'} for p in ('1_Core', '2_Buildings')])
    assert set(split['packs']) == {'Cartoon City Massive Pack/CCMP_1_Core', 'Cartoon City Massive Pack/CCMP_2_Buildings',
                                   'Cartoon City Massive Pack'}
    assert split['packs']['Cartoon City Massive Pack/CCMP_1_Core']['basis'] == 'owner'
    merged = packs.detect(KAYKIT, assets_of(KAYKIT), [{'path': 'KayKit_Free_pack/KayKit_Dungeon_Pack_1.0_FREE', 'value': 'merge'}])
    assert 'KayKit_Free_pack/KayKit_Dungeon_Pack_1.0_FREE' not in merged['packs']
    assert merged['pack_of']['KayKit_Free_pack/KayKit_Dungeon_Pack_1.0_FREE/Assets/gltf'] == 'KayKit_Free_pack'


def classify(path, referenced=(), stems=(), folders=(), has_models=True, answer=None, pixels=None):
    return image_kinds.classify(path, dict.fromkeys(referenced, 'Referenced'), set(stems), set(folders), has_models, answer, pixels)


def test_each_classification_layer():
    assert classify('k/Pack/tex/a.png', referenced=['k/Pack/tex/a.png'])['value'] == 'model_texture'
    assert classify('k/Icons/sword.png', has_models=False) == {'value': 'image', 'basis': 'pack-without-models',
                                                                'evidence': 'The pack holds no 3D models'}
    assert classify('k/Icons/rock_normal.png', has_models=False)['value'] == 'material_texture'
    assert classify('k/Pack/Models/crate.png', stems=['crate'])['basis'] == 'model-stem'
    assert classify('k/Pack/Surfaces/brick_roughness.png')['basis'] == 'material-name'
    assert classify('k/Pack/Textures/wall.png')['basis'] == 'folder-name'
    assert classify('k/Pack/UI/button.png')['value'] == 'image'
    assert classify('k/Pack/Models/x.png', folders=['k/Pack/Models'])['value'] == 'model_texture'
    assert classify('k/Pack/Misc/x.png', answer='texture')['basis'] == 'owner'
    assert classify('k/Pack/tex/a.png', referenced=['k/Pack/tex/a.png'], answer='image')['value'] == 'model_texture'
    hint = {'value': 'material_texture', 'basis': 'pixels', 'evidence': 'normal-map colors'}
    assert classify('k/Pack/Misc/x.png', pixels=hint)['basis'] == 'pixels'
    assert classify('k/Pack/UI/x.png', pixels=hint)['basis'] == 'folder-name'  # Pixels never outvote other evidence.


def test_pixel_hints():
    normal = np.zeros((32, 32, 4), np.uint8)
    normal[..., :3] = (128, 128, 255)
    normal[..., 3] = 255
    normal[::2, :, 0] = 140
    assert 'normal-map' in image_kinds.pixel_evidence(normal)['evidence']
    flat = np.full((32, 32, 4), 200, np.uint8)
    assert image_kinds.pixel_evidence(flat)['value'] == 'material_texture'  # Single channel gray: a map.
    cutout = np.zeros((32, 32, 4), np.uint8)
    cutout[8:24, 8:24] = (255, 0, 0, 255)
    assert image_kinds.pixel_evidence(cutout)['value'] == 'image' and 'cutout alpha' in image_kinds.pixel_evidence(cutout)['evidence']


def test_scans_use_gltf_obj_and_fbx_references_and_pack_answers(managed):
    config, _, one, _ = managed
    root = Path(one['path']) / 'Kit_1.0'
    (root / 'gltf').mkdir(parents=True)
    (root / 'License.txt').write_text('CC0')
    Image.new('RGB', (4, 4), 'blue').save(root / 'gltf/painted.png')
    (root / 'gltf/barrel.gltf').write_text('{"asset":{"version":"2.0"},"images":[{"uri":"painted.png"}]}')
    (root / 'fbx').mkdir()
    (root / 'fbx/chest.fbx').write_bytes(b'Kaydara FBX Binary\x00\x00RelativeFilename\x00\x10chest_diffuse.png\x00')
    Image.new('RGB', (4, 4), 'red').save(root / 'fbx/chest_diffuse.png')
    Image.new('RGB', (4, 4), 'gray').save(root / 'logo.png')
    sources.scan_source(config, one)
    work = working(sources.bound(config, one))
    images = {r['display_name']: r['type_metadata']['image_kind'] for r in records(work) if r.get('asset_type') == 'image'}
    assert 'painted' not in images and 'chest_diffuse' not in images  # Model textures stay dependencies.
    assert images['logo']['value'] == 'image'
    detected = packs.structure(config, one)
    assert 'Kit_1.0' in detected['packs'] and detected['packs']['Kit_1.0']['basis'] == 'markers'
    packs.answer(config, one['key'], 'Kit_1.0', 'merge')
    sources.answer_folder(config, one['key'], 'Kit_1.0', 'image_kind', 'texture')
    sources.scan_source(config, one)
    assert 'Kit_1.0' not in packs.structure(config, one)['packs']
    logo = next(r for r in records(work) if r['display_name'] == 'logo')
    assert logo['type_metadata']['image_kind']['basis'] == 'owner'
    packs.rename(config, one['key'], '', 'My library')
    assert packs.pack_of(config, one, logo)['name'] == 'My library'
    assert packs.fields(config, logo) == {'pack_name': 'My library', 'pack_path': ''}  # What agents get with each asset.
