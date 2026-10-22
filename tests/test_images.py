"""Static 2D images with real synthetic pixels: enrollment, processing, search and descriptions."""
from contextlib import closing
from dataclasses import replace
import base64
from io import BytesIO
import json
from pathlib import Path
import sqlite3

import pytest
from PIL import Image

from test_incremental import BatchBackend, library
from local_asset_library import image_media, incremental, sources
from local_asset_library.catalog import read_database
from local_asset_library.config import ConfigError
from local_asset_library.desktop_service import DesktopService
from local_asset_library.incremental import process, update_record, working
from local_asset_library.library_index import index_library
from local_asset_library.mcp_assets import AssetService
from local_asset_library.membership import records
from local_asset_library.publication import verified_hash
from local_asset_library.source_operations import ensure_index, publish_source

SVG_BOX = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20">'
           '<rect x="5" y="5" width="30" height="10" fill="#2050e0"/></svg>')
# No width/height/viewBox and content at negative coordinates, like many exported icon SVGs.
SVG_BARE = ('<svg xmlns="http://www.w3.org/2000/svg"><g>'
            '<path fill="#FFFFFF" d="M-20 -10 L20 -10 L20 10 L-20 10 Z"/></g></svg>')
SVG_EXTERNAL = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="8" height="8">'
                '<image xlink:href="C:/Windows/secret.png" width="8" height="8"/></svg>')


def icon(color, size=50):
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    for x in range(10, size - 10):
        for y in range(10, size - 10):
            image.putpixel((x, y), color)
    return image


def build_art(root):
    (root / 'PNG/White').mkdir(parents=True)
    (root / 'PNG/Black').mkdir(parents=True)
    (root / 'Pixel').mkdir()
    (root / 'Wide').mkdir()
    (root / 'Spritesheet').mkdir()
    (root / 'Models').mkdir()
    (root / 'Textures').mkdir()
    (root / 'Vector').mkdir()
    icon((255, 255, 255, 255)).save(root / 'PNG/White/arrow.png')
    icon((0, 0, 0, 255)).save(root / 'PNG/Black/arrow.png')
    tiny = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    for i in range(16):
        tiny.putpixel((i, i), (40, 90, 230, 255))
    tiny.save(root / 'Pixel/potion.png')
    (root / 'Pixel/copy.png').write_bytes((root / 'Pixel/potion.png').read_bytes())
    Image.new('RGB', (400, 60), (200, 120, 40)).save(root / 'Wide/banner.jpg', quality=95)
    Image.new('RGBA', (40, 30), (10, 200, 10, 128)).save(root / 'Wide/glow.webp', lossless=True)
    good = BytesIO()
    Image.new('RGB', (40, 40), 'red').save(good, format='PNG')
    (root / 'Pixel/damaged.png').write_bytes(good.getvalue()[:60])
    frames = [Image.new('RGB', (20, 20), c) for c in ('red', 'blue')]
    frames[0].save(root / 'Pixel/blink.gif', save_all=True, append_images=frames[1:], duration=100)
    Image.new('RGBA', (64, 32), (255, 0, 0, 255)).save(root / 'Spritesheet/sheet.png')
    (root / 'Spritesheet/sheet.xml').write_text('<TextureAtlas imagePath="sheet.png"/>')
    Image.new('RGB', (64, 64), 'gray').save(root / 'Preview.png')
    Image.new('RGB', (32, 32), 'green').save(root / 'Models/crate_tex.png')
    (root / 'Models/crate.obj').write_text('mtllib crate.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nusemtl m\nf 1 2 3\n')
    (root / 'Models/crate.mtl').write_text('newmtl m\nmap_Kd crate_tex.png\n')
    Image.new('RGB', (32, 32), 'brown').save(root / 'Textures/wood.png')
    (root / 'Vector/box.svg').write_text(SVG_BOX)
    (root / 'Vector/bare.svg').write_text(SVG_BARE)
    (root / 'Vector/linked.svg').write_text(SVG_EXTERNAL)


@pytest.fixture
def art(tmp_path):
    legacy, backend = library.__wrapped__(tmp_path)
    config = replace(legacy, source_root=tmp_path / 'managed-sources',
                     sources_registry=legacy.project_root / 'data/library/sources.json')
    (config.project_root / 'prompts/caption-image-v1.txt').write_text('Describe one 2D image as JSON.')
    root = tmp_path / 'art/Game Icons'
    build_art(root)
    source = sources.add(config, str(root))
    sources.set_import_types(config, source['key'], True)
    return config, backend, source, root


def scoped_records(config, source):
    return {r['source_relative_identity']: r for r in records(working(sources.bound(config, source)))}


def inventory_roles(config, source):
    with closing(read_database(working(sources.bound(config, source)))) as db:
        return {json.loads(r[0])['path'].split('/', 1)[1]: json.loads(r[0])['role'] for r in db.execute('SELECT record FROM inventory')}


def originals(root):
    return {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file() and 'metadata-lal' not in p.parts}


def inspect_images(config, source):
    scoped = sources.bound(config, source)
    ids = {r['asset_id'] for r in records(working(scoped)) if r.get('asset_type') == 'image'}
    return process(scoped, 'inspection', limit=100, asset_ids=ids)


def test_enrollment_is_opt_in_and_never_promotes_model_dependencies_or_sheets(art, tmp_path):
    config, _, source, root = art
    sources.scan_source(config, source)
    found = scoped_records(config, source)
    images = {k: r for k, r in found.items() if r.get('asset_type') == 'image'}
    assert set(images) == {'image:PNG/White/arrow', 'image:PNG/Black/arrow', 'image:Pixel/potion', 'image:Pixel/copy',
                           'image:Pixel/damaged', 'image:Pixel/blink', 'image:Wide/banner', 'image:Wide/glow',
                           'image:Vector/box', 'image:Vector/bare', 'image:Vector/linked'}
    assert any(r.get('asset_type', 'model_3d') == 'model_3d' for r in found.values())
    roles = inventory_roles(config, source)
    assert roles['Models/crate_tex.png'] == 'model_dependency_image'
    assert roles['Spritesheet/sheet.png'] == 'deferred_sprite_sheet'
    assert roles['Textures/wood.png'] == 'deferred_texture'
    assert roles['Preview.png'] == 'pack_contact_sheet'
    potion = images['image:Pixel/potion']
    assert potion['type_metadata']['purpose'] == 'generic_image'
    assert potion['type_metadata']['suggested_purpose']['value'] == 'icon'
    assert 'Game Icons' in potion['type_metadata']['suggested_purpose']['evidence']
    assert potion['type_metadata']['identical_content']['asset_ids'] == [images['image:Pixel/copy']['asset_id']]
    assert potion['processing']['caption'] == 'pending' and potion['file_roles'] == {potion['files'][0]['path']: 'primary'}
    # IDs are stable across rescans; a source without the opt-in enrolls no images.
    assert {k: r['asset_id'] for k, r in scoped_records(config, source).items()} == {k: r['asset_id'] for k, r in found.items()}
    other = tmp_path / 'other'
    (other / 'Icons').mkdir(parents=True)
    icon((255, 0, 0, 255)).save(other / 'Icons/red.png')
    second = sources.add(config, str(other))
    sources.scan_source(config, second)
    assert scoped_records(config, second) == {}
    with pytest.raises(ConfigError, match='checkbox'):
        sources.set_import_types(config, second['key'], 'yes')


def test_processing_measures_derives_and_isolates_faults_without_blender(art, monkeypatch):
    config, _, source, root = art
    before = originals(root)
    sources.scan_source(config, source)
    monkeypatch.setattr(incremental, 'discover_blender', lambda config: (_ for _ in ()).throw(AssertionError('Blender')))
    report = inspect_images(config, source)
    found = scoped_records(config, source)
    status = {k: r['processing']['inspection'] for k, r in found.items() if r.get('asset_type') == 'image'}
    assert status.pop('image:Pixel/damaged') == 'failed'
    assert status.pop('image:Pixel/blink') == 'unsupported'
    assert status.pop('image:Vector/linked') == 'unsupported'
    assert set(status.values()) == {'complete'}
    assert 'damaged or truncated' in found['image:Pixel/damaged']['stage_faults']['inspection']['error']
    assert '2-frame' in found['image:Pixel/blink']['stage_faults']['inspection']['reason']
    assert 'external resources' in found['image:Vector/linked']['stage_faults']['inspection']['reason']
    potion = found['image:Pixel/potion']
    tech = potion['technical']
    assert (tech['width'], tech['height'], tech['alpha'], tech['size_class'], tech['pixel_art_candidate']) == (16, 16, 'binary', 'tiny', True)
    by_role = {p['role']: p for p in potion['previews']}
    assert by_role['original']['source_path'] == potion['files'][0]['path']
    model = Image.open(config.output_path('data', by_role['model_input']['path'][5:]))
    assert model.mode == 'RGB' and model.size == (256, 256) and by_role['model_input']['derivation']['scale'] == 16
    # Nearest-neighbour enlargement keeps the original opaque pixel colors exactly.
    assert model.getpixel((8, 8)) == (40, 90, 230) and model.getpixel((8 + 16, 8)) == tuple(by_role['model_input']['derivation']['background'])
    banner = found['image:Wide/banner']
    assert banner['technical']['alpha'] == 'none' and banner['technical']['aspect'] == 'wide'
    assert [p for p in banner['previews'] if p['role'] == 'model_input'][0]['derivation']['background'] is None
    assert found['image:Wide/glow']['technical']['alpha'] == 'partial'
    box = found['image:Vector/box']['technical']
    assert box['vector']['canvas'] == [0.0, 0.0, 40.0, 20.0] and box['vector']['canvas_basis'] == 'viewBox'
    bare = found['image:Vector/bare']['technical']
    assert bare['vector']['canvas_basis'] == 'content-bounds-v1'
    x, y, w, h = bare['vector']['canvas']
    assert x <= -20 and y <= -10 and x + w >= 20 and y + h >= 10 and w <= 44 and h <= 24
    assert {p['role'] for p in found['image:Vector/box']['previews']} == {'display', 'thumbnail', 'model_input'}
    assert report['failed'] == 1 and report['unsupported'] == 2
    # Unchanged results and faults are retained, not retried; originals are untouched.
    again = inspect_images(config, source)
    assert again['outcomes'] == [] and again['retained'] == {'complete': 8, 'failed': 1, 'unsupported': 2}
    assert originals(root) == before
    # A changed source file is new input.
    icon((250, 10, 10, 255)).save(root / 'PNG/White/arrow.png')
    sources.scan_source(config, source)
    assert [o['asset_id'] for o in inspect_images(config, source)['outcomes']] == [found['image:PNG/White/arrow']['asset_id']]


def test_model_input_candidates_and_bounds():
    tiny = Image.new('RGBA', (16, 16), (255, 255, 255, 255))
    image, derivation = image_media.model_input(tiny, 'a')
    assert image.size == (32, 32) and derivation['background'] is None
    clear = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
    clear.putpixel((5, 5), (255, 255, 255, 255))
    assert image_media.model_input(clear, 'b')[1]['background'] == [82, 82, 82]
    assert image_media.model_input(clear, 'c')[1]['background'] == [40, 40, 40]
    clear.putpixel((5, 5), (0, 0, 0, 255))
    assert image_media.model_input(clear, 'c')[1]['background'] == [215, 215, 215]
    big = Image.new('RGBA', (3000, 1500), (1, 2, 3, 255))
    image, derivation = image_media.model_input(big, 'b')
    assert image.size == (1024, 512) and derivation['resample'] == ['lanczos-downscale']
    with pytest.raises(ConfigError, match='aspect ratio'):
        image_media.model_input(Image.new('RGBA', (3000, 1), (0, 0, 0, 255)), 'b')


def test_svg_structure_checks_refuse_unsafe_inputs():
    with pytest.raises(image_media.UnsupportedMedia, match='external'):
        image_media.svg_info('<svg xmlns="http://www.w3.org/2000/svg"><style>@import url(x.css);</style></svg>')
    with pytest.raises(image_media.UnsupportedMedia, match='entities'):
        image_media.svg_info('<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg"/>')
    with pytest.raises(ConfigError, match='well-formed'):
        image_media.svg_info('<svg')
    info = image_media.svg_info('<svg xmlns="http://www.w3.org/2000/svg" width="10px" height="5"><text>A</text>'
                                '<use href="#a"/><rect fill="url(#g)"/></svg>')
    assert (info['width'], info['height'], info['text_elements']) == (10.0, 5.0, 1)


def ready_images(config, backend, source):
    scoped = sources.bound(config, source)
    sources.scan_source(config, source)
    inspect_images(config, source)
    ensure_index(config, scoped)
    with closing(sqlite3.connect(working(scoped).output_path('data', 'embeddings/index.sqlite'))) as db, db:
        from local_asset_library.catalog import digest, encoded
        db.executemany('INSERT OR REPLACE INTO meta VALUES (?,?)', [('contract', encoded(backend.contract)),
                                                                   ('contract_fingerprint', encoded(digest(backend.contract)))])
    work = working(scoped)
    for record in records(work):
        if record.get('asset_type', 'model_3d') == 'model_3d':
            record['processing'].update(inspection='failed')  # No Blender in this fixture.
            record['stage_faults'] = {'inspection': {'status': 'failed', 'error': 'Synthetic: no Blender'}}
            update_record(work, record)
    report = index_library(work, backend)
    publish_source(scoped)
    sources.aggregate(config)
    return work, report


def test_image_vectors_search_filters_and_delivery_agree(art):
    config, backend, source, root = art
    work, report = ready_images(config, backend, source)
    images = [c for c in backend.calls if c[0] == 'image']
    assert images and all(path.endswith('model-input.png') for _, path in images)
    assert {o['status'] for o in report['outcomes'] if o['channel'] == 'description'} == {'deferred'}
    found = {r['source_relative_identity']: r for r in records(work)}
    assert found['image:Pixel/potion']['processing']['embeddings'] == 'partial'  # Image vector done; description deferred.
    status = sources.scan_source(config, source)
    assert found['image:Pixel/potion']['asset_id'] not in status['pending_ids']
    service, desktop = AssetService(config, backend=backend), DesktopService(config)
    payload = service.execute('search_assets', {'query': 'potion', 'mode': 'keyword', 'filters': {'asset_type': 'image'}})[0]
    assert [r['name'] for r in payload['results']] == ['potion']
    transparent = desktop.browse({'asset_type': 'image', 'transparent': True})
    assert {i['name'] for i in transparent['items']} == {'arrow', 'potion', 'copy', 'glow', 'box', 'bare'}
    assert {i['name'] for i in desktop.browse({'size_class': 'tiny'})['items']} == {'potion', 'copy'}
    keyword = service.execute('search_assets', {'query': 'arrow', 'mode': 'keyword', 'filters': {'transparent': True}})[0]
    assert sorted(r['asset_id'] for r in keyword['results']) == sorted(
        i['asset_id'] for i in desktop.browse({'transparent': True})['items'] if i['name'] == 'arrow')
    semantic = service.execute('search_assets', {'query': 'blue potion icon', 'mode': 'image', 'filters': {'asset_type': 'image'}})[0]
    assert semantic['results'] and all(r['asset_type'] == 'image' for r in semantic['results'])
    capability = config.output_path('data', 'embeddings/capability.json')
    capability.write_text(json.dumps(dict(json.loads(capability.read_text()), reference_image_query_support=True)))
    reference = service.execute('search_assets', {'mode': 'reference', 'reference_asset_id': found['image:Pixel/potion']['asset_id']})[0]
    assert reference['results']
    assert backend.calls[-1][1].endswith('model-input.png')  # Query preparation equals index preparation.
    payload, image, _ = service.execute('get_asset', {'asset_id': found['image:Pixel/potion']['asset_id'],
                                                      'include_preview': True, 'include_metadata': True})
    preview = payload['preview']
    assert preview['native_dimensions'] == [16, 16] and preview['scale'] == 16 and preview['pixels'] == 'original source pixels'
    delivered = Image.open(BytesIO(base64.b64decode(image)))
    assert delivered.mode == 'RGBA' and delivered.size == (256, 256)
    assert delivered.getpixel((0, 0)) == (40, 90, 230, 255) and delivered.getpixel((255, 0))[3] == 0
    assert payload['metadata']['technical']['alpha'] == 'binary'
    view = desktop.image_view(found['image:Vector/box']['asset_id'], 400)
    assert view['status'] == 'image' and view['vector'] and view['size'] == [400, 200]
    thumb = desktop.thumbnail(found['image:Pixel/potion']['asset_id'])
    assert Image.open(BytesIO(base64.b64decode(thumb['image']))).size == (320, 320)
    detail = desktop.asset(found['image:Pixel/potion']['asset_id'])['payload']['presentation']
    assert detail['asset_type'] == 'image' and detail['technical']['width'] == 16 and detail['model_input']['derivation']['scale'] == 16


def test_image_descriptions_use_their_own_prompt_batches_and_optional_failures(art):
    from test_captions import caption
    from local_asset_library.settings import save_general_settings
    config, backend, source, root = art
    work, _ = ready_images(config, backend, source)
    scoped = sources.bound(config, source)
    save_general_settings(config, 8, None, 4)
    prompts = []

    class Recorder(BatchBackend):
        def generate_batch(self, inputs_list, prompt, max_new_tokens):
            prompts.append((prompt, [i[0]['view_label'] for i in inputs_list]))
            return super().generate_batch(inputs_list, prompt, max_new_tokens)

    ready = [r['asset_id'] for r in records(work) if sources.description_state(r) == 'missing']
    assert len(ready) == 8
    stop = Recorder([json.dumps(caption())] * 8, fault_on_batch=1)
    from local_asset_library.caption_batching import GpuMemoryError
    with pytest.raises(GpuMemoryError, match='batch size 4'):
        process(scoped, 'caption', 8, backend=stop, asset_ids=set(ready))
    assert all(r['processing']['caption'] == 'pending' for r in records(work) if r['asset_id'] in ready)
    outputs = [json.dumps(caption()), '{}'] + [json.dumps(caption())] * 6
    result = process(scoped, 'caption', 8, backend=Recorder(outputs), asset_ids=set(ready))
    assert result['complete'] == 7 and result['failed'] == 1
    assert {p for p, _ in prompts} == {'Describe one 2D image as JSON.'}
    labels = [label for _, batch in prompts for label in batch]
    assert any('backdrop that is not part of the image' in label for label in labels)
    complete = [r for r in records(work) if r['processing']['caption'] == 'complete' and r.get('asset_type') == 'image']
    assert {r['caption_provenance']['prompt_version'] for r in complete} == {'image-v1'}
    assert all(r['caption_provenance']['attempts'][0]['raw'] for r in complete)
    # Batch size is provenance only; failures are recorded, not retried, and never import failures.
    save_general_settings(config, 8, None, 2)
    again = process(scoped, 'caption', dry_run=True, asset_ids=set(ready))
    assert again['pending'] == 0 and again['retained'] == {'complete': 7, 'failed': 1}
    index_library(work, backend)
    status = sources.scan_source(config, source)
    failed = next(r for r in records(work) if r['processing']['caption'] == 'failed')
    report = sources.importing_failures(config)
    assert str(config.source_file(failed['files'][0]['path'])) not in report['paths']
    assert str(root / 'Pixel/damaged.png') in report['paths']  # A real decode fault is an import failure.
    assert sources.import_outcome(failed, False)['state'] == 'complete'
    assert sum(1 for r in records(work) if r.get('asset_type') == 'image' and sources.description_state(r) == 'complete') == 7
    with closing(sqlite3.connect(work.output_path('data', 'embeddings/index.sqlite'))) as db:
        channels = {row for row in db.execute("SELECT channel FROM vectors")}
    assert channels == {('image',), ('description',)}
    assert status['descriptions']['complete'] == 7 and status['descriptions']['failed'] == 1


def test_switching_images_off_and_on_keeps_results_and_never_records_faults(art):
    config, backend, source, root = art
    work, _ = ready_images(config, backend, source)
    before = {r['asset_id']: r for r in records(work) if r.get('asset_type') == 'image'}
    sources.set_import_types(config, source['key'], False)
    sources.scan_source(config, source)
    assert not [r for r in records(work) if r.get('asset_type') == 'image']
    sources.set_import_types(config, source['key'], True)
    status = sources.scan_source(config, source)
    after = {r['asset_id']: r for r in records(work) if r.get('asset_type') == 'image'}
    assert after.keys() == before.keys()
    assert all(after[k]['processing'] == before[k]['processing'] and after[k]['previews'] == before[k]['previews'] for k in after)
    assert not set(after) & set(status['pending_ids'])
    assert inspect_images(config, source)['outcomes'] == []
    # Never published and re-enrolled without results: inspected again, not recorded as corrupt output.
    potion = next(r for r in after.values() if r['display_name'] == 'potion')
    potion.update(technical=None, previews=[])
    potion['processing'].update(inspection='pending', previews='pending')
    update_record(work, potion)
    outcomes = inspect_images(config, source)['outcomes']
    assert [(o['asset_id'], o['status']) for o in outcomes] == [(potion['asset_id'], 'complete')]
