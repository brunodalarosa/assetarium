"""Preservation and current-input checks before and after repaired captions."""
import sys,json,hashlib,sqlite3
from pathlib import Path
from collections import Counter,defaultdict
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_config
from local_asset_library.catalog import walk_source,snapshot,digest
from local_asset_library.membership import records
from local_asset_library.publication import generation,atomic_json
from local_asset_library.retrieval import source_check,resolved_detail
from local_asset_library.incremental import working,process
folder=ROOT/'data/texture-repairs/20261014'
before=json.loads((folder/'before.json').read_text(encoding='utf-8'))
c=load_config(ROOT/'config.example.toml',ROOT)
c=replace(c,catalog_generation=generation(c))
now={r['asset_id']:r for r in records(c)}
targets=set(before['targets'])
changed=[k for k,r in before['records'].items() if k not in targets and r!=now[k]]
owner_changes=[k for k,r in before['records'].items() if r.get('owner_overlay')!=now[k].get('owner_overlay')]
outputs=[p for p,h in before['outputs'].items() if not (ROOT/p).exists() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
with sqlite3.connect(c.output_path('data','embeddings/index.sqlite')) as db:
    vectors={r[0]:digest([hashlib.sha256(v).hexdigest() if isinstance(v,bytes) else v for v in r]) for r in db.execute('SELECT * FROM vectors')}
    counts=dict(db.execute('SELECT channel,count(*) FROM vectors GROUP BY channel'))
    integrity=db.execute('PRAGMA quick_check').fetchone()[0]
    image_ids={r[0] for r in db.execute("SELECT DISTINCT asset_id FROM vectors WHERE channel='image'")}
with sqlite3.connect(c.output_path('data','catalog.sqlite')) as db:
    catalog_integrity=db.execute('PRAGMA quick_check').fetchone()[0]
old_vectors=[k for k,h in before['vectors'].items() if vectors.get(k)!=h]
outcomes={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (folder/'outcomes').glob('*.json')}
successful=[k for k,v in outcomes.items() if v['status']=='complete']
not_attempted=targets-set(outcomes)
failures={}
for identifier in successful:
    try:
        source_check(c,now[identifier])
        resolved=resolved_detail(c,identifier)
        if not resolved['texture_overrides']: raise ValueError('Missing import overrides')
        if identifier not in image_ids: raise ValueError('No image-search vector')
        result=json.loads(Path(outcomes[identifier]['result_path']).read_text(encoding='utf-8'))
        if result['status']!='complete' or not all(s['unchanged'] for s in result['sources']): raise ValueError('Invalid render/source evidence')
    except (OSError,ValueError,KeyError) as exc: failures[identifier]=str(exc)
pack_counts=defaultdict(Counter)
for k in targets:
    pack_counts[now[k]['pack_id']]['recovered' if k in successful else 'retained_fault']+=1
checks={'originals_unchanged':before['source']==snapshot(walk_source(c)),
        'unrelated_records_unchanged':not changed,'owner_overlays_unchanged':not owner_changes,
        'old_outputs_unchanged':not outputs,'old_vectors_unchanged':not old_vectors,
        'recovered_sources_and_image_search_valid':not failures,'catalog_integrity':catalog_integrity=='ok','index_integrity':integrity=='ok'}
receipt={'status':'passed' if all(checks.values()) else 'verification_fault','generation':c.catalog_generation,
         'checks':checks,'pack_results':pack_counts,'recovered':len(successful),'retained_faults':len(targets)-len(successful),
         'unchanged_faults_not_retried':len(not_attempted),'new_processing_failures':{k:v for k,v in outcomes.items() if v['status']!='complete'},
         'changed_unrelated_records':changed,'changed_owner_overlays':owner_changes,'changed_outputs':outputs,
         'changed_old_vectors':old_vectors,'recovered_validation_failures':failures,'vector_counts':counts,
         'owner_accuracy_artistic_review':'pending','descriptions':dict(Counter(now[k]['processing']['caption'] for k in successful))}
receipt['recovered_with_retained_geometry_faults'] = [k for k in successful if any(
    f.get('kind') == 'overlapping_duplicate_faces' for f in now[k].get('inspection_run', {}).get('source_faults', []))]
label=sys.argv[1] if len(sys.argv)>1 else 'verification'
atomic_json(folder/(label+'.json'),receipt)
print(json.dumps({k:v for k,v in receipt.items() if k not in {'new_processing_failures'}},default=dict))
sys.exit(not all(checks.values()))
