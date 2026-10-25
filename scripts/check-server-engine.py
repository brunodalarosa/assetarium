"""Real check of the local-server description engine against a running OpenAI-compatible server.

Builds an isolated synthetic project under scratch/<run-name> whose previews are drawn shapes,
sets the engine to local-server and runs the ordinary caption stage through the composition root.
Assetarium does not start the server. Writes data/engines/<run-name>/report.json.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
parser.add_argument('--url', default='http://127.0.0.1:8080/v1')
parser.add_argument('--model', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/engines' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir(parents=True, exist_ok=False)

from test_sources import managed, ready_source
from local_asset_library import engines, sources
from local_asset_library.captions import file_hash
from local_asset_library.engine_server import probe
from local_asset_library.incremental import process, update_record
from local_asset_library.membership import records
from local_asset_library.publication import atomic_json
from local_asset_library.settings import save_general_settings


def draw(kind, view):
    image = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    pen = ImageDraw.Draw(image)
    shift = {'front': 0, 'side': 40, 'three_quarter': 20}[view]
    if kind == 'apple':
        pen.ellipse((126 + shift, 150, 386 - shift, 410), fill=(200, 30, 35, 255))
        pen.rectangle((250, 105, 262, 160), fill=(90, 55, 25, 255))
        pen.ellipse((262, 100, 330, 140), fill=(60, 150, 50, 255))
    elif kind == 'crate':
        pen.polygon([(256, 120), (400 - shift, 190), (256, 260), (112 + shift, 190)], fill=(196, 150, 90, 255))
        pen.polygon([(112 + shift, 190), (256, 260), (256, 420), (112 + shift, 350)], fill=(160, 115, 60, 255))
        pen.polygon([(256, 260), (400 - shift, 190), (400 - shift, 350), (256, 420)], fill=(130, 90, 45, 255))
    else:
        pen.rectangle((236, 330, 276, 430), fill=(110, 70, 35, 255))
        pen.polygon([(256, 80), (380 - shift, 340), (132 + shift, 340)], fill=(40, 130, 60, 255))
    return image


config, backend, one, _ = managed.__wrapped__(fixture)
work = ready_source(config, backend, one)
for prompt in (ROOT / 'prompts').glob('caption-*.txt'):  # The fixture's placeholders are not real prompts.
    (config.project_root / 'prompts' / prompt.name).write_bytes(prompt.read_bytes())
kinds = ['apple', 'crate', 'tree']
assets = []
for index, record in enumerate(records(work)):
    kind = kinds[index % len(kinds)]
    for preview in record['previews']:
        path = work.output_path('data', preview['path'][5:])
        draw(kind, preview['view_label']).save(path)
        preview['sha256'] = file_hash(path)
    record['description'] = record['caption_provenance'] = None
    record['processing']['caption'] = 'pending'
    update_record(work, record)
    assets.append({'asset_id': record['asset_id'], 'drawn': kind})
sources.scan_source(config, one)
scoped = sources.bound(config, one)
report = {'status': 'running', 'server': args.url, 'model': args.model, 'synthetic_only': True, 'assets': assets,
          'probe': probe(args.url, args.model)}
try:
    save_general_settings(config, 8, None, None, True, 'local-server', {'url': args.url, 'model': args.model})
    engine = engines.description_engine(scoped)
    report['engine_contract'] = engine.contract
    started = time.perf_counter()
    result = process(scoped, 'caption', 20, backend=engine)
    report['elapsed_seconds'] = round(time.perf_counter() - started, 1)
    report['stage'] = {k: result.get(k) for k in ('pending', 'selected', 'complete', 'failed', 'retained')}
    described = {r['asset_id']: r for r in records(sources.working(scoped) if hasattr(sources, 'working') else work)}
    for item in assets:
        record = described[item['asset_id']]
        provenance = record.get('caption_provenance') or {}
        item.update(caption=record['processing']['caption'], identity=(record.get('description') or {}).get('identity'),
                    description=(record.get('description') or {}).get('description'),
                    colors=(record.get('description') or {}).get('colors'),
                    generation_mode=provenance.get('generation_mode'), engine=provenance.get('engine'),
                    attempts=[{k: a.get(k) for k in ('status', 'error')} | {'metrics': {m: (a.get('metrics') or {}).get(m)
                              for m in ('elapsed_seconds', 'input_tokens', 'generated_tokens', 'server_model')}}
                              for a in provenance.get('attempts', [])],
                    fault=(record.get('stage_faults') or {}).get('caption'))
    report['dry_run_after'] = process(scoped, 'caption', 20, dry_run=True)['pending']
    report['status'] = 'passed' if result.get('complete') == len(assets) and report['dry_run_after'] == 0 else 'faulty'
except Exception as exc:
    import traceback
    report.update(status='faulty', reason=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
atomic_json(OUT / 'report.json', report)
print(json.dumps({k: report.get(k) for k in ('status', 'reason', 'elapsed_seconds', 'stage', 'dry_run_after')}, indent=2))
for item in assets:
    print(item['drawn'], '→', item.get('caption'), (item.get('identity') or {}).get('label'), item.get('colors'))
raise SystemExit(report['status'] != 'passed')
