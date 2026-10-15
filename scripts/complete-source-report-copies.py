"""Complete historical report copies after the Windows writer defect fix.

This does not reprocess assets, retry failed assets, or repeat migration moves.
The original migration receipt and all source reports remain unchanged.
"""
from pathlib import Path
import json
import re
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from local_asset_library.config import load_config
from local_asset_library.sources import registry,bound,owners
from local_asset_library.source_migration import _partition
from local_asset_library.publication import read_json,atomic_json,filesystem_path

config=load_config(root/'config.example.toml',root)
original=read_json(root/'data/library/source-migration/latest.json')
mapping=owners(config);by_key={s['key']:s for s in registry(config)['sources']}
saved=[];faults=[]
for item in original['faults']:
    path=Path(item['path'])
    if not path.is_relative_to(root/'data') or path.suffix not in {'.json','.jsonl'}:
        faults.append(item);continue
    relative=path.relative_to(root/'data').as_posix()
    text=path.read_text(encoding='utf-8')
    relevant={mapping[i] for i in set(re.findall(r'asset_[0-9a-f]{32}',text)) if i in mapping}
    value=[json.loads(line) for line in text.splitlines() if line.strip()] if path.suffix=='.jsonl' else json.loads(text)
    for key in sorted(relevant):
        target=bound(config,by_key[key]).output_path('data','history/shared-reports/'+relative)
        if path.suffix=='.jsonl':target=target.with_suffix(target.suffix+'.json')
        expected=_partition(value,key,mapping)
        try:
            if not Path(filesystem_path(target)).exists():
                atomic_json(target,expected)
                assert read_json(target)==expected
                saved.append(str(target))
        except (OSError,ValueError) as exc:
            faults.append({'path':str(target),'reason':str(exc)})
report={'status':'passed' if not faults else 'faulty','original_migration_receipt':original['evidence'],
        'original_faults_retained':len(original['faults']),'completed_copies':saved,'faults':faults,
        'asset_processing_or_moves_repeated':False}
atomic_json(root/'data/library/source-migration/report-copies-completion.json',report)
print(json.dumps({'status':report['status'],'completed_copies':len(saved),'faults':faults},indent=2))
sys.exit(bool(faults))
