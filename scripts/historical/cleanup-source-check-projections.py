"""Remove only redundant, inactive projections of the explicitly named QA sources.

No source results, faults, reports or original files are deleted. Source-owned
published rows/vectors must prove that every removed combined row is retained.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_project_config
from local_asset_library.sources import registry,bound
from local_asset_library.publication import read_json,atomic_json,generation

parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
config=load_project_config(ROOT)
target_root=(ROOT/'data/library/generations').resolve()
receipt=ROOT/'data/library/verification/source-test-cache-cleanup.json'
if args.apply and receipt.exists():raise RuntimeError('One-time QA cache cleanup already has a receipt; no automatic rerun')
def data(path,kind):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        if kind=='records':return {i:json.loads(v) for i,v in db.execute('SELECT asset_id,record FROM assets')}
        return {r[0]:tuple(r) for r in db.execute('SELECT * FROM vectors')}
current=config.output_path('data','catalog.sqlite')
retained_records=data(current,'records');retained_vectors=data(config.output_path('data','embeddings/index.sqlite'),'vectors')
value=registry(config)
fixture_keys={s['key'] for s in value.get('detached',[]) if s['key'].startswith('LAL-source-verification-')}
for source in value.get('detached',[]):
    if source['key'] not in fixture_keys:continue
    scoped=bound(config,source)
    if not scoped.output_path('data','library/active.json').exists():continue
    retained_records.update(data(scoped.output_path('data','catalog.sqlite'),'records'))
    retained_vectors.update(data(scoped.output_path('data','embeddings/index.sqlite'),'vectors'))
targets=[]
for directory in target_root.glob('v_*'):
    if directory.name==generation(config):continue
    path=directory/'catalog.sqlite'
    if not path.exists():continue
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        packs={p for p, in db.execute('SELECT DISTINCT pack_id FROM assets')}
    if not packs.intersection(fixture_keys):continue
    assert not directory.is_symlink() and not directory.is_junction()
    assert directory.resolve().parent==target_root
    files=[]
    for p in directory.rglob('*'):
        assert not p.is_symlink() and not p.is_junction() and p.resolve().is_relative_to(directory.resolve())
        if p.is_file():files.append(p)
    assert {p.relative_to(directory).as_posix() for p in files}=={'catalog.sqlite','embeddings/index.sqlite','library/membership.json'}
    old_records=data(path,'records');old_vectors=data(directory/'embeddings/index.sqlite','vectors')
    assert all(retained_records.get(k)==v for k,v in old_records.items())
    assert all(retained_vectors.get(k)==v for k,v in old_vectors.items())
    targets.extend(files)
    for manifest in (ROOT/'data/library/combined-publications').glob('*.json'):
        if read_json(manifest).get('generation')==directory.name:targets.append(manifest)
plan={'status':'planned','targets':[str(p) for p in targets], 'logical_bytes':sum(p.stat().st_size for p in targets),
      'verification':'All combined asset records and vector bytes remain in current/source-owned publications',
      'originals_reports_faults_previews_removed':False,'faults':[]}
if args.apply:
    plan['sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in targets}
    for p in targets:
        try:p.unlink()
        except OSError as exc:plan['faults'].append({'path':str(p),'reason':str(exc)})
    plan['status']='faulty' if plan['faults'] else 'passed'
    atomic_json(receipt,plan)
print(json.dumps(plan,indent=2))
