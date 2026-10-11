"""Recompute arithmetic from saved evidence only; no inference or ranking changes."""
from pathlib import Path
from contextlib import closing
import argparse
import json
import re
import statistics

from local_asset_library.catalog import encoded, save_json
from local_asset_library.captions import file_hash
from local_asset_library.config import load_config
from local_asset_library.evaluation import verify_freeze, count_quality, percentile, expansion_gate, relevance_metrics
from local_asset_library.retrieval import index_database

root=Path(__file__).resolve().parents[1]
config=load_config(root/'config.example.toml',root)
verify_freeze(root)
parser=argparse.ArgumentParser()
parser.add_argument('--owner-labels',type=Path,help='Reviewed exported artifact; never implies pilot approval')
parser.add_argument('--run-name',default='run',help='Saved benchmark directory name')
args=parser.parse_args()
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',args.run_name):
    raise SystemExit('Use a short lowercase run name')
run_dir=config.output_path('data','evaluation/'+args.run_name)
publish_dir=root/'docs/evaluation' if args.run_name=='run' else run_dir/'report'
protocol=json.loads((root/'docs/evaluation/protocol.json').read_text())
spec=json.loads((root/'docs/evaluation/queries.json').read_text())
labels=json.loads((root/'docs/evaluation/labels-provisional.json').read_text())
if args.owner_labels:
    candidate=json.loads(args.owner_labels.read_text())
    if candidate.get('owner_review')!='reviewed' or candidate.get('status')!='owner_reviewed' or any(v['review']!='owner_reviewed' for v in candidate['queries'].values()):
        raise SystemExit('Incomplete explicit owner relevance review; keep provisional status')
    if candidate['complete_pool']!=labels['complete_pool'] or set(candidate['queries'])!=set(labels['queries']):
        raise SystemExit('Owner artifact pool/query mismatch')
    labels=candidate
for value in labels['queries'].values():
    if set(value['grades']) != set(labels['complete_pool']):
        raise SystemExit('Incomplete graded pool; cannot calculate ranked relevance')
manifest=json.loads((run_dir/'manifest.json').read_text())
cold=json.loads((run_dir/'cold.json').read_text())
if manifest['state']!='complete' or cold['state']!='complete':
    raise SystemExit('Incomplete benchmark; preserve partial evidence, do not report complete metrics')
entries=manifest['entries']
raw={}
for e in entries:
    path=root/e['raw_path']
    if file_hash(path)!=e['raw_sha256']:
        raise SystemExit('Raw evidence changed: '+e['raw_path'])
    if e['status']=='complete':
        raw[(e['query_id'],e['mode'],e['repeat'])]=json.loads(path.read_text())
        e['quality']=relevance_metrics(e['asset_ids'],labels['queries'][e['query_id']]['grades'])
first=[e for e in entries if e['repeat']==1]
summary={}
exact=[q['id'] for q in spec['queries'] if q['category']=='exact']
negative=[q['id'] for q in spec['queries'] if q['category']=='negative']
positive=[q['id'] for q in spec['queries'] if q['category']!='negative']
for mode in protocol['modes']:
    all_mode=[e for e in entries if e['mode']==mode]
    once=[e for e in first if e['mode']==mode]
    good=[e for e in all_mode if e['status']=='complete']
    onegood=[e for e in once if e['status']=='complete']
    negatives=[e for e in onegood if e['query_id'] in negative]
    vals=[e['seconds'] for e in good]
    diversity=[a for e in onegood for a in e['asset_ids']]
    ctx=lambda key:[e['context'][key] for e in good if e['context'][key] is not None]
    filter_entries=[e for e in onegood if e['query_id'].startswith('F')]
    summary[mode]={
        'positive':count_quality(once,positive),'natural':count_quality(once,protocol['natural_language_gate_ids']),
        'exact':count_quality(once,exact),
        'exact_success_ids':[e['query_id'] for e in onegood if e['query_id'] in exact and e['quality']['hit5']],
        'split_quality':{s:{'positive':count_quality(once,[q['id'] for q in spec['queries'] if q['split']==s and q['category']!='negative']),
                            'natural':count_quality(once,[q['id'] for q in spec['queries'] if q['split']==s and q['id'] in protocol['natural_language_gate_ids']])}
                         for s in ['development','held_out']},
        'negative_queries':len(negative),'negative_evaluated':len(negatives),
        'negative_queries_with_candidates':sum(bool(e['negative_returned_candidates']) for e in negatives),
        'negative_candidate_count':sum(e['negative_returned_candidates'] for e in negatives),
        'negative_strong_claim_count':sum(e['negative_strong_claims'] for e in negatives),
        'filter_queries_evaluated':len(filter_entries),'filter_results_checked':sum(len(e['asset_ids']) for e in filter_entries),
        'filter_violations':sum(len(e['filter_violations']) for e in all_mode if e['status']=='complete'),
        'unique_assets_across_text_queries':len(set(diversity)),'returned_slots_first_repeat':len(diversity),
        'unique_assets_across_positive_queries':len({a for e in onegood if e['query_id'] in positive for a in e['asset_ids']}),
        'returned_positive_slots_first_repeat':sum(len(e['asset_ids']) for e in onegood if e['query_id'] in positive),
        'within_shortlist_duplicate_slots':sum(len(e['asset_ids'])-len(set(e['asset_ids'])) for e in onegood),
        'warm_samples':len(vals),'warm_p50_seconds':statistics.median(vals) if vals else None,'warm_p95_seconds':percentile(vals),
        'context_max_characters':max(ctx('exact_characters'),default=0),
        'context_max_characters_div4_tokens':max(ctx('characters_div4_estimator'),default=0),
        'context_max_embeddinggemma_tokenizer_tokens':max(ctx('embeddinggemma_tokenizer_tokens'),default=0),
        'context_median_characters':statistics.median(ctx('exact_characters')) if good else None,
        'failures':sum(e['status']=='faulty' for e in all_mode),
    }
    summary[mode]['repeat_rank_changes']=sum(e['asset_ids'] != [r['asset_id'] for r in raw[(e['query_id'],mode,2)]['response']['results']]
        for e in onegood if (e['query_id'],mode,2) in raw)
reference=[e for e in first if e['mode']=='reference' and e['status']=='complete']
reference_runs=[e for e in entries if e['mode']=='reference' and e['status']=='complete']
refs=json.loads(config.output_path('data','evaluation/references/manifest.json').read_text())['references']
for e in reference:
    q=next(q for q in refs if q['id']==e['query_id'])
    grades={a:g for a,g in labels['queries'][q['id']]['grades'].items() if a!=q['asset_id']}
    e['other_asset_quality']=relevance_metrics([a for a in e['asset_ids'] if a!=q['asset_id']],grades)
costs={'caption':json.loads(config.output_path('data','captions/measurements.json').read_text()),
       'embedding_initial_index':{k:v for k,v in json.loads(config.output_path('data','embeddings/initial-conservative-exclusions.json').read_text()).items() if k!='outcomes'},
       'embedding_corrected_and_reused_index':{k:v for k,v in json.loads(config.output_path('data','embeddings/demonstrations.json').read_text()).items() if k in {'first_index','unchanged_reindex','resources'}},
       'measurement_scope':'Existing step 4/5 receipts, not new captioning/indexing. Initial indexing excludes runtime startup and model download; corrected pass reused prior vectors.'}
with closing(index_database(config,True)) as db:
    pool={'logical_assets':40,'vectors':db.execute('SELECT count(*) FROM vectors').fetchone()[0],
          'channel_vectors':dict(db.execute('SELECT channel,count(*) FROM vectors GROUP BY channel')),
          'failed_jobs':db.execute("SELECT count(*) FROM jobs WHERE status='failed'").fetchone()[0]}
gate=expansion_gate(summary,protocol,labels['status'])
result={'version':protocol['version'],'status':gate['status'],'labels_status':labels['status'],
        'owner_relevance_review':labels['owner_review'],'pilot_decision':'pending','gate':gate,'pool':pool,
        'modes':summary,'reference':reference,'cold':cold,'costs':costs,'per_query':first,
        'reference_timing':{'samples':len(reference_runs),
                            'warm_p50_seconds':statistics.median(e['seconds'] for e in reference_runs),
                            'warm_p95_seconds':percentile([e['seconds'] for e in reference_runs])},
        'resources':manifest['resources'],'freeze_sha256':manifest['freeze_sha256'],
        'contract_fingerprint':manifest['contract_fingerprint'],'retrieval_sha256':manifest['retrieval_sha256'],
        'measurement_definitions':protocol['policy'],
        'raw_manifest':{'path':(run_dir/'manifest.json').relative_to(root).as_posix(),'sha256':file_hash(run_dir/'manifest.json')}}
save_json(publish_dir/'results.json',result)
# First repeat: complete channel lists, compact responses and timing for each comparison.
# Second-repeat evidence remains local, hash-bound in the manifest, never discarded.
with (publish_dir/'rankings.jsonl').open('w',encoding='utf-8',newline='\n') as stream:
    for e in first:
        stream.write(encoded({'query_id':e['query_id'],'mode':e['mode'],'split':e['split'],
                              'raw_sha256':e['raw_sha256'],'evidence':raw.get((e['query_id'],e['mode'],1),e)})+'\n')
print(json.dumps({'status':result['status'],'gate':gate,'modes':summary,'reference':reference},indent=2))
