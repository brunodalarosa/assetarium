"""Add only this server; byte backups and parsed preservation checks before writing.

--opencode-config PATH also registers with that OpenCode config (omitted: OpenCode is skipped).
--snippets-only writes this checkout's client snippets under ignored data/mcp/clients/ and edits
no client configuration. The tracked docs/mcp/clients/ files are neutral examples; the older
docs/mcp/codex-setup.toml and opencode-setup.json are kept as recorded evidence.
"""
import argparse
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import tomllib

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from local_asset_library.config import venv_python
from local_asset_library.setup_agent import snippets as client_snippets
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--opencode-config')
parser.add_argument('--snippets-only',action='store_true')
args=parser.parse_args()
server='local_asset_library'
python=str(venv_python(root,'.venv-mcp'))
entry=str(root/'scripts/asset-mcp.py')
if not Path(python).is_file() or not Path(entry).is_file():
    raise SystemExit('Server not installed; no configuration edited')
generated={item['id']:item['text'] for item in client_snippets(root)}
clients=root/'data/mcp/clients'
clients.mkdir(parents=True,exist_ok=True)
for name,suffix in (('codex','.toml'),('claude-code','.txt'),('opencode','.json'),('generic','.json')):
    (clients/(name+suffix)).write_text(generated[name]+'\n',encoding='utf-8')
if args.snippets_only:
    raise SystemExit(print('Wrote '+', '.join(sorted(p.name for p in clients.iterdir()))))
backup=root/'data/mcp/config-backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup.mkdir(parents=True,exist_ok=False)
codex=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'config.toml'
opencode=Path(args.opencode_config) if args.opencode_config else None
toml='\n'+generated['codex']
oc=json.loads(generated['opencode'])['mcp'][server]
records=[]
for client,path,parser in [('codex',codex,tomllib.loads),('opencode',opencode,json.loads)]:
    if path is None:
        records.append({'client':client,'status':'skipped','reason':'No --opencode-config given'})
        continue
    if not path.is_file():
        records.append({'client':client,'status':'pending','reason':'Discovered active file absent','path':str(path)})
        continue
    before=path.read_bytes()
    text=before.decode('utf-8-sig')
    old=parser(text)
    key='mcp_servers' if client=='codex' else 'mcp'
    if server in old.get(key,{}):
        raise SystemExit('Existing project server entry; do not overwrite without explicit review')
    if client=='codex':
        updated=text+toml
    else:
        # Strict JSON active configuration: append one key without rewriting unrelated bytes.
        if key in old:
            raise SystemExit('OpenCode already has MCP map; use reviewed merge, not this first-registration script')
        end=text.rfind('}')
        updated=text[:end].rstrip()+',\n  "mcp": '+json.dumps({server:oc},indent=2)+'\n'+text[end:]
    new=parser(updated)
    delta=new[key].pop(server)
    if key not in old:
        del new[key]
    if new!=old:
        raise SystemExit('Unrelated settings changed; no write')
    copied=backup/(client+path.suffix)
    copied.write_bytes(before)
    if copied.read_bytes()!=before:
        raise SystemExit('Backup verification failed; no write')
    after=(b'\xef\xbb\xbf' if before.startswith(b'\xef\xbb\xbf') else b'')+updated.encode('utf-8')
    # Refuse to clobber a concurrent edit after preparation.
    if path.read_bytes()!=before:
        raise SystemExit('Configuration changed concurrently; no write')
    path.write_bytes(after)
    if path.read_bytes()!=after:
        raise SystemExit('Configuration write verification failed')
    records.append({'client':client,'status':'registered','path':str(path),'backup':str(copied),
        'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest(),
        'unrelated_settings_preserved':True,'entry':delta})
receipt={'records':records,'restore':'Close client, verify current config has no later edits, copy exact backup bytes back to path. Backups may contain private settings; remain ignored and are never committed.'}
(backup/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
(root/'data/mcp/registration.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
