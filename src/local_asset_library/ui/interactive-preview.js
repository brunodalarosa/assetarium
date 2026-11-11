'use strict';
// The app owns navigation and file authorization; Online 3D Viewer owns the 3D.
// The still shows at once; the live view loads only after the selection rests, so browsing passes no viewers.
window.LALPreview = (() => {
  let active = null, shellPromise = null, sequence = 0, hintSeen = false;
  const stats = {prepared: 0, frames: 0};
  const supported = new Set(['glb','gltf','fbx','obj','dae','stl']);
  const AUTO_DELAY = 250, AUTO_BYTES = 16 * 1024 * 1024;
  const VIEWS = [['three_quarter','3/4'],['front','Front'],['side','Side'],['top','Top']];
  const HINT = 'Drag to rotate · right-drag to pan · scroll to zoom · double-click to fit · R resets';
  // Static Lucide outlines; no caller data reaches innerHTML.
  const ICONS = {
    expand: '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    shrink: '<path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/><path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/>',
    more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  };
  const make = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const icon = name => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]}</svg>`;
  const paint = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const mib = bytes => (bytes / 1048576).toFixed(1) + ' MiB';

  class Preview {
    constructor(container, item, api) {
      this.container = container; this.item = item; this.api = api;
      this.serial = 0; this.frame = null; this.ticket = null; this.ready = false;
      this.fullscreen = false; this.closed = false; this.retainedFault = null;
      this.requests = new Map(); this.fileReads = 0; this.selectedAt = performance.now(); this.liveMs = null;
      this.view = VIEWS.some(([v]) => v === item.view) ? item.view : 'three_quarter';
      hintSeen = hintSeen || item.hintSeen === true;
      this.background = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'studio';
      container.classList.add('interactive-preview');
      this.dialog = make('dialog', undefined, 'model-preview');
      this.dialog.setAttribute('aria-label', item.name + ' preview');
      // The header only shows in fullscreen, where the inspector's own title is hidden.
      const header = make('div', undefined, 'model-preview-header');
      const title = make('h3', item.name);
      const format = make('span', item.sourceFormat?.toUpperCase() || '', 'preview-format');
      header.append(title, format);
      this.stage = make('div', undefined, 'model-stage');
      if (item.image) {
        this.still = make('img', undefined, 'preview-still');
        this.still.src = 'data:image/png;base64,' + item.image; this.still.alt = item.imageAlt;
      } else this.still = make('span', item.imageReason || 'Still image unavailable', 'preview-still placeholder');
      this.viewport = make('div', undefined, 'model-viewport');
      this.status = make('div', undefined, 'model-status');
      this.status.setAttribute('role','status'); this.status.setAttribute('aria-live','polite');
      this.status.hidden = true;
      this.hint = make('p', HINT, 'model-hint'); this.hint.hidden = true;
      const corner = make('div', undefined, 'model-corner');
      this.helpButton = this.iconButton('help', '3D controls: ' + HINT, () => this.showHint(this.hint.hidden, false));
      this.full = this.iconButton('expand', 'Fullscreen', () => this.toggleFullscreen());
      this.full.classList.add('model-fullscreen-button');
      this.more = this.iconButton('more', 'Display options', () => this.toggleMenu());
      this.more.setAttribute('aria-haspopup','true'); this.more.setAttribute('aria-expanded','false');
      corner.append(this.helpButton, this.full, this.more);
      this.menu = this.buildMenu();
      this.views = make('div', undefined, 'model-views');
      this.views.setAttribute('role','group'); this.views.setAttribute('aria-label','View');
      this.viewButtons = VIEWS.map(([name, label]) => {
        const button = make('button', label); button.type = 'button'; button.dataset.view = name; button.dataset.noTooltip = '';
        button.onclick = () => this.chooseView(name); this.views.append(button); return button;
      });
      this.stage.append(this.still, this.viewport, this.status, this.hint, corner, this.menu, this.views);
      this.warning = make('p', undefined, 'model-warning'); this.warning.hidden = true;
      this.warning.setAttribute('role','status');
      this.dialog.append(header, this.stage, this.warning);
      // show() runs the dialog focusing steps; a new selection must leave focus where browsing put it.
      const previous = document.activeElement;
      container.append(this.dialog); this.dialog.show();
      if (previous && previous !== document.body && previous.isConnected) previous.focus({preventScroll: true});
      this.dialog.addEventListener('cancel', event => { event.preventDefault(); if (this.fullscreen) this.exitFullscreen(); });
      this.dialog.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !this.menu.hidden) { event.preventDefault(); this.closeMenu(true); }
      });
      this.onOutside = event => { if (!this.menu.hidden && !this.menu.contains(event.target) && !this.more.contains(event.target)) this.closeMenu(false); };
      document.addEventListener('pointerdown', this.onOutside, true);
      this.onMessage = event => this.message(event);
      window.addEventListener('message', this.onMessage);
      this.resizeObserver = new ResizeObserver(() => this.send('command',{action:'resize'}));
      this.resizeObserver.observe(this.viewport);
      this.available = Boolean(item.sourceFormat && supported.has(item.sourceFormat));
      this.setControls(false); this.markView();
      if (!this.available) this.say(item.sourceFormat
        ? `Live 3D isn’t available for .${item.sourceFormat} · showing renders`
        : 'No verified source is available for live 3D · showing renders', 'note');
      // Only a selection that rests loads a viewer; dispose() cancels this for every asset browsing passes.
      else this.autoTimer = setTimeout(() => this.start({auto: true}), AUTO_DELAY);
    }
    iconButton(name, label, action) {
      const button = make('button', undefined, 'model-icon'); button.type = 'button';
      button.innerHTML = icon(name); button.setAttribute('aria-label', label); button.title = label;
      button.dataset.tooltip = '';  // Its title is its tooltip (verify-tooltips.py audits the marker).
      button.onclick = action; return button;
    }
    buildMenu() {
      const menu = make('div', undefined, 'model-menu'); menu.hidden = true;
      menu.setAttribute('role','group'); menu.setAttribute('aria-label','Display options');
      this.menuControls = [];
      const actions = make('div', undefined, 'model-menu-actions');
      for (const [label, action] of [['Fit', 'fit'], ['Reset view', 'reset']]) {
        const button = make('button', label); button.type = 'button'; button.dataset.action = action; button.dataset.noTooltip = '';
        button.onclick = () => this.command(action); this.menuControls.push(button); actions.append(button);
      }
      menu.append(actions,
        this.select('Projection',[['perspective','Perspective'],['orthographic','Orthographic']],'projection'),
        this.select('Background',[['studio','Studio'],['white','White'],['dark','Dark']],'background', this.background),
        this.select('Navigation',[['upright','Keep upright'],['free','Free orbit']],'navigation'),
        this.select('Up axis',[['Y','Y'],['Z','Z'],['X','X']],'up'));
      const edgeLabel = make('label',undefined,'model-edges'), edges = make('input');
      edges.type = 'checkbox'; edges.onchange = () => this.command('edges', edges.checked);
      this.menuControls.push(edges); edgeLabel.append(edges, document.createTextNode('Show edges')); menu.append(edgeLabel);
      return menu;
    }
    select(label, options, action, value) {
      const wrapper = make('label',label), select = make('select');
      select.dataset.action = action;
      for (const [v,text] of options) { const option = make('option',text); option.value = v; select.append(option); }
      select.dataset.initial = value || options[0][0]; select.value = select.dataset.initial;
      select.onchange = () => this.command(action, select.value);
      this.menuControls.push(select); wrapper.append(select); return wrapper;
    }
    setControls(enabled) {
      for (const control of this.menuControls) control.disabled = !enabled;
      this.more.disabled = !enabled;
      this.more.title = enabled ? 'Display options' : 'Display options are available once the live view loads';
      if (!enabled) this.closeMenu(false);
      // Before the live view, 3/4 · Front · Side switch the stills; there is no top still.
      const top = this.viewButtons[3];
      top.disabled = !enabled; top.title = enabled ? '' : 'Top is available in the live view';
    }
    markView() { for (const b of this.viewButtons) b.setAttribute('aria-pressed', String(b.dataset.view === this.view)); }
    chooseView(name) {
      if (this.ready) { this.view = name; this.markView(); this.command('view', name); return; }
      if (name !== 'top' && name !== this.view) this.item.onView?.(name);
    }
    toggleMenu() { if (this.menu.hidden) this.openMenu(); else this.closeMenu(true); }
    openMenu() {
      if (!this.ready) return;
      if (!this.hint.hidden) this.retireHint();  // Opening the menu shows the controls were found.
      this.menu.hidden = false; this.more.setAttribute('aria-expanded','true');
      this.menuControls[0].focus();
    }
    closeMenu(focus) {
      if (this.menu.hidden) return;
      this.menu.hidden = true; this.more.setAttribute('aria-expanded','false');
      if (focus) this.more.focus();
    }
    say(text, tone, action) {
      this.status.replaceChildren(); this.status.className = 'model-status' + (tone ? ' ' + tone : '');
      this.status.hidden = !text;
      if (!text) return;
      if (tone === 'loading') this.status.append(make('span', undefined, 'search-spinner'));
      this.status.append(make('span', text));
      if (action) {
        const button = make('button', action.label); button.type = 'button'; button.onclick = action.run; button.dataset.noTooltip = '';
        this.status.append(button);
      }
    }
    loading(message) { this.loadingText = message; this.say(message, message ? 'loading' : null); }
    showHint(show, remember) {
      clearTimeout(this.hintTimer);
      this.hint.hidden = !show;
      this.helpButton.setAttribute('aria-expanded', String(show));
      if (show && remember) this.hintTimer = setTimeout(() => this.retireHint(), 8000);
    }
    retireHint() {
      this.showHint(false, false);
      if (!hintSeen) { hintSeen = true; this.item.onHintSeen?.(); }
    }
    send(type, data = {}, transfer = []) {
      this.frame?.contentWindow?.postMessage({kind:'lal-3d',session:this.session,type,...data},'*',transfer);
    }
    async start({auto = false, fullscreen = false} = {}) {
      clearTimeout(this.autoTimer); this.autoTimer = null;
      if (this.retainedFault || this.closed || !this.available) return;
      if (this.frame || this.loadingText) { if (fullscreen && !this.fullscreen) await this.enterFullscreen(); return; }
      const serial = ++this.serial;
      this.ready = false; this.setControls(false); this.warning.hidden = true;
      this.loading('Loading 3D…');
      if (fullscreen) await this.enterFullscreen();
      this.timer = setTimeout(() => this.fault('Interactive preview exceeded the 90-second loading limit.'),90000);
      try {
        if (!shellPromise) shellPromise = this.api.preview_shell().then(result => {
          if (result.status !== 'ready') throw Error(result.reason || 'Viewer resources are unavailable.');
          return result.html;
        });
        stats.prepared++;
        const [manifest, html] = await Promise.all([
          this.api.preview_prepare(this.item.assetId,this.item.sourceFormat,this.item.version),shellPromise]);
        if (this.serial !== serial || this.closed) { if (manifest.ticket) this.api.preview_release(manifest.ticket); return; }
        if (manifest.status !== 'ready') { this.fail(manifest.reason || '3D preview is unavailable.',manifest.retained === true,manifest.status === 'stale'); return; }
        if (auto && manifest.total_bytes > AUTO_BYTES) {
          // Large packages wait for a click: nothing is read until the owner asks.
          this.api.preview_release(manifest.ticket).catch(() => {});
          ++this.serial; clearTimeout(this.timer); this.loadingText = null;
          this.say('Large model · ' + mib(manifest.total_bytes), 'note', {label: 'Click to load', run: () => this.start()});
          return;
        }
        this.ticket = manifest.ticket; this.manifest = manifest;
        this.session = String(++sequence) + '-' + Math.random().toString(36).slice(2);
        const frame = make('iframe'); frame.title = this.item.name + ' — live 3D view';
        frame.setAttribute('sandbox','allow-scripts'); frame.setAttribute('referrerpolicy','no-referrer');
        this.frame = frame; this.frameReady = new Promise(resolve => this.resolveFrame = resolve);
        stats.frames++;
        frame.srcdoc = html; this.viewport.prepend(frame);
        await this.frameReady;
        for (let i=0; i<manifest.files.length; i++) {
          if (this.serial !== serial || this.closed || !this.frame) return;
          if (manifest.files.length > 1) this.loading(`Loading 3D · file ${i+1} of ${manifest.files.length}…`);
          const file = await this.api.preview_file(this.ticket,i); this.fileReads++;
          if (this.serial !== serial || this.closed || !this.frame) return;
          if (file.status !== 'ready') { this.fail(file.reason || 'A source file is unavailable.',file.retained === true,file.status === 'stale'); return; }
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
        this.loading('Loading 3D…'); this.send('load');
      } catch (error) { if (this.serial === serial && !this.closed) await this.fault(error.message); }
    }
    async message(event) {
      if (event.source !== this.frame?.contentWindow || event.data?.kind !== 'lal-3d') return;
      const message = event.data;
      if (message.type === 'boot') {
        this.send('init',{sourceName:this.manifest.source_name, view:this.view, background:this.background}); return;
      }
      if (message.session !== this.session) return;
      if (message.type === 'ready') {
        if (message.desktopBridge || message.parentAccess) { await this.fault('The 3D frame could not be isolated from the desktop interface.'); return; }
        this.resolveFrame?.(); this.resolveFrame = null;
      }
      else if (message.type === 'progress') { if (this.loadingText) this.loading('Loading 3D · ' + message.message.replace(/…$/, '').toLowerCase() + '…'); }
      else if (message.type === 'loaded') {
        clearTimeout(this.timer); this.ready = true; this.loading(null); this.setControls(true);
        this.liveMs = Math.round(performance.now() - this.selectedAt);
        this.summary = message.summary;
        this.stage.classList.add('live');
        if (!hintSeen) this.showHint(true, true);
        if (message.missing?.length) {
          const reason = 'Some referenced files could not be loaded: ' + message.missing.join(', ');
          this.warning.textContent = reason + '. Available geometry is shown; this is a partial preview.';
          this.warning.hidden = false;
          this.retainedFault = reason;
          try { await this.api.preview_fault(this.ticket,reason.slice(0,1200),message.missing.slice(0,64)); }
          catch (error) { this.warning.textContent += ' Could not save fault evidence: ' + error.message; }
        }
      } else if (message.type === 'fault') await this.fault(message.reason);
      else if (message.type === 'interacted') { if (!this.hint.hidden || !hintSeen) this.retireHint(); }
      else if (message.type === 'search') { if (!this.fullscreen) this.item.onSearch?.(); }
      else if (message.type === 'escape') {
        if (!this.menu.hidden) this.closeMenu(false);
        else if (this.fullscreen) this.exitFullscreen(); else this.item.onEscape?.();
      }
      else if (message.type === 'command-done') { this.requests.get(message.request)?.(); this.requests.delete(message.request); }
    }
    async command(action, value) {
      if (!this.ready || !this.frame) return;
      if (action === 'reset') {
        this.view = this.item.view && VIEWS.some(([v]) => v === this.item.view) ? this.item.view : 'three_quarter';
        this.markView();
        for (const select of this.menu.querySelectorAll('select[data-action=up]')) select.value = 'Y';
      }
      try { await this.acknowledge(action,value); }
      catch (error) { await this.fault(error.message); }
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
      this.fullscreen = true; this.dialog.close(); this.dialog.classList.add('model-fullscreen');
      this.dialog.showModal(); this.setFullIcon();
      this.previousOverflow = document.documentElement.style.overflow;
      document.documentElement.style.overflow = 'hidden';
      this.full.focus();
      await paint();
      if (!this.fullscreen || this.closed) return;
      try { await this.acknowledge('resize'); }
      catch (error) { await this.fault(error.message); }
    }
    async exitFullscreen() {
      if (!this.fullscreen) return;
      this.closeMenu(false);
      this.fullscreen = false; this.dialog.close(); this.dialog.classList.remove('model-fullscreen');
      this.dialog.show(); this.setFullIcon();
      document.documentElement.style.overflow = this.previousOverflow || '';
      this.full.focus();
      await paint();
      if (this.closed || this.fullscreen) return;
      try { await this.acknowledge('resize'); }
      catch (error) { await this.fault(error.message); }
    }
    setFullIcon() {
      const label = this.fullscreen ? 'Exit fullscreen' : 'Fullscreen';
      this.full.innerHTML = icon(this.fullscreen ? 'shrink' : 'expand');
      this.full.setAttribute('aria-label', label); this.full.title = label;
    }
    toggleFullscreen() { if (this.fullscreen) return this.exitFullscreen(); return this.enterFullscreen(); }
    release(keepTicket = false) {
      ++this.serial; clearTimeout(this.timer); clearTimeout(this.autoTimer);
      this.frame?.remove(); this.frame = null; this.stage.classList.remove('live');
      this.resolveFrame?.(); this.resolveFrame = null;
      for (const resolve of this.requests.values()) resolve(); this.requests.clear();
      if (this.ticket && !keepTicket) this.api.preview_release(this.ticket).catch(() => {});
      this.ticket = null; this.ready = false; this.loadingText = null; this.setControls(false); this.showHint(false, false);
    }
    fail(reason, retained = true, stale = false, keepTicket = false) {
      this.release(keepTicket);
      this.retainedFault = retained ? reason : null;
      if (stale) this.say('The library changed.', 'fault', this.item.onRefresh && {label: 'Refresh', run: () => this.item.onRefresh()});
      else this.say(`Live 3D unavailable: ${reason}${retained ? ' Recorded; no automatic retry.' : ''} Showing renders.`, 'fault');
    }
    async fault(reason) {
      if (this.closed || (this.retainedFault && !this.ready)) return;
      this.retainedFault = reason;
      const ticket = this.ticket;
      // The ticket identifies the inputs the fault is recorded against; release it only after recording.
      this.fail(reason, true, false, true);
      if (!ticket) return;
      let saved;
      try { saved = await this.api.preview_fault(ticket,reason.slice(0,1200)); }
      catch (error) { saved = {status: 'faulty', reason: error.message}; }
      this.api.preview_release(ticket).catch(() => {});
      if (saved?.status !== 'faulty' || saved.channel === 'interactive_preview') return;
      if (!this.closed) this.say(this.status.textContent + ' Could not save fault evidence: ' + (saved.reason || 'unknown error'), 'fault');
    }
    // Leaving the page or hiding the panel releases the viewer; the still stays with a way back.
    stop() {
      if (this.fullscreen) { document.documentElement.style.overflow = this.previousOverflow || ''; this.fullscreen = false;
        this.dialog.close(); this.dialog.classList.remove('model-fullscreen'); this.dialog.show(); this.setFullIcon(); }
      const wasLive = this.frame || this.loadingText || this.autoTimer;
      this.release();
      if (wasLive && this.available && !this.retainedFault && !this.closed) this.say('Live 3D paused', 'note', {label: 'Load', run: () => this.start()});
    }
    dispose() {
      this.closed = true; this.stop(); this.resizeObserver.disconnect();
      window.removeEventListener('message',this.onMessage);
      document.removeEventListener('pointerdown', this.onOutside, true);
    }
  }
  return {
    mount(container, item, api) { active?.dispose(); active = new Preview(container,item,api); return active; },
    dispose() { active?.dispose(); active = null; },
    pause() { active?.stop(); },
    get current() { return active; },
    stats,
    AUTO_BYTES,
  };
})();
