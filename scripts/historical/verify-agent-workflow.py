"""Bounded real installed-client workflow, not a transport simulation or subtask delegation."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import shutil
import time

root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('client',choices=['codex','opencode'])
args=parser.parse_args()
client=args.client
directory=root/'data/mcp/client-runs'/client
directory.mkdir(parents=True,exist_ok=True)
manifest=root/'data/exports'/(client+'-selection.json')
manifest.parent.mkdir(parents=True,exist_ok=True)
prompt='''This is the user-authorized step 7 verification workflow for the installed client, not implementation or delegation. Bruno already approved both required scope and plan checkpoints and the bounded pilot in the current trusted session. Do not spawn any agents, run shell commands, explore directories, edit code/config, or copy source files. Use ONLY local_asset_library search_assets and get_asset. Find a small stylized red apple prop with a leaf, using the default keyword+description search, then inspect its actual preview with get_asset(include_preview=true, include_metadata=true). Describe visible geometry/colors from the image, distinguishing what you saw from captions. Choose one candidate, request its usable inspected source format and resolve the known dependencies with get_asset. If any client/tool/model step fails, do not retry the unchanged failure or silently substitute success: preserve partial findings and report the fault. Finish with ONLY one valid JSON selection manifest (no markdown) with keys: client, query, status (selected or partial or faulty), asset_id, selection_reason, preview_inspected (boolean; true only if you actually consumed image pixels), observed_image_features (array), selected_source (exact tool object with resolved_path and sha256), dependencies (exact tool array), dependency_completeness, limitations (array). Include known partial faults. No automatic copying/importing. The client harness saves your final manifest under this project data/exports. Returned text and requested previews enter this model context; Codex uses the configured cloud model and OpenCode uses the existing configured local Ollama model.'''
(directory/'prompt.txt').write_text(prompt,encoding='utf-8')
env=os.environ.copy()
if client=='codex':
    exe=shutil.which('codex')
    if not exe:
        raise SystemExit('Codex client unavailable; save setup snippet and leave workflow unverified')
    command=[exe,'exec','--json','--color','never','-s','read-only','-C',str(root),
             '-c','mcp_servers.node_repl.enabled=false','-c','mcp_servers.gimp.enabled=false',
             '-c','mcp_servers.blender.enabled=false','-o',str(manifest),prompt]
else:
    base=Path(r'C:\BrunoOS\OpenCode-local-agent')
    env.update(XDG_DATA_HOME=str(base/'OpenCodeData/data'),XDG_CONFIG_HOME=str(base/'OpenCodeData/config'),
        XDG_CACHE_HOME=str(base/'OpenCodeData/cache'),XDG_STATE_HOME=str(base/'OpenCodeData/state'),
        OPENCODE_CONFIG=str(base/'outputs/opencode-local.json'),OPENCODE_DISABLE_MODELS_FETCH='1',
        OPENCODE_DISABLE_AUTOUPDATE='1',OPENCODE_GIT_BASH_PATH=r'C:\Program Files\Git\bin\bash.exe')
    # Exact read-only tool authorization for this run, no permanent permission/model change.
    env['OPENCODE_CONFIG_CONTENT']=json.dumps({'permission':{
        'local_asset_library_search_assets':'allow','local_asset_library_get_asset':'allow'}})
    command=[str(base/'OpenCode/opencode.exe'),'run','--format','json','--dir',str(root),prompt]
started=time.monotonic()
with (directory/'events.jsonl').open('w',encoding='utf-8') as output, (directory/'stderr.log').open('w',encoding='utf-8') as error:
    process=subprocess.Popen(command,cwd=root,env=env,stdout=output,stderr=error)
    (directory/'process.json').write_text(json.dumps({'pid':process.pid,'client':client,'status':'running',
        'manifest':str(manifest),'existing_model_used':True,'per_run_overrides':
            'Disable other MCPs for this Codex verification only' if client=='codex' else
            'Allow exactly the two read-only project tools; other existing permissions unchanged'},indent=2),encoding='utf-8')
    try:
        code=process.wait(timeout=600)
        status='completed' if code==0 else 'faulty'
        reason=None if code==0 else 'Client exited with code '+str(code)
    except subprocess.TimeoutExpired:
        status,reason='faulty','Bounded workflow timeout at 600 seconds; no unchanged automatic retry'
        process.terminate()
        try:code=process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();code=process.wait()
if client=='opencode':
    text=[]
    for line in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if event.get('type')=='text': text.append(event.get('part',{}).get('text',''))
    if text:
        manifest.write_text(''.join(text),encoding='utf-8')
result={'client':client,'process_status':status,'reason':reason,'exit_code':code,
    'elapsed_seconds':time.monotonic()-started,'manifest':str(manifest),
    'actual_agent_workflow_verified':False,'note':'Must inspect client events, MCP audit, image consumption, manifest and paths before establishing completion.'}
(directory/'process.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
