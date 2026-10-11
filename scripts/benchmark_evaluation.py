"""Frozen pilot-only benchmark. Never reindex/caption; preserve full channel rankings.

Run warm comparison once, then separate --cold pass. Failed items are recorded, not retried.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import re
import subprocess
import sys
import time

from local_asset_library.catalog import encoded, save_json
from local_asset_library.config import load_config
from local_asset_library.captions import file_hash
from local_asset_library.evaluation import verify_freeze, ordered_queries, relevance_metrics, filter_violations

root = Path(__file__).resolve().parents[1]
config = load_config(root/'config.example.toml',root)
receipt = verify_freeze(root)
spec = json.loads((root/'docs/evaluation/queries.json').read_text())
protocol = json.loads((root/'docs/evaluation/protocol.json').read_text())
labels = json.loads((root/'docs/evaluation/labels-provisional.json').read_text())
refs = json.loads(config.output_path('data','evaluation/references/manifest.json').read_text())['references']
parser = argparse.ArgumentParser()
parser.add_argument('--cold',action='store_true')
parser.add_argument('--child',choices=protocol['modes']+['reference'])
parser.add_argument('--run-name',default='run',help='New evidence directory name for an explicitly requested reproduction')
args = parser.parse_args()
if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',args.run_name):
    raise SystemExit('Use a short lowercase run name')
target = config.output_path('data','evaluation/'+args.run_name)
target.mkdir(parents=True,exist_ok=True)

if args.cold:
    output = target/'cold.json'
    if output.exists():
        raise SystemExit('Cold evidence already exists; no unchanged retry')
    measurements = []
    for mode in protocol['modes']+['reference']:
        started = time.perf_counter()
        launched_epoch = time.time()
        run = subprocess.run([sys.executable,str(Path(__file__).resolve()),'--child',mode,'--run-name',args.run_name],cwd=root,
                             capture_output=True,text=True,encoding='utf-8',timeout=150,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        wall = time.perf_counter()-started
        if run.returncode:
            value = {'mode':mode,'status':'faulty','stderr':run.stderr,'stdout':run.stdout}
        else:
            value = json.loads(run.stdout.strip().splitlines()[-1])
            value['stderr'] = run.stderr
            # Same-host wall clock timestamps include process startup up to actual first completion.
            value['startup_and_first_query_wall_seconds'] = value['first_query_completed_epoch_seconds']-launched_epoch
        value['total_process_wall_seconds'] = wall
        measurements.append(value)
        save_json(output,{'measurements':measurements,'state':'partial' if len(measurements)<6 else 'complete',
                          'samples_per_mode':1,'disk_cache':'not purged','definition':'Fresh Python/model process; parent launch to child first-completion wall timestamp includes first response/tokenizer measurement, excludes second query and shutdown. OS disk cache not purged.'})
        print(json.dumps(value),flush=True)
    raise SystemExit(0)

from local_asset_library.embedding_backend import EmbeddingBackend
from local_asset_library.retrieval import SearchEngine, pilot_records
backend = None if args.child=='keyword' else EmbeddingBackend(config)
engine = SearchEngine(config,backend)
records = {r['asset_id']:r for r in pilot_records(config)}

def invoke(q,mode):
    reference = q['id'].startswith('R')
    if reference:
        assert file_hash(root/q['path'])==q['sha256']
    response,evidence = engine.search('' if reference else q['text'],mode,
                                      q['path'] if reference else None,q.get('filters',{}),
                                      exclude_image_hashes={q['parent_sha256'],q['sha256']} if reference else None)
    if reference:
        assert any(e.get('sha256')==q['parent_sha256'] for e in evidence['excluded'])
        assert all(r['input']['sha256'] not in {q['parent_sha256'],q['sha256']} for r in evidence['channel_rankings']['image'])
    text = encoded(response)
    assert len(text)==response['serialized_characters'] <= 6000
    evidence['context_measurement'] = {'exact_characters':len(text),'characters_div4_estimator':response['estimated_tokens'],
        'embeddinggemma_tokenizer_tokens':len(backend.model.tokenizer.encode(text,add_special_tokens=False)) if backend else None,
        'tokenizer': 'pinned EmbeddingGemma-2 tokenizer; surrogate, not agent billing/context tokens',
        'excluded':'images, transport/tool schema overhead; no agent integration at step 6'}
    return response,evidence

if args.child:
    q = refs[0] if args.child=='reference' else spec['queries'][0]
    response,evidence = invoke(q,args.child)
    first_end = time.perf_counter()
    first_epoch = time.time()
    first = {'search_seconds':evidence['elapsed_seconds'],'characters':response['serialized_characters']}
    response,evidence = invoke(q,args.child)
    print(json.dumps({'mode':args.child,'status':'complete','query_id':q['id'],
                      'model_load_seconds':backend.load_seconds if backend else 0,
                      'first_query_completed_epoch_seconds':first_epoch,
                      'first':first,'warm':{'search_seconds':evidence['elapsed_seconds'],'characters':response['serialized_characters']},
                      'after_first_query_seconds':time.perf_counter()-first_end}),flush=True)
    raise SystemExit(0)

output = target/'manifest.json'
if output.exists():
    raise SystemExit('Benchmark evidence already exists; do not retry unchanged queries')
manifest = {'started_at':datetime.now(timezone.utc).isoformat(),'freeze_sha256':file_hash(root/'docs/evaluation/freeze.json'),
            'contract_fingerprint':backend.fingerprint,'retrieval_sha256':file_hash(root/'src/local_asset_library/retrieval.py'),
            'protocol':protocol,'labels_status':labels['status'],'entries':[], 'state':'running',
            'pilot_assets':len(records),'held_out_tuning':False}
save_json(output,manifest)
# Generic runtime priming has no evaluation labels/results and is never tuned.
backend.text('runtime warmup')
for q in ordered_queries(spec['queries']+refs):
    modes = ['reference'] if q['id'].startswith('R') else protocol['modes']
    for mode in modes:
        for repeat in range(protocol['warm_repeats']):
            path = target/f'{q["id"]}-{mode}-{repeat+1}.json'
            try:
                response,evidence = invoke(q,mode)
                ids = [r['asset_id'] for r in response['results']]
                quality = relevance_metrics(ids,labels['queries'][q['id']]['grades'])
                item = {'query_id':q['id'],'split':q['split'],'category':q.get('category','reference'),'mode':mode,
                        'repeat':repeat+1,'status':'complete','quality':quality,
                        'asset_ids':ids,'seconds':evidence['elapsed_seconds'],
                        'context':evidence['context_measurement'],
                        'filter_violations':filter_violations(response,q,records),
                        'negative_returned_candidates':len(ids) if q.get('category')=='negative' else None,
                        'negative_strong_claims':sum(r['match_status']!='weak_unvalidated' for r in response['results']) if q.get('category')=='negative' else None,
                        'excluded_rows':len(evidence['excluded'])}
                if q['id'].startswith('R'):
                    cross = {a:g for a,g in labels['queries'][q['id']]['grades'].items() if a!=q['asset_id']}
                    item['same_asset_hit5']=int(q['asset_id'] in ids)
                    item['other_asset_quality']=relevance_metrics([a for a in ids if a!=q['asset_id']],cross,k=5)
                    item['limitation']=q['limitation']
                save_json(path,evidence)
            except (OSError,ValueError,RuntimeError,KeyError,AssertionError) as exc:
                item={'query_id':q['id'],'split':q['split'],'category':q.get('category','reference'),
                      'mode':mode,'repeat':repeat+1,'status':'faulty','error':str(exc),'type':type(exc).__name__}
                save_json(path,item)
            item['raw_path']=path.relative_to(root).as_posix()
            item['raw_sha256']=file_hash(path)
            manifest['entries'].append(item)
            save_json(output,manifest)
            if item['status']=='faulty':
                break  # No unchanged retry after a failure.
        print(json.dumps({'query':q['id'],'mode':mode,'split':q['split'],'status':item['status']}),flush=True)
manifest.update(state='complete',finished_at=datetime.now(timezone.utc).isoformat(),resources=backend.resources())
save_json(output,manifest)
print(json.dumps({'completed':len(manifest['entries']),'faulty':sum(e['status']=='faulty' for e in manifest['entries']),
                  'manifest':str(output)}),flush=True)
