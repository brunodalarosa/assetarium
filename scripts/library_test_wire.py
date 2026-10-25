"""Verification-only STDIO client for isolated configured fixtures."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

from local_asset_library.config import venv_python


class FixtureWire:
    def __init__(self,root,config,log):
        self.stderr=log.open('w',encoding='utf-8')
        code="import asyncio,json,sys; from pathlib import Path; from local_asset_library.config import Config; from local_asset_library.mcp_server import serve; value=json.loads(sys.argv[1]); asyncio.run(serve(Config(Path(value['project']),Path(value['source']),None)))"
        self.process=subprocess.Popen([str(venv_python(root,'.venv-mcp')),'-c',code,
            json.dumps({'project':str(config.project_root),'source':str(config.source_root)})],cwd=root,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.messages=queue.Queue();self.sequence=0
        def read():
            for line in self.process.stdout:self.messages.put(line)
            self.messages.put(None)
        threading.Thread(target=read,daemon=True).start()
        self.send('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'synthetic-publication-check','version':'1'}})
        self.send('notifications/initialized',notification=True)
    def send(self,method,params=None,notification=False):
        message={'jsonrpc':'2.0','method':method}
        if params is not None:message['params']=params
        if not notification:self.sequence+=1;message['id']=self.sequence
        self.process.stdin.write(json.dumps(message)+'\n');self.process.stdin.flush()
        if notification:return
        while True:
            line=self.messages.get(timeout=30)
            if line is None:raise RuntimeError('Fixture server exited')
            result=json.loads(line)
            if result.get('id')==self.sequence:return result['result']
    def search(self,args):
        result=self.send('tools/call',{'name':'search_assets','arguments':args})
        if result.get('isError'):raise RuntimeError(str(result))
        return json.loads(result['content'][0]['text'])
    def close(self):
        self.process.stdin.close();code=self.process.wait(timeout=15);self.stderr.close()
        if code:raise RuntimeError('Fixture server did not close cleanly')
