"""Validate owner data and recompute quality from frozen saved rankings only."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import sys

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'src'))
from local_asset_library.evaluation import verify_freeze, relevance_metrics, count_quality, expansion_gate
verify_freeze(root)
source=Path(sys.argv[1])
blob=source.read_bytes()
labels=json.loads(blob)
old=json.loads((root/'docs/evaluation/labels-provisional.json').read_text())
spec=json.loads((root/'docs/evaluation/queries.json').read_text())
protocol=json.loads((root/'docs/evaluation/protocol.json').read_text())
if labels.get('status')!='owner_reviewed' or labels.get('owner_review')!='reviewed':
    raise SystemExit('Faulty owner artifact: review status missing')
if labels['complete_pool']!=old['complete_pool'] or set(labels['queries'])!=set(old['queries']):
    raise SystemExit('Faulty owner artifact: pool/query mismatch')
for value in labels['queries'].values():
    if value.get('review')!='owner_reviewed' or set(value['grades'])!=set(labels['complete_pool']):
        raise SystemExit('Faulty owner artifact: incomplete review/grades')
    relevance_metrics([],value['grades'])
saved=json.loads((root/'docs/evaluation/results.json').read_text())
entries=deepcopy(saved['per_query'])
for e in entries:
    e['quality']=relevance_metrics(e['asset_ids'],labels['queries'][e['query_id']]['grades'])
summary=deepcopy(saved['modes'])
for mode,value in summary.items():
    picked=[e for e in entries if e['mode']==mode]
    for field,ids in [('positive',[q['id'] for q in spec['queries'] if q['category']!='negative']),
                      ('natural',protocol['natural_language_gate_ids']),
                      ('exact',[q['id'] for q in spec['queries'] if q['category']=='exact'])]:
        value[field]=count_quality(picked,ids)
    value['exact_success_ids']=[e['query_id'] for e in picked if e['query_id'].startswith('E') and e['quality']['hit5']]
gate=expansion_gate(summary,protocol,labels['status'])
decision_path=root/'docs/mcp/pilot-decision.json'
decision=json.loads(decision_path.read_text(encoding='utf-8'))
if decision.get('status')!='approved' or decision.get('full_library_expansion_approved') is not False:
    raise SystemExit('Explicit separately recorded bounded pilot decision missing; do not infer it from labels')
gate.update(owner_approval='See separately recorded trusted-session decision',step7_authorized=True)
target=root/'docs/mcp'
target.mkdir(parents=True,exist_ok=True)
(target/'owner-labels.json').write_bytes(blob)
result={'owner_artifact_sha256':hashlib.sha256(blob).hexdigest(),'owner_queries':len(labels['queries']),
    'labels_status':labels['status'],'recomputed_from':'docs/evaluation/results.json saved first-repeat asset IDs',
    'no_inference_or_tuning':True,'modes':summary,'gate':gate,
    'pilot_decision':{'path':'docs/mcp/pilot-decision.json','sha256':hashlib.sha256(decision_path.read_bytes()).hexdigest(),
      'status':decision['status'],'scope':decision['scope']}}
(target/'owner-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'labels_status':result['labels_status'],'queries':result['owner_queries'],
    'gate':gate,'pilot_decision':result['pilot_decision']},indent=2))
