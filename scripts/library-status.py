"""Small read-only progress snapshot, without scanning sources or importing models."""
from pathlib import Path
import json
import sqlite3
from contextlib import closing

root=Path(__file__).resolve().parents[1]
jobs=root/'data/library/jobs.sqlite'
progress=root/'data/library/processing-status.json'
result={'stages':{},'processing':json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else {'status':'idle'}}
if jobs.exists():
    with closing(sqlite3.connect(jobs.as_uri()+'?mode=ro',uri=True)) as db:
        for stage,status,count in db.execute('SELECT stage,status,COUNT(*) FROM jobs GROUP BY stage,status'):
            result['stages'].setdefault(stage,{})[status]=count
path=root/'data/library/generations/work/catalog.sqlite'
if path.exists():
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        for (payload,) in db.execute('SELECT record FROM assets'):
            row=json.loads(payload)
            state=row['processing'].get('embeddings','pending')
            result['stages'].setdefault('embeddings',{}).setdefault(state,0)
            result['stages']['embeddings'][state]+=1
print(json.dumps(result))
