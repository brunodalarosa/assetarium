"""A real no-change refresh proof; refuses pending work before any processing call."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_config
from local_asset_library.incremental import refresh,process,publish,working,database_content
from local_asset_library.publication import generation
from local_asset_library.catalog import save_json
config=load_config(ROOT/'config.example.toml',ROOT)
out=ROOT/'data/library/verification/step8-no-change';out.mkdir(parents=True,exist_ok=False)
work=working(config)
before={'generation':generation(config),'catalog':database_content(work.output_path('data','catalog.sqlite'),'catalog'),
        'index':database_content(work.output_path('data','embeddings/index.sqlite'),'index')}
preview={stage:process(config,stage,1000,dry_run=True) for stage in ('inspection','caption','embeddings')}
if any(value['pending'] for value in preview.values()):
    save_json(out/'report.json',{'status':'faulty','reason':'Unexpected pending work; no actual process calls executed',
        'dry_runs':{k:{field:value for field,value in v.items() if field!='outcomes'} for k,v in preview.items()}})
    raise RuntimeError('Unexpected invalidation; resolve the application contract mismatch without retrying asset faults')
scan=refresh(config)
if not scan.get('no_change'):
    save_json(out/'report.json',{'status':'faulty','reason':'Scan reported changed inputs','scan':scan})
    raise RuntimeError('Collection changed; no no-change claim')
actual={stage:process(config,stage,1000) for stage in ('inspection','caption','embeddings')}
publication=publish(config)
after={'generation':generation(config),'catalog':database_content(work.output_path('data','catalog.sqlite'),'catalog'),
       'index':database_content(work.output_path('data','embeddings/index.sqlite'),'index')}
assert actual['inspection']['selected']==actual['caption']['selected']==actual['embeddings']['processed']==0
assert after==before and publication.get('no_change')
report={'status':'passed','before':before,'after':after,'scan':scan,'publication':publication,
    'stage_summaries':{k:{field:value for field,value in v.items() if field!='outcomes'} for k,v in actual.items()},
    'render_jobs':0,'caption_inference_jobs':0,'embedding_inference_jobs':0,'models_loaded':False,
    'method':'Dry-run refusal guard, actual no-change scan/cached process with no backend, stable verified DB contents and publication version.'}
save_json(out/'report.json',report)
print(json.dumps({k:v for k,v in report.items() if k not in {'scan','publication','stage_summaries'}}))
