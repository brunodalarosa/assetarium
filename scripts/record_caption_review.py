"""Record only AI technical review, bound to viewed results and image hashes."""
import argparse
from pathlib import Path
import json
from datetime import datetime, timezone

from local_asset_library.config import load_project_config
from local_asset_library.catalog import detail, save_json
from local_asset_library.captions import file_hash
from local_asset_library.caption_quality import review_findings

parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=["library"])
parser.add_argument("--notes", type=Path, required=True)
parser.add_argument("--source", help="Registered asset source key; default is the whole library")
parser.add_argument("--reviewer", default="Codex AI")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
config = load_project_config(root)
if args.source:
    from local_asset_library import sources
    config = sources.bound(config, sources.get_source(config, args.source))
import uuid
from local_asset_library.incremental import working,update_record
from local_asset_library.membership import membership
from local_asset_library.gpu_queue import lease
config=working(config)
notes=json.loads(args.notes.read_text(encoding='utf-8'))
allowed=set(membership(config)['asset_ids'])
if not isinstance(notes.get('assets'),dict) or not notes['assets'] or not set(notes['assets']).issubset(allowed):
    raise ValueError('Review must name configured library members')
receipts=[]
prepared=[]
with lease(config,'caption-review',timeout=0,resource='operations'):
    for identifier,note in notes['assets'].items():
        record=detail(config,identifier)
        provenance=record.get('caption_provenance')
        if not provenance:
            raise ValueError('No generated caption evidence to review: '+identifier)
        result_path=config.output_path('data',provenance['result_path'].removeprefix('data/'))
        result=json.loads(result_path.read_text(encoding='utf-8'))
        if result['provenance']['fingerprint']!=provenance['fingerprint']:
            raise ValueError('Review/result fingerprint mismatch')
        for view in provenance.get('input_views',[]):
            if file_hash(config.output_path('data',view['path'][5:]))!=view['sha256']:
                raise ValueError('Review input pixels changed')
        findings=review_findings(note)
        record['caption_provenance']={**provenance,'ai_review':'technically_reviewed','ai_review_observations':note,
            'visual_faults':findings,'ai_review_scope':notes['scope']}
        prepared.append(record)
        receipts.append({'asset_id':identifier,'result_sha256':file_hash(result_path),'caption_fingerprint':provenance['fingerprint'],
            'findings':findings,'original_provenance':provenance})
    receipt={'status':'prepared','reviewer':args.reviewer+'; not owner approval','scope':notes['scope'],
        'utc':datetime.now(timezone.utc).isoformat(),'receipts':receipts,'owner_states_modified':False,'original_results_modified':False}
    path=config.output_path('data','library/reviews/'+uuid.uuid4().hex+'.json')
    save_json(path,receipt)
    # Original review provenance is on disk before any metadata replacement.
    for record in prepared:
        update_record(config,record)
    receipt['status']='technically_reviewed'
    save_json(path,receipt)
print(json.dumps({'assets':len(receipts),'receipt':str(path),'publish':'Use the explicit library refresh after review.'}))
