"""Compare a legacy publication with the migrated source-owned library."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_project_config
from local_asset_library.sources import registry,bound,source_status
from local_asset_library.publication import read_json,atomic_json,generation

parser=argparse.ArgumentParser();parser.add_argument('--legacy-generation',required=True)
args=parser.parse_args()
if not __import__('re').fullmatch(r'v_[0-9a-f]{32}',args.legacy_generation):parser.error('Invalid publication generation')
config=load_project_config(ROOT)
legacy=ROOT/'data/library/generations'/args.legacy_generation


def db_records(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        return {i:json.loads(value) for i,value in db.execute('SELECT asset_id,record FROM assets')}


def vectors(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        return {r[0]:[hashlib.sha256(x).hexdigest() if isinstance(x,bytes) else x for x in r]
                for r in db.execute('SELECT * FROM vectors')}


before=db_records(legacy/'catalog.sqlite');after=db_records(config.output_path('data','catalog.sqlite'))
old_vectors=vectors(legacy/'embeddings/index.sqlite');new_vectors=vectors(config.output_path('data','embeddings/index.sqlite'))
migration=read_json(ROOT/'data/library/source-migration/latest.json')
history=Path(migration['evidence'])
originals=read_json(history/'originals-before.json')==read_json(history/'originals-after.json')
source_states=[source_status(config,s) for s in registry(config)['sources']]
references=0;missing=[]
for source in registry(config)['sources']:
    scoped=bound(config,source)
    for identifier,record in after.items():
        if record['pack_id']!=source['key']:continue
        for preview in record['previews']:
            if preview.get('origin')!='rendered':continue
            path=config.output_path('data',preview['path'][5:])
            if not path.is_relative_to(scoped.metadata_root) or not path.is_file():missing.append(str(path))
            references+=1
completion=read_json(ROOT/'data/library/source-migration/report-copies-completion.json')
checks={'asset_identities_unchanged':set(before)==set(after),'all_published_records_unchanged':before==after,
        'all_vector_bytes_and_bindings_unchanged':old_vectors==new_vectors,'original_assets_unchanged':originals,
        'generated_preview_references_in_source_metadata':not missing,
        'historical_report_copies_complete':completion['status']=='passed'}
report={'status':'passed' if all(checks.values()) else 'faulty','checks':checks,'assets':len(after),
        'vectors':len(new_vectors),'sources':len(source_states),'rendered_preview_references':references,
        'missing_references':missing,'existing_assets_with_recorded_processing_issues':sum(s.get('failed',0) for s in source_states),
        'generation':generation(config),'legacy_generation':args.legacy_generation,'original_migration_receipt':str(history),
        'application_writer_fault_resolution':'data/library/source-migration/report-copies-completion.json'}
atomic_json(ROOT/'data/library/verification/source-preservation.json',report)
print(json.dumps(report,indent=2));sys.exit(report['status']!='passed')
