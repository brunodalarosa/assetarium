"""Read-only benchmark/pilot preservation checks; no inference or processing expansion."""
from pathlib import Path
from contextlib import closing
import json
import math
from html.parser import HTMLParser

from local_asset_library.catalog import encoded, save_json, verify_source
from local_asset_library.captions import file_hash
from local_asset_library.config import load_project_config
from local_asset_library.evaluation import verify_freeze, filter_violations
from local_asset_library.retrieval import pilot_records, resolved_detail, index_database, checked_vector

root=Path(__file__).resolve().parents[2]
config=load_project_config(root)
verify_freeze(root)
manifest=json.loads(config.output_path('data','evaluation/run/manifest.json').read_text())
assert manifest['state']=='complete'
records={r['asset_id']:r for r in pilot_records(config)}
spec=json.loads((root/'docs/evaluation/queries.json').read_text())
queries={q['id']:q for q in spec['queries']}
refs=json.loads(config.output_path('data','evaluation/references/manifest.json').read_text())['references']
queries.update({q['id']:q for q in refs})
assert len(manifest['entries'])==328 and len(records)==40
assert not any(e['status']!='complete' for e in manifest['entries'])
held_out=False
rankings=0
for e in manifest['entries']:
    if e['split']=='held_out':
        held_out=True
    assert not held_out or e['split']=='held_out'
    path=root/e['raw_path']
    assert file_hash(path)==e['raw_sha256']
    value=json.loads(path.read_text())
    response=value['response']
    assert len(encoded(response))==response['serialized_characters']<=6000
    ids=[r['asset_id'] for r in response['results']]
    assert len(ids)==len(set(ids)) and set(ids)<=records.keys()
    assert not filter_violations(response,queries[e['query_id']],records)
    for channel, ranking in value['channel_rankings'].items():
        rankings+=1
        rid=[r['asset_id'] for r in ranking]
        assert len(rid)==len(set(rid)) and set(rid)<=records.keys()
        assert not filter_violations({'results':[{'asset_id':a} for a in rid]},queries[e['query_id']],records)
        assert all(math.isfinite(r['score']) for r in ranking)
        if channel!='keyword':
            assert all(-1.00001<=r['score']<=1.00001 for r in ranking)
    if e['mode']!='keyword':
        metrics=value['query_metrics']
        assert metrics['finite'] and metrics['dimensions']==768 and abs(metrics['norm']-1)<1e-5
    if e['mode']=='reference':
        q=queries[e['query_id']]
        assert value['query_metrics']['modality']=='image' and value['query_metrics']['pixel_tensor_shapes']
        assert all(r['input']['sha256'] not in {q['sha256'],q['parent_sha256']} for r in value['channel_rankings']['image'])
        assert any(r.get('sha256')==q['parent_sha256'] for r in value['excluded'])
for identifier in records:
    resolved_detail(config,identifier)
with closing(index_database(config,True)) as db:
    rows=db.execute('SELECT * FROM vectors').fetchall()
    assert len(rows)==208
    for row in rows:
        checked_vector(row,manifest['contract_fingerprint'])
    image_hashes={json.loads(row[11])['sha256'] for row in rows if row[2]=='image'}
    assert all(q['sha256'] not in image_hashes for q in refs)
before=json.loads(config.output_path('data','evaluation/preservation-before.json').read_text())
after={'catalog_sha256':file_hash(config.output_path('data','catalog.sqlite')),
       'index_sha256':file_hash(config.output_path('data','embeddings/index.sqlite')),
       'pilot_sha256':file_hash(config.output_path('data','pilot/selection-manifest.json'))}
assert before==after
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images=[]
    def handle_starttag(self,tag,attrs):
        if tag=='img':
            self.images.append(dict(attrs)['src'])
review=config.output_path('data','evaluation/relevance-review.html')
parser=Links()
parser.feed(review.read_text(encoding='utf-8'))
assert len(parser.images)==1444 and all((review.parent/p).is_file() for p in parser.images)
source=verify_source(config)
area_bytes={area:sum(p.stat().st_size for p in (root/area).rglob('*') if p.is_file())
            for area in ('models','data','cache','logs','scratch','.venv','.venv-caption','.venv-embedding')}
from local_asset_library.model_storage import project_model_bytes
area_bytes['models']=project_model_bytes(config)
generated=sum(v for k,v in area_bytes.items() if k!='models')
assert area_bytes['models']<8*1024**3 and generated<20*1024**3
verification={'status':'pass','complete_searches':328,'channel_rankings_checked':rankings,
              'finite_normalized_persisted_vectors':208,'reference_parent_exclusion_queries':4,
              'review_image_links_checked':len(parser.images),'unchanged_catalog_index_pilot':after,
              'source':source,'area_bytes':area_bytes,'total_managed_bytes':sum(area_bytes.values()),
              'generated_budget_remaining_bytes':20*1024**3-generated,
              'model_budget_remaining_bytes':8*1024**3-area_bytes['models'],
              'owner_quality_approval':'pending','step7_authorized':False}
save_json(root/'docs/evaluation/verification.json',verification)
print(json.dumps(verification))
