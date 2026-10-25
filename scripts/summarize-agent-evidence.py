"""Check actual client events/manifests against recorded returns; no agent simulation."""
from pathlib import Path
import hashlib
import json
import sys
import tomllib

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from local_asset_library.catalog import encoded
from local_asset_library.config import load_project_config
config=load_project_config(root)
results={}
queries={'codex':'small stylized red apple prop with a leaf','opencode':'small stylized red apple prop with leaf'}
for client in ['codex','opencode']:
    directory=root/'data/mcp/client-runs'/client
    process=json.loads((directory/'process.json').read_text(encoding='utf-8'))
    if process.get('status')=='running':raise SystemExit('Client still running; preserve pending state')
    events=[]
    for line in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    audits=[]
    for path in (root/'data/mcp/runs').glob('*/calls.jsonl'):
        rows=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
        if rows and rows[0]['arguments'].get('query')==queries[client]:audits.append((path,rows))
    if len(audits)!=1:raise SystemExit('Ambiguous or missing workflow audit; no fabricated connection result')
    path,rows=audits[0]
    manifest_path=root/'data/exports'/(client+'-selection.json')
    manifest=None
    faults=[]
    if manifest_path.exists():
        try:manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        except ValueError as exc:faults.append('Client final output is not JSON: '+str(exc))
    else:faults.append('Client did not produce a final selection manifest')
    verified=False
    manifest_paths=False
    if manifest is not None:
        try:
            source=manifest['selected_source']
            matching=[r['response'] for r in rows if r['tool']=='get_asset' and r['response'].get('selected_source')==source]
            assert matching,'Manifest source differs from actual tool return'
            assert any(r['dependencies']==manifest['dependencies'] for r in matching),'Manifest dependencies differ from tool return'
            selected=config.source_file(source['path'])
            assert str(selected)==source['resolved_path']
            assert hashlib.sha256(selected.read_bytes()).hexdigest()==source['sha256']
            for d in manifest['dependencies']:
                if d.get('required_for_render') is False:continue
                dep=config.source_file(d['path'])
                assert str(dep)==d['resolved_path'] and hashlib.sha256(dep.read_bytes()).hexdigest()==d['sha256']
            manifest_paths=True
            # Final vision claims are checked together with real image transport and observations.
            verified=bool(manifest.get('preview_inspected') is True and manifest.get('observed_image_features')
                and any(r['image_bytes']>0 for r in rows) and any(r['tool']=='search_assets' for r in rows)
                and process['process_status']=='completed')
        except (AssertionError,KeyError,TypeError,ValueError,OSError) as exc:
            faults.append('Manifest verification faulty: '+str(exc))
    if not verified and process.get('reason'):faults.append(process['reason'])
    if manifest is None:
        # Preserve a clearly labeled partial receipt, never invent a local agent's final choice.
        details=next((r['response'] for r in reversed(rows) if r['tool']=='get_asset'),{})
        partial={'client':client,'query':queries[client],'status':'faulty','preview_inspected':False,
            'observed_image_features':[],'asset_id':details.get('asset_id'),
            'selected_source':details.get('selected_source'),'dependencies':details.get('dependencies',[]),
            'manifest_origin':'Harness preservation of partial tool returns; no final agent selection or preview inspection verified',
            'faults':faults,'limitations':['Actual local-model selection/vision remains unverified; no unchanged retry.']}
        partial_path=manifest_path.with_name(client+'-partial-receipt.json')
        partial_path.write_text(json.dumps(partial,indent=2)+'\n',encoding='utf-8')
    if client=='codex':
        client_calls=[e['item'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='mcp_tool_call']
        usage=[e['usage'] for e in events if e.get('type')=='turn.completed']
        image_consumption='PNG ImageContent in completed get_asset event; image-specific agent observations in commentary/final manifest; inspected evidence image matched those observations'
    else:
        client_calls=[e['part'] for e in events if e.get('type')=='tool_use']
        usage=[e['part']['tokens'] for e in events if e.get('type')=='step_finish' and 'tokens' in e.get('part',{})]
        image_consumption='PNG attachment in completed tool event; final image-specific agent observations required before marking vision verified'
    assert len(client_calls)==len(rows),'Client call count differs from independent server audit'
    value={'client':client,'workflow_verified':verified,'status':'verified_with_asset_limitations' if verified else 'faulty_or_unverified',
        'configured_model':'gpt-6.1-sol' if client=='codex' else 'ollama/qwen3.8:local-agent',
        'model_location':'cloud' if client=='codex' else 'local Ollama localhost:11434',
        'client_process':{k:v for k,v in process.items() if k not in ('actual_agent_workflow_verified','note')},
        'manifest':manifest_path.relative_to(root).as_posix() if manifest is not None else None,
        'manifest_source_dependencies_verified':manifest_paths,'tool_calls':len(rows),
        'per_call':[{'tool':r['tool'],'characters':r['text_characters'],'utf8_bytes':r['text_utf8_bytes'],
                     'heuristic_tokens':r['heuristic_tokens'],'image_bytes':r['image_bytes'],
                     'image_base64_characters':r['image_base64_characters'],'seconds':r['elapsed_seconds'],'is_error':r['is_error']} for r in rows],
        'returned_text_characters_total':sum(r['text_characters'] for r in rows),
        'returned_image_bytes_total':sum(r['image_bytes'] for r in rows),
        'actual_client_usage':usage,'usage_scope':'Whole client steps/session, includes instructions/schemas/repeated context/images; not retrieval-only or billing-savings proof',
        'image_evidence':image_consumption,'audit':path.relative_to(root).as_posix(),'faults':faults,
        'asset_limitations':manifest.get('limitations',[]) if manifest else ['Incomplete local workflow']}
    results[client]=value
registration=json.loads((root/'data/mcp/registration.json').read_text())
for r in registration['records']:
    parser=tomllib.loads if r['client']=='codex' else json.loads
    original=parser(Path(r['backup']).read_bytes().decode('utf-8-sig'))
    active=parser(Path(r['path']).read_bytes().decode('utf-8-sig'))
    key='mcp_servers' if r['client']=='codex' else 'mcp'
    assert active[key].pop('local_asset_library')==r['entry']
    if key not in original:del active[key]
    assert active==original
wire=json.loads((root/'data/mcp/protocol/final/wire.json').read_text())
tools=next(r['result']['tools'] for r in wire if 'tools' in r.get('result',{}))
summary={'clients':results,'two_tool_schema_characters':len(encoded(tools)),
    'schema_measurement':'Exact compact JSON of both Tool definitions including annotations, excluding initialization/instructions and transport envelope',
    'registration':registration['records'],'unrelated_active_settings_reverified':True,
    'cloud_disclosure':'Codex returns include descriptions, metadata, source/dependency paths and requested PNGs. The current cloud-backed verification chat also inspected the same PNG and reviewed bounded audit summaries. OpenCode inference uses the existing localhost Ollama provider; reviewing its evidence here does not make this whole task fully local.',
    'no_public_server_or_game_import':True,'full_library_processed':False}
(root/'docs/mcp/client-results.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'clients':{k:{f:v[f] for f in ['workflow_verified','status','tool_calls','returned_text_characters_total','returned_image_bytes_total','faults']} for k,v in results.items()},'schema_characters':summary['two_tool_schema_characters']},indent=2))
