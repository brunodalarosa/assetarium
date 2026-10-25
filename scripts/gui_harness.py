"""Shared helpers for the real-WebView2 verify scripts of the React desktop UI.

Scripts read state and call actions through window.lal (frontend/src/main.tsx) and drive
controls the way a user does; results and screenshots go to data/gui/<run-name>/.
"""
import json
import os
from pathlib import Path
import threading
import time

from ui_text import assert_ui_text


def isolate_hash_cache(script):
    """Synthetic checks keep their hashes out of the shared cache/file-hashes.sqlite (decision 0004)."""
    os.environ['LAL_HASH_CACHE'] = str(Path(__file__).resolve().parents[1] / 'scratch/hash-cache' / (Path(script).stem + '.sqlite'))

# Small page helpers: until() polls, frame() waits two paints, pick() chooses a beUI select
# option by value (as a click would), type() fills a React-controlled input.
PRELUDE = r"""window.until=async(fn,ms=10000)=>{const end=Date.now()+ms;while(Date.now()<end){try{if(fn())return true}catch(e){}
  await new Promise(r=>setTimeout(r,40))}throw Error('Timed out: '+fn)};
window.frame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
window.$=id=>document.getElementById(id);
window.pick=async(id,value)=>{const root=$(id);root.querySelector('[aria-haspopup=listbox]').click();await frame();
  const option=[...root.querySelectorAll('[role=option]')].find(o=>o.dataset.listboxId===(value===''?'__any':String(value)));
  if(!option)throw Error('No option '+value+' in '+id);option.click();await frame();return root.dataset.value};
window.type=(element,value)=>{const target=typeof element==='string'?$(element):element;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(target,value);
  target.dispatchEvent(new Event('input',{bubbles:true}));return true};
window.stubApi=overrides=>{window.fixtureApi=window.fixtureApi||lal.state.api;
  lal.setState({api:Object.assign(Object.create(fixtureApi),overrides)});return true};
true"""


class Harness:
    def __init__(self, window, out, report):
        self.window, self.out, self.report = window, out, report
        report.setdefault('checks', {})
        report.setdefault('screenshots', [])

    def js(self, script, timeout=60):
        """Evaluate a script (statement list or promise); JS errors raise instead of passing silently."""
        done, values = threading.Event(), []
        def callback(value):
            values.append(value)
            done.set()
        # pywebview reports through the callback only when the script yields a promise.
        self.window.evaluate_js('(async()=>{try{const value=await eval(%s);return value===undefined?null:value}'
                                'catch(error){return {__error:String(error&&error.stack||error)}}})()' % json.dumps(script), callback)
        if not done.wait(timeout):
            raise RuntimeError('UI check completion timeout')
        if isinstance(values[0], dict) and '__error' in values[0]:
            raise RuntimeError('UI script fault: ' + values[0]['__error'])
        return values[0]

    def check(self, name, script, timeout=60):
        value = self.js(script, timeout)
        self.report['checks'][name] = value
        assert value is True or (isinstance(value, dict) and value and all(value.values())), {name: value}
        return value

    def wait_ready(self, timeout=30, extra='true'):
        deadline = time.perf_counter() + timeout
        while not self.window.evaluate_js(f'Boolean(window.lal && lal.state.ready && lal.state.context && ({extra}))'):
            if time.perf_counter() > deadline:
                raise RuntimeError('Startup timeout')
            time.sleep(.1)
        assert self.window.gui.renderer == 'edgechromium'
        self.js(PRELUDE)

    def capture(self, name, settle=.45):
        time.sleep(settle)  # Let spring transitions settle before the screenshot.
        assert_ui_text(self.window, name, self.report)
        from System import Action
        from System.IO import MemoryStream
        from System.Threading.Tasks import Task
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        form = self.window.gui.BrowserView.instances[self.window.uid]
        stream, done, faults = MemoryStream(), threading.Event(), []
        def capture_on_ui():
            task = form.browser.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)
            def finished(task):
                if task.IsFaulted:
                    faults.append(str(task.Exception))
                done.set()
            task.ContinueWith(Action[Task](finished), form.browser.syncContextTaskScheduler)
        form.Invoke(Action(capture_on_ui))
        assert done.wait(15) and not faults
        (self.out / name).write_bytes(bytes(stream.ToArray()))
        stream.Dispose()
        self.report['screenshots'].append(name)
