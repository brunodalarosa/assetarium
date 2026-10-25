"""Image evidence and deterministic reference inputs. Does not load models or rankings."""
from pathlib import Path
import json
from PIL import Image, ImageDraw
from local_asset_library.catalog import save_json, digest
from local_asset_library.captions import file_hash
from local_asset_library.config import load_project_config
from local_asset_library.retrieval import pilot_records, preview_file, index_database
from contextlib import closing

root = Path(__file__).resolve().parents[2]
if (root / 'docs/evaluation/freeze.json').exists():
    raise SystemExit('Preparation already frozen; preserve image evidence and labels')
config = load_project_config(root)
spec = json.loads((root / "docs/evaluation/queries.json").read_text(encoding="utf-8"))
records = pilot_records(config)
lookup = {r['pack_id'] + '/' + r['display_name']: r for r in records}
target = config.output_path("data", "evaluation/prelabel")
target.mkdir(parents=True, exist_ok=True)
evidence = []
for offset in range(0, len(records), 8):
    sheet = Image.new("RGB", (1280, 4 * 275), (235, 235, 235))
    draw = ImageDraw.Draw(sheet)
    for j, record in enumerate(records[offset:offset + 8]):
        alias = record['pack_id'] + '/' + record['display_name']
        views = [p for p in record['previews'] if p.get('origin') == 'rendered']
        chosen = [next(p for p in views if p['view_label'] == label) for label in ('three_quarter', 'side')]
        for k, preview in enumerate(chosen):
            with Image.open(preview_file(config, preview)) as source:
                rgba = source.convert('RGBA')
                img = Image.alpha_composite(Image.new('RGBA', rgba.size, (82,82,82,255)), rgba).convert('RGB')
                img.thumbnail((300, 240))
                x, y = (j % 2) * 640 + k * 320, (j // 2) * 275
                sheet.paste(img, (x, y + 30))
                draw.text((x + 4, y + 8), f"{offset+j+1} {record['display_name']} / {preview['view_label']}", fill='black')
            evidence.append({'asset_id': record['asset_id'], 'alias': alias, 'path': preview['path'],
                             'sha256': preview['sha256'], 'sheet': f'data/evaluation/prelabel/views-{offset//8+1}.jpg'})
    sheet.save(target / f'views-{offset//8+1}.jpg', quality=94)
with closing(index_database(config, True)) as db:
    indexed_hashes = {json.loads(r[0])['sha256'] for r in db.execute("SELECT preview FROM vectors WHERE channel='image'")}
references = []
for query in spec['references']:
    record = lookup[query['asset']]
    view = next(p for p in record['previews'] if p.get('origin') == 'rendered' and p['view_label'] == query['view'])
    original = preview_file(config, view)
    with Image.open(original) as source:
        box = tuple(round(v * (source.width if i % 2 == 0 else source.height)) for i, v in enumerate(query['crop_fractions']))
        crop = source.crop(box)
        assert crop.size != source.size
        path = config.output_path('data', f'evaluation/references/{query["id"]}.png')
        path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(path)
    sha = file_hash(path)
    assert sha not in indexed_hashes
    references.append({**query, 'asset_id': record['asset_id'], 'path': path.relative_to(root).as_posix(),
                       'sha256': sha, 'parent_path': view['path'], 'parent_sha256': view['sha256'],
                       'crop_box': list(box), 'indexed_parent_rows_excluded': 'all rows with matching parent SHA-256',
                       'limitation': 'Crop of an existing rendered asset, not an independent photograph; parent view excluded.'})
save_json(config.output_path('data', 'evaluation/prelabel/image-evidence.json'), {'views': evidence, 'references': references})
save_json(config.output_path('data', 'evaluation/references/manifest.json'), {'references': references})
save_json(config.output_path('data', 'evaluation/preservation-before.json'),
          {'catalog_sha256': file_hash(config.output_path('data', 'catalog.sqlite')),
           'index_sha256': file_hash(config.output_path('data', 'embeddings/index.sqlite')),
           'pilot_sha256': file_hash(config.output_path('data', 'pilot/selection-manifest.json'))})
print(json.dumps({'review_sheets': [str(p) for p in target.glob('views-*.jpg')], 'references': references}))
