'use strict';
// The app owns navigation and file authorization; Online 3D Viewer owns the 3D.
window.LALPreview = (() => {
  let active = null, shellPromise = null, sequence = 0;
  const supported = new Set(['glb','gltf','fbx','obj','dae','stl']);
  const make = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const paint = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

  class Preview {
    constructor(container, item, api) {
      this.container = container; this.item = item; this.api = api;
      this.serial = 0; this.frame = null; this.ticket = null; this.ready = false;
      this.fullscreen = false; this.closed = false; this.retainedFault = null;
      this.requests = new Map(); this.fileReads = 0;
      container.classList.add('interactive-preview');
      this.still = make('div', undefined, 'preview-still');
      this.launch = make('button', undefined, 'preview-launch');
      this.launch.type = 'button';
      this.launch.setAttribute('aria-label', 'Explore ' + item.name + ' in 3D');
      if (item.image) {
        const image = make('img'); image.src = 'data:image/png;base64,' + item.image;
        image.alt = item.imageAlt; this.launch.append(image);
      } else this.launch.append(make('span', item.imageReason || 'Still image unavailable', 'placeholder'));
      this.launch.append(make('span', '↻ Explore in 3D', 'preview-launch-label'));
      this.launch.onclick = () => this.start(false);
      this.launchFull = this.button('Open fullscreen', () => this.start(true));
      this.launchFull.classList.add('preview-open-fullscreen');
      this.note = make('p', undefined, 'preview-availability');
      this.note.setAttribute('role','status');
      this.still.append(this.launch, this.launchFull, this.note);
      container.append(this.still);
      this.dialog = make('dialog', undefined, 'model-preview');
      const labelId = 'model-preview-title-' + (++sequence);
      this.dialog.setAttribute('aria-labelledby', labelId);
      const header = make('div', undefined, 'model-preview-header');
      const title = make('h3', item.name); title.id = labelId;
      const source = make('span', item.sourceFormat?.toUpperCase() || '', 'preview-format');
      const heading = make('div', undefined, 'model-preview-heading'); heading.append(title, source);
      const actions = make('div', undefined, 'model-preview-actions');
      this.back = this.button('Back to image', () => this.stop());
      this.full = this.button('Fullscreen', () => this.toggleFullscreen());
      actions.append(this.back, this.full); header.append(heading, actions);
      this.viewport = make('div', undefined, 'model-viewport');
      this.overlay = make('div', undefined, 'model-loading');
      this.overlay.setAttribute('role','status'); this.overlay.setAttribute('aria-live','polite');
      this.spinner = make('span', undefined, 'search-spinner'); this.overlay.append(this.spinner);
      this.loadingLabel = make('span','Preparing 3D preview…'); this.overlay.append(this.loadingLabel);
      this.viewport.append(this.overlay);
      this.tools = make('div', undefined, 'model-toolbar'); this.controls = [];
      this.tools.setAttribute('aria-label','3D preview controls');
      this.tools.append(this.control('Fit', 'fit'), this.control('Reset view', 'reset'),
        this.control('−', 'zoom', -0.15, 'Zoom out'), this.control('+', 'zoom', 0.15, 'Zoom in'));
      this.tools.append(this.select('View preset', [['isometric','Isometric'],['front','Front'],['back','Back'],
        ['left','Left'],['right','Right'],['top','Top'],['bottom','Bottom']], 'view'));
      const options = make('details',undefined,'model-options');
      options.append(make('summary','Display options'));
      const settings = make('div',undefined,'model-settings');
      settings.append(this.select('Projection',[['perspective','Perspective'],['orthographic','Orthographic']],'projection'),
        this.select('Background',[['studio','Studio'],['white','White'],['dark','Dark']],'background'),
        this.select('Navigation',[['upright','Keep upright'],['free','Free orbit']],'navigation'),
        this.select('Up axis',[['Y','Y'],['Z','Z'],['X','X']],'up'));
      const edgeLabel = make('label',undefined,'model-edges'), edges = make('input');
      edges.type = 'checkbox'; edges.onchange = () => this.command('edges', edges.checked, 'Preparing edges…');
      this.controls.push(edges); edgeLabel.append(edges,document.createTextNode('Show edges')); settings.append(edgeLabel);
      options.append(settings);
      this.help = make('p','Drag to rotate · right-drag to pan · scroll to zoom. Keyboard: arrows rotate, Shift + arrows pan, + / − zoom, F fits, R resets.','model-help');
      this.summary = make('p',undefined,'model-summary'); this.summary.setAttribute('role','status');
      this.warning = make('p',undefined,'model-warning'); this.warning.hidden = true; this.warning.setAttribute('role','status');
      this.dialog.append(header,this.viewport,this.tools,options,this.help,this.summary,this.warning);
      container.append(this.dialog);
      this.dialog.addEventListener('cancel', event => {
        event.preventDefault(); if (this.fullscreen) this.exitFullscreen(); else this.stop();
      });
      this.onMessage = event => this.message(event);
      window.addEventListener('message', this.onMessage);
      this.resizeObserver = new ResizeObserver(() => this.send('command',{action:'resize'}));
      this.resizeObserver.observe(this.viewport);
      if (!item.sourceFormat || !supported.has(item.sourceFormat)) {
        this.launch.disabled = this.launchFull.disabled = true;
        this.note.textContent = item.sourceFormat ? `3D preview is unavailable for ${item.sourceFormat.toUpperCase()}. Choose a supported source format.` : 'No verified source is available for 3D preview.';
      }
      this.setControls(false);
    }
    button(label, action) { const b = make('button',label); b.type = 'button'; b.onclick = action; return b; }
    control(label, action, value, accessibleName) {
      const button = this.button(label, () => this.command(action, value));
      button.dataset.action = action;
      if (accessibleName) button.setAttribute('aria-label',accessibleName);
      this.controls.push(button); return button;
    }
    select(label, options, action) {
      const wrapper = make('label',label), select = make('select');
      select.dataset.action = action;
      for (const [value,text] of options) { const option = make('option',text); option.value = value; select.append(option); }
      select.onchange = () => this.command(action, select.value);
      this.controls.push(select); wrapper.append(select); return wrapper;
    }
    setControls(enabled) { for (const control of this.controls) control.disabled = !enabled; }
    loading(message) {
      this.loadingText = message;
      this.overlay.hidden = !message;
      this.loadingLabel.textContent = message || '';
      this.viewport.setAttribute('aria-busy',String(Boolean(message)));
    }
    send(type, data = {}, transfer = []) {
      this.frame?.contentWindow?.postMessage({kind:'lal-3d',session:this.session,type,...data},'*',transfer);
    }
    async start(fullscreen) {
      if (this.retainedFault || this.closed || this.launch.disabled) return;
      if (this.frame || this.loadingText) { if (fullscreen && !this.fullscreen) await this.enterFullscreen(); return; }
      const serial = ++this.serial;
      this.still.hidden = true; this.dialog.show();
      this.ready = false; this.setControls(false); this.warning.hidden = true;
      this.full.disabled = false; this.spinner.hidden = false; this.overlay.classList.remove('model-load-fault');
      for (const control of this.controls) {
        if (control.tagName === 'SELECT') control.selectedIndex = 0;
        if (control.type === 'checkbox') control.checked = false;
      }
      this.summary.textContent = ''; this.loading('Preparing local files…');
      if (fullscreen) await this.enterFullscreen();
      else this.back.focus();
      this.timer = setTimeout(() => this.fault('Interactive preview exceeded the 90-second loading limit.'),90000);
      try {
        await paint();
        if (!shellPromise) shellPromise = this.api.preview_shell().then(result => {
          if (result.status !== 'ready') throw Error(result.reason || 'Viewer resources are unavailable.');
          return result.html;
        });
        const [manifest, html] = await Promise.all([
          this.api.preview_prepare(this.item.assetId,this.item.sourceFormat,this.item.version),shellPromise]);
        if (this.serial !== serial || this.closed) { if (manifest.ticket) this.api.preview_release(manifest.ticket); return; }
        if (manifest.status !== 'ready') { this.fail(manifest.reason || '3D preview is unavailable.',manifest.retained); return; }
        this.ticket = manifest.ticket; this.manifest = manifest;
        this.session = String(++sequence) + '-' + Math.random().toString(36).slice(2);
        const frame = make('iframe'); frame.title = this.item.name + ' — interactive 3D preview';
        frame.setAttribute('sandbox','allow-scripts'); frame.setAttribute('referrerpolicy','no-referrer');
        this.frame = frame; this.frameReady = new Promise(resolve => this.resolveFrame = resolve);
        frame.srcdoc = html; this.viewport.prepend(frame);
        await this.frameReady;
        for (let i=0; i<manifest.files.length; i++) {
          if (this.serial !== serial || this.closed || !this.frame) return;
          this.loading(`Loading local files ${i+1} / ${manifest.files.length}…`);
          const file = await this.api.preview_file(this.ticket,i); this.fileReads++;
          if (this.serial !== serial || this.closed || !this.frame) return;
          if (file.status !== 'ready') { this.fail(file.reason || 'A source file is unavailable.',file.retained); return; }
          const bytes = new Uint8Array(manifest.files[i].size);
          // Yield between bounded chunks instead of freezing the library on a large decode.
          for (let offset=0;offset<file.content.length;offset+=524288) {
            const chunk = atob(file.content.slice(offset,offset+524288));
            const start = offset/4*3;
            for (let j=0;j<chunk.length;j++) bytes[start+j]=chunk.charCodeAt(j);
            await new Promise(resolve => setTimeout(resolve,0));
            if (this.serial !== serial || this.closed || !this.frame) return;
          }
          this.send('file',{aliases:manifest.files[i].aliases,buffer:bytes.buffer},[bytes.buffer]);
        }
        this.loading('Importing model…'); await paint(); this.send('load');
      } catch (error) { if (this.serial === serial && !this.closed) await this.fault(error.message); }
    }
    async message(event) {
      if (event.source !== this.frame?.contentWindow || event.data?.kind !== 'lal-3d') return;
      const message = event.data;
      if (message.type === 'boot') { this.send('init',{sourceName:this.manifest.source_name}); return; }
      if (message.session !== this.session) return;
      if (message.type === 'ready') {
        if (message.desktopBridge || message.parentAccess) { await this.fault('The 3D frame could not be isolated from the desktop interface.'); return; }
        this.resolveFrame?.(); this.resolveFrame = null;
      }
      else if (message.type === 'progress') this.loading(message.message);
      else if (message.type === 'loaded') {
        clearTimeout(this.timer); this.ready = true; this.loading(null); this.setControls(true);
        const stats = message.summary;
        this.summary.textContent = `Preview geometry · ${stats.triangles.toLocaleString()} triangles · ${stats.meshes.toLocaleString()} meshes · ${stats.materials.toLocaleString()} materials`;
        if (message.missing?.length) {
          const reason = 'Some referenced files could not be loaded: ' + message.missing.join(', ');
          this.warning.textContent = reason + '. Available geometry is shown; this is a partial preview.';
          this.warning.hidden = false;
          this.retainedFault = reason;
          try { await this.api.preview_fault(this.ticket,reason.slice(0,1200),message.missing.slice(0,64)); }
          catch (error) { this.warning.textContent += ' Could not save fault evidence: ' + error.message; }
        }
      } else if (message.type === 'fault') await this.fault(message.reason);
      else if (message.type === 'search') { if (!this.fullscreen) this.item.onSearch?.(); }
      else if (message.type === 'escape') { if (this.fullscreen) this.exitFullscreen(); else this.stop(); }
      else if (message.type === 'command-done') { this.requests.get(message.request)?.(); this.requests.delete(message.request); }
    }
    async command(action, value, message = 'Updating preview…') {
      if (!this.ready || !this.frame) return;
      if (action === 'reset') {
        this.dialog.querySelector('select[data-action=view]').value = 'isometric';
        this.dialog.querySelector('select[data-action=up]').value = 'Y';
      }
      this.setControls(false); this.loading(message);
      await paint();
      try { await this.acknowledge(action,value); }
      catch (error) { await this.fault(error.message); return; }
      if (this.ready) { this.loading(null); this.setControls(true); }
    }
    acknowledge(action,value) {
      if (!this.frame) return Promise.resolve();
      const request = ++sequence;
      return new Promise((resolve,reject) => {
        const timer = setTimeout(() => { this.requests.delete(request); reject(Error('The preview did not respond.')); },15000);
        this.requests.set(request,() => { clearTimeout(timer); resolve(); });
        this.send('command',{action,value,request});
      });
    }
    async enterFullscreen() {
      if (this.fullscreen || this.closed) return;
      this.returnFocus = this.full;
      this.fullscreen = true; this.dialog.close(); this.dialog.classList.add('model-fullscreen');
      this.dialog.showModal(); this.full.textContent = 'Exit fullscreen';
      this.previousOverflow = document.documentElement.style.overflow;
      document.documentElement.style.overflow = 'hidden';
      const serial = this.serial, previous = this.loadingText;
      this.loading('Opening fullscreen…'); this.full.focus();
      await paint();
      if (!this.fullscreen || this.closed || serial !== this.serial) return;
      try { await this.acknowledge('resize'); }
      catch (error) { await this.fault(error.message); return; }
      this.loading(this.ready ? null : previous || 'Preparing local files…');
    }
    async exitFullscreen() {
      if (!this.fullscreen) return;
      this.fullscreen = false; this.dialog.close(); this.dialog.classList.remove('model-fullscreen');
      this.dialog.show(); this.full.textContent = 'Fullscreen';
      document.documentElement.style.overflow = this.previousOverflow || '';
      if (this.retainedFault && !this.ready) { this.full.disabled = true; this.back.focus(); return; }
      const serial = this.serial, previous = this.loadingText;
      this.loading('Returning to inspection…');
      await paint();
      if (this.closed || this.fullscreen || serial !== this.serial) return;
      try { await this.acknowledge('resize'); }
      catch (error) { await this.fault(error.message); return; }
      this.loading(this.ready ? null : previous || 'Preparing 3D preview…');
      if (this.returnFocus?.isConnected && this.dialog.contains(this.returnFocus)) this.returnFocus.focus();
      else this.full.focus();
    }
    toggleFullscreen() { if (this.fullscreen) return this.exitFullscreen(); return this.enterFullscreen(); }
    fail(reason, retained = true) {
      ++this.serial; clearTimeout(this.timer); this.retainedFault = retained ? reason : null;
      this.ready = false; this.setControls(false); this.loading(null);
      this.warning.textContent = reason + (retained ? ' Recorded failure; no automatic retry.' : '');
      this.warning.hidden = false; this.summary.textContent = 'The existing image and source evidence remain available.';
      this.overlay.hidden = false; this.spinner.hidden = true; this.overlay.classList.add('model-load-fault');
      this.loadingLabel.textContent = '3D preview unavailable. ' + reason + ' Use Back to image to continue.';
      this.full.disabled = !this.fullscreen;
      this.frame?.remove(); this.frame = null;
      this.resolveFrame?.(); this.resolveFrame = null;
      for (const resolve of this.requests.values()) resolve(); this.requests.clear();
    }
    async fault(reason) {
      if (this.closed || (this.retainedFault && !this.ready)) return;
      this.retainedFault = reason;
      const ticket = this.ticket;
      this.fail(reason);
      if (ticket) {
        try { await this.api.preview_fault(ticket,reason.slice(0,1200)); }
        catch (error) { this.warning.textContent += ' Could not save fault evidence: ' + error.message; }
      }
    }
    stop(focus = true) {
      ++this.serial; clearTimeout(this.timer);
      if (this.fullscreen) document.documentElement.style.overflow = this.previousOverflow || '';
      this.fullscreen = false; this.dialog.close(); this.dialog.classList.remove('model-fullscreen');
      this.full.textContent = 'Fullscreen'; this.frame?.remove(); this.frame = null;
      this.resolveFrame?.(); this.resolveFrame = null;
      for (const resolve of this.requests.values()) resolve(); this.requests.clear();
      if (this.ticket) this.api.preview_release(this.ticket).catch(() => {});
      this.ticket = null; this.ready = false; this.loading(null); this.still.hidden = false;
      if (this.retainedFault) {
        this.note.textContent = this.retainedFault + ' Recorded 3D preview failure; the existing image is retained.';
        this.launch.disabled = this.launchFull.disabled = true;
      }
      if (focus) this.launch.disabled ? this.container.closest('.detail-body')?.querySelector('.close-detail')?.focus() : this.launch.focus();
    }
    dispose() {
      this.stop(false); this.closed = true; this.resizeObserver.disconnect();
      window.removeEventListener('message',this.onMessage);
    }
  }
  return {
    mount(container, item, api) { active?.dispose(); active = new Preview(container,item,api); return active; },
    dispose() { active?.dispose(); active = null; },
    pause() { active?.stop(false); },
    get current() { return active; }
  };
})();
