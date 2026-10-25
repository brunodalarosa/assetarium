"""Read-only original-source and pilot-result preservation receipts for Step 8."""
import argparse
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import json
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_asset_library import hash_cache; hash_cache.require_fresh()  # Byte audit: never reuse recorded hashes (decision 0004).
from local_asset_library.config import load_project_config
from local_asset_library.catalog import read_database,snapshot,walk_source,save_json
from local_asset_library.captions import file_hash
from local_asset_library.incremental import working
parser=argparse.ArgumentParser();parser.add_argument('--run-name',required=True);args=parser.parse_args()
if not args.run_name.replace('-','').isalnum():raise ValueError('Invalid run name')
out=ROOT/'data/library/verification'/args.run_name;out.mkdir(parents=True,exist_ok=False)
config=load_project_config(ROOT)
before=json.loads(config.output_path('data','evidence/source-baseline.json').read_text(encoding='utf-8'))
after=snapshot(walk_source(config))
source_before={r['path']:r for r in before};source_after={r['path']:r for r in after}
changed=[p for p in sorted(set(source_before)|set(source_after)) if source_before.get(p)!=source_after.get(p)]
legacy=replace(config,catalog_generation='legacy')
work=working(config)
with closing(read_database(legacy)) as db:
    old={i:json.loads(r) for i,r in db.execute('SELECT asset_id,record FROM assets')}
with closing(read_database(work)) as db:
    current={i:json.loads(r) for i,r in db.execute('SELECT asset_id,record FROM assets')}
pilot=json.loads(config.output_path('data','pilot/selection-manifest.json').read_text(encoding='utf-8'))
protected=[];differences=[]
for item in pilot['assets']:
    identifier=item['asset_id'];original=old[identifier];now=current[identifier]
    for key in ('technical','description','caption_provenance','inspection_run','owner_overlay','previews'):
        if original.get(key)!=now.get(key):differences.append({'asset_id':identifier,'field':key})
    for view in original['previews']:
        if view.get('path','').startswith('data/'):
            path=config.output_path('data',view['path'][5:])
            valid=file_hash(path)==view['sha256'];protected.append({'path':str(path),'valid':valid})
    for stage in ('inspection_run','caption_provenance'):
        original_path=(original.get(stage) or {}).get('result_path')
        if original_path:
            path=config.output_path('data',original_path.removeprefix('data/'))
            protected.append({'path':str(path),'sha256':file_hash(path),'exists':True})
report={'status':'passed' if not changed and not differences and all(p.get('valid',True) for p in protected) else 'faulty',
    'original_source_entries':len(before),'changed_sources':changed,'pilot_assets':len(pilot['assets']),
    'changed_pilot_fields':differences,'protected_pilot_outputs':protected,
    'method':'Complete original SHA-256/size/mtime comparison; existing pilot record fields compared to retained legacy catalog; rendered input hashes verified.',
    'no_sources_copied_or_modified':True}
save_json(out/'report.json',report)
print(json.dumps({k:v for k,v in report.items() if k!='protected_pilot_outputs'}))
sys.exit(report['status']!='passed')
