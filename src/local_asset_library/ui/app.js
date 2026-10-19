'use strict';
const $ = id => document.getElementById(id);
const state = { activeSearch:null, context:null, items:[], generation:0, detailGeneration:0, selected:null, lastSettings:null, lastResponse:null, api:null, cardNodes:new Map(), offset:0, total:0, observer:null, browsing:true, thumbQueue:[], thumbWorkers:0 };
const views = {three_quarter:'Three-quarter',front:'Front',side:'Side'};
function activeCollection(){return !$('source-browser-view').hidden&&state.sourceBrowse?state.sourceBrowse:state;}
function collectionElement(collection,id){return $(collection===state?id:'source-'+id);}
function node(tag, text, className){ const el=document.createElement(tag); if(text!==undefined)el.textContent=text; if(className)el.className=className; return el; }
function display(value){return value===null||value===undefined?'Unknown':typeof value==='object'?JSON.stringify(value,null,2):String(value);}
function packName(value){return value.replace(/^kenney_/,'Kenney · ').replace(/^quaternius_/,'Quaternius · ').replaceAll('_',' ').replaceAll('-',' ');}
function status(text){$('status').textContent=text;}
function fail(reason){$('error').textContent=reason;$('error').hidden=false;}
function resetError(){$('error').hidden=true;$('error').textContent='';}
function searchBusy(generation){state.activeSearch=generation;$('search-busy').hidden=generation===null;$('submit').disabled=generation!==null;}
function filters(){ const f={}; if($('pack').value)f.pack=$('pack').value;if($('format').value)f.format=$('format').value;if($('triangles').value!=='')f.max_triangles=Number($('triangles').value);if($('rigged').value)f.rigged=$('rigged').value==='true';return f; }
function settings(){const args={mode:$('mode').value,filters:filters(),limit:Number($('limit').value)};if(args.mode==='reference'){args.reference_asset_id=$('reference-asset').value;args.reference_view=$('reference-view').value;}else args.query=$('query').value;return args;}
function addOptions(select,values,label=x=>x){for(const value of values){const o=node('option',label(value));o.value=value;select.append(o);}}
function captionBadge(item){if(item.caption_status==='warning')return node('span','Caption warning','badge warning caption-quality-badge');return null;}
function cardLabel(item){return `${item.name}, ${packName(item.pack)}${item.source_faulty ? ', source fault' : ''}${item.caption_status==='warning' ? ', caption warning' : ''}`;}
function refreshCaptionBadge(card,item,info){const latest={...item,...info};card.button.querySelector('.caption-quality-badge')?.remove();const flag=captionBadge(latest);if(flag)card.button.querySelector('.badges').append(flag);card.button.setAttribute('aria-label',cardLabel(latest));}
function hasDescription(item){return !item.caption_faulty&&!['pending',undefined].includes(item.caption_status);}
function badges(item){const el=node('div',undefined,'badges');if(item.source_faulty)el.append(node('span','Source fault','badge fault'));const caption=captionBadge(item);if(caption)el.append(caption);if(hasDescription(item)&&item.caption_owner_review!=='approved')el.append(node('span','Review '+(item.caption_owner_review||'pending'),'badge review'));return el;}
function renderCards(items, generation, collection=state, append=false) {
  const grid=collectionElement(collection,'grid');
  collection.items = append ? collection.items.concat(items) : items;
  if(!append){collection.cardNodes.clear();grid.replaceChildren();collection.observer?.disconnect();}
  collectionElement(collection,'empty').hidden = collection.items.length > 0;
  for (const item of items) {
    const button = node('button', undefined, 'card');
    button.type = 'button';
    button.dataset.id = item.asset_id;
    button.setAttribute('aria-pressed', String(item.asset_id === collection.selected));
    button.setAttribute('aria-label', cardLabel(item));
    const thumb = node('div', undefined, 'thumb');
    thumb.append(node('span', 'Loading existing preview…', 'placeholder'));
    const text = node('div', undefined, 'card-text');
    text.append(node('span', item.name, 'card-name'), node('span', packName(item.pack), 'pack'), badges(item));
    button.append(thumb, text);
    button.onclick = () => selectAsset(item.asset_id,null,'three_quarter',true,collection);
    grid.append(button);
    collection.cardNodes.set(item.asset_id, {button, thumb});
  }
  if(!append)collection.observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting){collection.observer.unobserve(entry.target);const item=collection.items.find(i=>i.asset_id===entry.target.dataset.id);if(item)loadThumbnails([item],generation,collection);}}},{root:collection===state?null:$('source-collection'),rootMargin:'100px'});
  for(const item of items)collection.observer.observe(collection.cardNodes.get(item.asset_id).button);
  if(collection===state)for(const item of items){if(!$('reference-asset').querySelector(`option[value="${item.asset_id}"]`)){const option=node('option',item.name+' · '+packName(item.pack));option.value=item.asset_id;$('reference-asset').append(option);}}

}
async function loadThumbnails(items,generation,collection=state){
 for(const item of items)state.thumbQueue.push({item,generation,collection,version:collection.context.generation});
 async function load(){while(state.thumbQueue.length){
  const {item,generation,collection,version}=state.thumbQueue.shift();if(generation!==collection.generation)continue;
  let result;try{result=await collection.api.thumbnail(item.asset_id,version);}catch(error){result={reason:error.message};}
  if(generation!==collection.generation)continue;
  if(result.status==='stale'){if(collection===state)status('Library version changed; refresh the published view.');else sourceBrowseError('Saved source contents changed. Return to asset sources and reopen this source.');continue;}
  const card=collection.cardNodes.get(item.asset_id);if(!card)continue;const payload=result.payload||{};card.thumb.replaceChildren();
  if(result.image){const image=node('img');image.src='data:image/png;base64,'+result.image;image.alt=item.name+' — three-quarter preview';card.thumb.append(image);}
  else{const pending=payload.preview?.status==='pending',excluded=payload.preview?.status==='excluded';const label=excluded?'Preview not selected':pending?'Preview not generated':'Preview unavailable';const reason=payload.preview?.reason||payload.reason||result.reason||'Requested three-quarter preview unavailable';const placeholder=node('span',label,'placeholder');placeholder.title=reason;placeholder.setAttribute('aria-label',label+': '+reason);card.thumb.append(placeholder);const accessibleReason=node('span',reason,'sr');accessibleReason.id=(collection===state?'':'source-')+'preview-state-'+item.asset_id;card.button.append(accessibleReason);card.button.setAttribute('aria-describedby',accessibleReason.id);card.button.querySelector('.badges').append(node('span',excluded?'Preview excluded':pending?'Preview pending':'Preview fault',pending||excluded?'badge review':'badge fault'));}
  if(payload.presentation)refreshCaptionBadge(card,item,payload.presentation);if(payload.presentation?.faults?.length)card.button.title='Recorded faults available in detail';
 }}
 const tasks=[];while(state.thumbWorkers<3&&state.thumbQueue.length){state.thumbWorkers++;tasks.push(load().finally(()=>state.thumbWorkers--));}await Promise.all(tasks);
}

async function browse(resetPage=true){searchBusy(null);if(resetPage)state.offset=0;state.browsing=true;paging.hidden=false;const generation=++state.generation;state.lastSettings=null;$('copy-settings').disabled=true;$('reproduce-note').hidden=true;$('candidate-note').hidden=true;$('grid').setAttribute('aria-busy','true');resetError();$('results-title').textContent='Library assets';status('Loading this page…');try{const result=await state.api.browse(filters(),state.offset,40);if(generation!==state.generation)return;if(result.status==='faulty')throw Error(result.reason);if(result.generation!==state.context.generation)throw Error('Published version changed; refreshing context.');state.total=result.total_count;renderCards(result.items,generation);$('page-info').textContent=`${state.offset+1}–${state.offset+result.items.length} of ${result.total_count}`;$('previous-page').disabled=state.offset===0;$('next-page').disabled=state.offset+40>=result.total_count;status(`${result.total_count} matching assets · thumbnails load as they become visible`);}catch(error){if(generation===state.generation){fail(error.message);status('Browse unavailable. Refresh the published view to load its current version.');}}finally{if(generation===state.generation)$('grid').setAttribute('aria-busy','false');}}
async function search(){const args=settings();if(state.activeSearch!==null&&JSON.stringify(args)===state.activeSearchSettings)return;state.browsing=false;paging.hidden=true;if(args.mode!=='reference'&&!args.query.trim()){await browse();return;}const generation=++state.generation;state.activeSearchSettings=JSON.stringify(args);searchBusy(generation);state.lastSettings=null;$('copy-settings').disabled=true;$('reproduce-note').hidden=true;$('candidate-note').hidden=args.mode==='keyword';$('grid').setAttribute('aria-busy','true');resetError();$('results-title').textContent='Search shortlist';status(args.mode==='keyword'?'Searching the library…':'Searching the library… First model load can take longer; the window remains available.');try{const result=await state.api.search(args);if(generation!==state.generation)return;const payload=result.payload||{};if(result.is_error||result.status==='faulty'||payload.status==='faulty')throw Error(payload.reason||result.reason||'Search failed');if(payload.generation!==state.context.generation)throw Error("Published version changed; refresh the view.");state.lastSettings=structuredClone(result.arguments);$('copy-settings').disabled=false;$('reproduce-note').hidden=false;renderCards(payload.results,generation);status(`${payload.results.length} candidates · ${result.elapsed_seconds.toFixed(2)} s${payload.truncated?' · shortlist truncated by the shared response cap':''}${payload.fault_count?' · '+payload.fault_count+' recorded exclusion / preview faults':''}`);if(payload.faults?.length){const note=payload.faults.map(f=>`${f.channel}: ${f.reason}`).join('\n');$('status').title=note;}}catch(error){if(generation===state.generation){fail(error.message);status('Search is faulty. No fallback or automatic retry. Earlier cards are retained.');}}finally{if(generation===state.generation){searchBusy(null);$('grid').setAttribute('aria-busy','false');}}}
function section(title){const el=node('section',undefined,'evidence');el.append(node('h3',title));return el;}
function rawDetails(title,value){const d=node('details');d.append(node('summary',title),node('pre',display(value)));return d;}
function facts(entries){const dl=node('dl');for(const [k,v] of entries){dl.append(node('dt',k),node('dd',display(v)));}return dl;}
async function copy(text,message){try{const result=await state.api.copy_text(text);if(result.status!=='copied')throw Error(result.reason);status(message);}catch(error){fail(error.message);}}
function collectionVisible(collection){return (collection===state||collection===state.sourceBrowse)&&!$(collection===state?'library-view':'source-browser-view').hidden;}
function closeDetail(collection=activeCollection()){
 if(collectionVisible(collection))LALPreview.dispose();
 ++collection.detailGeneration;const selected=collection.selected;collection.selected=null;
 for(const {button} of collection.cardNodes.values())button.setAttribute('aria-pressed','false');
 const detail=collectionElement(collection,'detail');detail.removeAttribute('aria-busy');
 detail.innerHTML='<div class="detail-empty"><span aria-hidden="true">◇</span><h2>Take a closer look</h2><p>Select an asset to inspect its views, sources, and evidence.</p></div>';
 if(collectionVisible(collection))collection.cardNodes.get(selected)?.button.focus({preventScroll:true});
}
async function selectAsset(identifier,format=null,view='three_quarter',moveFocus=true,collection=activeCollection()){
 if(!collectionVisible(collection))return;
 LALPreview.dispose();collection.selected=identifier;
 for(const [id,{button}] of collection.cardNodes)button.setAttribute('aria-pressed',String(id===identifier));
 const generation=++collection.detailGeneration,detail=collectionElement(collection,'detail');detail.setAttribute('aria-busy','true');
 detail.replaceChildren(node('div','Loading asset evidence…','detail-body'));
 if(moveFocus&&innerWidth<761)detail.scrollIntoView({block:'start'});
 try{
  const result=await collection.api.asset(identifier,format,view,collection.context.generation);
  if(generation!==collection.detailGeneration||!collectionVisible(collection))return;
  if(!result.payload)throw Error(result.reason||'Asset detail unavailable');
  renderDetail(result,identifier,format,view,moveFocus,collection);
 }catch(error){if(generation===collection.detailGeneration)detail.replaceChildren(node('div','Detail fault: '+error.message,'detail-body'));}
 finally{if(generation===collection.detailGeneration)detail.setAttribute('aria-busy','false');}
}
function renderDetail(result,identifier,format,view,moveFocus,collection=activeCollection()){const p=result.payload,info=p.presentation||{};const body=node('div',undefined,'detail-body');const head=node('div',undefined,'detail-header');const heading=node('h2',info.name||p.name||identifier);heading.tabIndex=-1;const close=node('button','×','close-detail');close.type='button';close.setAttribute('aria-label','Close asset detail');close.onclick=()=>closeDetail(collection);head.append(heading,close);body.append(head,node('p',packName(info.pack||p.pack||''),'pack'));if(p.status==='faulty')body.append(node('p',p.reason,'state-banner'));
 const preview=node('div',undefined,'detail-preview');body.append(preview);LALPreview.mount(preview,{assetId:identifier,name:info.name||p.name||identifier,sourceFormat:p.selected_source?.format,version:collection.context.generation,onSearch:()=>collection===state?$('query').focus():collectionElement(collection,'grid').focus(),image:result.image,imageAlt:(info.name||p.name)+' — '+(views[view]||view)+' view',imageReason:p.preview?.reason||p.reason||'Requested view unavailable; no substitute.'},collection.api);
 const controls=node('div',undefined,'detail-controls');const viewLabel=node('label','Preview view'),viewSelect=node('select');viewSelect.id=(collection===state?'':'source-')+'detail-view';addOptions(viewSelect,collection.context.views,x=>views[x]||x);viewSelect.value=view;viewSelect.onchange=()=>selectAsset(identifier,format,viewSelect.value,false,collection);viewLabel.append(viewSelect);const formatLabel=node('label','Source format'),formatSelect=node('select');formatSelect.id=(collection===state?'':'source-')+'detail-format';addOptions(formatSelect,info.formats||[]);formatSelect.value=format||p.selected_source?.format||info.formats?.[0]||'';formatSelect.onchange=()=>selectAsset(identifier,formatSelect.value,view,false,collection);formatLabel.append(formatSelect);controls.append(viewLabel,formatLabel);body.append(controls);
 const source=section('Source location');if(p.selected_source){source.append(node('p',p.selected_source.format.toUpperCase()+' · original file · verified hash'),node('code',p.selected_source.resolved_path,'path'));const button=node('button','Copy source path');button.type='button';button.onclick=()=>copy(p.selected_source.resolved_path,'Source path copied. Asset files were not copied.');source.append(button,rawDetails('Source SHA-256',p.selected_source.sha256));}else source.append(node('p','No currently verified usable source. See recorded fault evidence.'));body.append(source);
 const technical=section('Measured technical facts'),t=info.technical||{};technical.append(node('p',info.scale,'hint'));const selectedFormat=p.selected_source?.format;if(selectedFormat&&t.inspected_format&&selectedFormat!==t.inspected_format)technical.append(node('p',selectedFormat.toUpperCase()+' is uninspected; the facts below describe '+t.inspected_format.toUpperCase()+'.','state-banner'));technical.append(facts([['Inspected format',t.inspected_format?.toUpperCase()],['Triangles',t.evaluated_instance_totals?.triangles],['Vertices',t.evaluated_instance_totals?.vertices],['Armatures',t.armatures?.length],['Actions',t.actions?.length],['Physical scale','Unknown']]));technical.append(rawDetails('Measurement and inspected-source evidence',t));body.append(technical);
 const observations=section('Generated visual observations');observations.append(node('p','Provisional observations, separate from measured facts.','hint'));if(info.observations){observations.append(node('p',info.observations.description||display(info.observations)),rawDetails('Structured observations',info.observations));}else observations.append(node('p',info.caption_faulty?'Description generation failed; the recorded fault is listed below.':'No description yet. Descriptions are optional: this asset is searchable by name and image. Generate them in Settings → Asset sources.'));body.append(observations);
 const quality=info.caption_quality||{},captionNotes=section('Caption warnings and notes');const notes=node('ul');for(const issue of quality.issues||[]){if(issue.severity==='fault')continue;notes.append(node('li',(issue.severity==='warning'?'Warning: ':'Note: ')+issue.reason,issue.severity==='warning'?'caption-warning':undefined));}captionNotes.append(notes.childNodes.length?notes:node('p',quality.status==='fault'?'Caption unavailable; see recorded faults below.':'No caption review notes recorded.'),rawDetails('Original caption review evidence',{classification:quality.classification,issues:quality.issues,original_findings:info.caption_faults}));body.append(captionNotes);
 const suggestions=section('Suggested uses');const list=node('ul');for(const use of info.suggested_uses||[])list.append(node('li',use));suggestions.append(list.childNodes.length?list:node('p','No suggestions recorded.'),node('p','Suggestions are interpretations, not verified asset capabilities.','hint'));body.append(suggestions);
 const review=section('Owner review');review.append(facts([['Caption review',info.owner_review||'pending'],['Artistic suitability',info.owner_artistic_approval||'pending']]));body.append(review);
 const faults=section('Recorded faults');const faultBox=node('div',undefined,'fault-list'),faultList=node('ul');const combined=[...(info.source_faults||[]),...(quality.issues||[]).filter(i=>i.severity==='fault'),...(info.faults||[])];if(p.preview?.status==='faulty')combined.push({channel:'requested preview',reason:p.preview.reason});for(const fault of combined){const text=typeof fault==='string'?fault:fault.evidence||fault.reason||fault.issue||fault.kind||display(fault);faultList.append(node('li',text));}faultBox.append(combined.length?faultList:node('p','No faults recorded for this detail.'));faults.append(faultBox,rawDetails('Full fault and processing evidence',{source:info.source_faults,caption:quality,runtime:info.faults,processing:info.processing}));body.append(faults);
 const deps=section('Dependencies');deps.append(node('p',p.dependency_completeness||'Known references only; completeness is unknown.'),rawDetails('Dependency paths and referring-source evidence',p.dependencies||info.dependencies||[]));body.append(deps);
 const license=section('License evidence');license.append(node('p','Supplied source evidence; unknowns remain unknown.','hint'));const licenses=info.license_evidence||[];license.append(rawDetails('Recorded license evidence',licenses));body.append(license);collectionElement(collection,'detail').replaceChildren(body);if(moveFocus)heading.focus();else if(collectionVisible(collection))collectionElement(collection,format?'detail-format':'detail-view').focus({preventScroll:true});}
$('search-form').addEventListener('submit',event=>{event.preventDefault();search();});
$('clear').onclick=()=>{++state.detailGeneration;state.selected=null;$('query').value='';for(const id of ['pack','format','triangles','rigged'])$(id).value='';$('mode').value='combined';$('limit').value='20';$('reference-controls').hidden=true;$('query').disabled=false;closeDetail();browse();$('query').focus();};
$('mode').onchange=()=>{const reference=$('mode').value==='reference';$('reference-controls').hidden=!reference;$('query').disabled=reference;$('query').maxLength=$('mode').value==='keyword'?256:1024;};
$('copy-settings').onclick=()=>{if(state.lastSettings)copy(JSON.stringify(state.lastSettings,null,2),'Exact MCP search_assets settings copied. Use the same catalog and index versions.');};
for(const gridId of ['grid','source-grid'])$(gridId).addEventListener('keydown',event=>{
 const grid=$(gridId),card=event.target.closest('.card');if(!card)return;
 const cards=[...grid.querySelectorAll('.card')],index=cards.indexOf(card),columns=Math.max(1,getComputedStyle(grid).gridTemplateColumns.split(' ').length);
 let next=index;if(event.key==='ArrowRight')next++;else if(event.key==='ArrowLeft')next--;else if(event.key==='ArrowDown')next+=columns;else if(event.key==='ArrowUp')next-=columns;else if(event.key==='Home')next=0;else if(event.key==='End')next=cards.length-1;else return;
 event.preventDefault();cards[Math.max(0,Math.min(cards.length-1,next))]?.focus();
});
document.addEventListener('keydown',event=>{
 if(LALPreview.current?.dialog.open&&event.key==='Escape'){event.preventDefault();if(LALPreview.current.fullscreen)LALPreview.current.exitFullscreen();else LALPreview.current.stop();return;}
 if(LALPreview.current?.fullscreen)return;
 const collection=activeCollection();if(event.key==='Escape'&&collection.selected&&collectionVisible(collection))closeDetail(collection);
 if(event.ctrlKey&&event.key.toLowerCase()==='f'&&!$('library-view').hidden){event.preventDefault();$('query').focus();}
});
window.addEventListener('pywebviewready',async()=>{state.api=window.pywebview.api;try{state.context=await state.api.context();if(state.context.status==='faulty')throw Error(state.context.reason);$('scope').textContent=`Approved ${state.context.pilot_count}-asset library`;$('inventory').textContent=`${state.context.inventory_count} inventory records · ${state.context.generation}`;addOptions($('pack'),state.context.packs,packName);addOptions($('format'),state.context.formats,x=>x.toUpperCase());$('version').textContent=`Catalog ${state.context.versions.catalog.slice(0,10)} · index ${state.context.versions.index.slice(0,10)}`;$('version').title=JSON.stringify(state.context.versions,null,2);await browse();renderCoverage(state.context);await loadSources();watchChanges();if(state.context.managed_sources)await sourceAction('scan');$('query').focus();}catch(error){fail(error.message);status('Startup data is faulty. No model loading or fallback attempted.');$('grid').setAttribute('aria-busy','false');}});

const paging=node('nav',undefined,'paging');paging.setAttribute('aria-label','Asset pages');
for(const [id,label] of [['previous-page','Previous page'],['page-info',''],['next-page','Next page']]){const element=node(id==='page-info'?'span':'button',label);element.id=id;if(element.tagName==='BUTTON')element.type='button';paging.append(element);}$('grid').before(paging);
$('previous-page').onclick=()=>{state.offset=Math.max(0,state.offset-40);browse(false);};$('next-page').onclick=()=>{state.offset+=40;browse(false);};
const operations=node('div',undefined,'library-operations');
const reload=node('button','Refresh published view');reload.type='button';reload.onclick=()=>refreshContext(true);operations.append(reload);$('search-form').after(operations);
const failuresButton=node('button','Importing failures report');failuresButton.id='open-import-failures';failuresButton.type='button';operations.append(failuresButton);
async function refreshContext(force=false){
 if(!state.api)return;
 try{
  const context=await state.api.context();if(context.status==='faulty')throw Error(context.reason);
  const changed=context.generation!==state.context?.generation||context.sources_revision!==state.context?.sources_revision;
  if(changed||force){
   const wasBrowsing=state.browsing;let selected=state.selected;
   ++state.generation;++state.detailGeneration;searchBusy(null);state.context=context;state.lastSettings=null;$('copy-settings').disabled=true;
   if(context.visible_asset_ids){const visible=new Set(context.visible_asset_ids);renderCards(state.items.filter(item=>visible.has(item.asset_id)),state.generation);if(selected&&!visible.has(selected)){closeDetail(state);selected=null;}}
   for(const [id,values,label] of [['pack',context.packs,packName],['format',context.formats,x=>x.toUpperCase()]]){const select=$(id),value=select.value;while(select.options.length>1)select.remove(1);addOptions(select,values,label);select.value=values.includes(value)?value:'';}
   $('scope').textContent=`${context.pilot_count} library assets`;$('inventory').textContent=`${context.inventory_count} published records`;
   $('version').textContent=`Catalog ${context.versions.catalog.slice(0,10)} · index ${context.versions.index.slice(0,10)}`;
   if(wasBrowsing)await browse(false);else await search();
   if(selected){if(!$('library-view').hidden)await selectAsset(selected,null,'three_quarter',false,state);}else closeDetail(state);
  }
  renderCoverage(context);
 }catch(error){fail(error.message);}
}
function renderCoverage(context){
 const source=context.working_coverage||context.coverage,coverage=Object.values(source.packs);
 const pending=coverage.reduce((n,p)=>n+(p.stages.caption.pending||0),0),failed=coverage.reduce((n,p)=>n+(p.stages.caption.failed||0),0);
 $('coverage').textContent=`${context.coverage.membership} in the library · ${pending} without descriptions · ${failed} description failures`;
}
const coverageLine=node('p',undefined,'hint');coverageLine.id='coverage';operations.after(coverageLine);
// One cheap stat-only poll; library and source data reload only when their token changes.
const changeTokens={library:null,sources:null};let watchingChanges=false;
const workerMessages={loading_libraries:'Searching the library… Preparing the search runtime; the window remains available.',loading_model:'Searching the library… Loading the search model (first search only); the window remains available.'};
async function watchChanges(){
 if(watchingChanges)return;watchingChanges=true;
 const first=await state.api.changes();if(first.status!=='faulty'){changeTokens.library=first.library;changeTokens.sources=first.sources;}
 setInterval(async()=>{
  if(state.checkingChanges)return;state.checkingChanges=true;
  try{
   const tokens=await state.api.changes();if(tokens.status==='faulty')return;
   const sourcesChanged=tokens.sources!==changeTokens.sources,libraryChanged=tokens.library!==changeTokens.library;
   if(state.activeSearch!==null&&workerMessages[tokens.worker])status(workerMessages[tokens.worker]);
   changeTokens.sources=tokens.sources;changeTokens.library=tokens.library;
   if(libraryChanged)await refreshContext();
   // Running operations also report worker liveness, which is not a file change.
   if(sourcesChanged||state.sources.some(source=>operationActive(source.operation)))await loadSources();
  }finally{state.checkingChanges=false;}
 },1500);
}


const sourceCards=new Map();state.sources=[];state.sourcesRevision=null;state.loadingSources=false;
function operationActive(operation){return ['queued','scanning','processing','publishing','cancelling','verifying'].includes(operation?.status);}
function sourceMessage(source){if(source.scan_fault)return source.scan_fault;if(source.processing_paused)return 'Processing paused. Select formats in General to resume.';if(!source.scanned)return 'Waiting for the source scan. Assets must be processed before they appear in searches.';if(source.needs_processing)return `${source.pending||0} ${(source.pending||0)===1?'asset needs':'assets need'} processing or publication.`;if(source.failed)return 'Import finished. Recorded failures are listed in the importing failures report.';if(source.skipped_formats&&source.eligible_assets===0)return 'No assets match the selected processing formats. Existing results remain available.';if(source.skipped_formats)return 'Selected formats are up to date. Other assets remain scanned and saved.';return 'Up to date and published.';}
function renderSourceWarnings(){
 const shown=new Set();
 for(const source of state.sources){
  const operation=source.operation?.operation==='describe'?{}:(source.operation||{}),active=operationActive(operation);
  if(!source.needs_processing&&!source.scan_fault&&!active)continue;
  shown.add(source.key);let card=sourceCards.get(source.key);
  if(!card){
   const root=node('article',undefined,'source-warning'),title=node('h3'),path=node('p',undefined,'source-path'),message=node('p');
   const bar=node('progress');bar.max=100;bar.setAttribute('aria-label','Processing and publishing progress');
   const label=node('p',undefined,'source-progress-label'),actions=node('div',undefined,'source-actions'),process=node('button','Process assets','primary'),cancel=node('button','Cancel');
   process.type=cancel.type='button';process.dataset.source=cancel.dataset.source=source.key;process.dataset.action='process';cancel.dataset.action='cancel';
   process.onclick=()=>sourceAction('process',source.key);cancel.onclick=()=>sourceAction('cancel',source.key);actions.append(process,cancel);root.append(title,path,message,bar,label,actions);$('source-warnings').append(root);
   card={root,title,path,message,bar,label,process,cancel};sourceCards.set(source.key,card);
  }
  card.title.textContent=source.name;card.path.textContent=source.path;card.message.textContent=sourceMessage(source);
  const cancelPending=operation.status==='cancelling';
  card.process.disabled=operationActive(source.operation)||!source.enabled||source.processing_paused;card.process.title=source.processing_paused?'Select processing formats in Settings → General':source.enabled?'':'Enable this source in Settings before processing';
  card.cancel.hidden=!active;card.cancel.disabled=cancelPending;card.cancel.textContent=cancelPending?'Cancelling…':'Cancel';
  card.bar.hidden=!(active||operation.status==='cancelled'||operation.status==='complete_with_faults');card.bar.value=Math.round((operation.progress||0)*100);
  card.bar.setAttribute('aria-valuetext',`${Math.round((operation.progress||0)*100)}% — ${operation.phase||'Waiting'}`);
  card.label.textContent=operation.reason||((active||operation.status==='cancelled'||operation.status==='complete_with_faults')?`${operation.phase||operation.status}${operation.total?' · '+operation.completed+' / '+operation.total:''}`:'');
 }
 for(const [key,card] of sourceCards){if(!shown.has(key)){card.root.remove();sourceCards.delete(key);}}
 $('source-warnings').hidden=!shown.size;
}
function renderSourceSettings(){
 const focused=document.activeElement?.dataset;const focusKey=focused?.source,focusAction=focused?.action;
 $('source-list').replaceChildren();$('sources-empty').hidden=state.sources.length>0;
 for(const source of state.sources){
  const row=node('article',undefined,'source-row'),info=node('div'),controls=node('div',undefined,'source-controls');
  const heading=node('h3'),browseButton=node('button',undefined,'source-browse-link');browseButton.type='button';
  browseButton.dataset.source=source.key;browseButton.dataset.action='browse';browseButton.setAttribute('aria-label','Browse assets in '+source.name);browseButton.title='Browse source contents';
  const icon=node('span','🔍','source-browse-icon');icon.setAttribute('aria-hidden','true');browseButton.append(node('span',source.name),icon);browseButton.onclick=()=>openSourceBrowser(source.key);heading.append(browseButton);
  info.append(heading,node('p',source.path),node('p',sourceMessage(source)));
  const counts=source.format_counts;
  info.append(node('p',counts?Object.entries(counts).map(([format,count])=>`${format==='gltf'?'glTF / GLB':format.toUpperCase()}: ${count}`).join(' · '):'Format counts appear after scanning.','source-format-counts'));
  if(source.import_formats)info.append(node('p','Imported formats: '+(source.import_formats.length?source.import_formats.map(format=>format==='gltf'?'glTF / GLB':format.toUpperCase()).join(', '):'none')+'. Other original formats are retained and excluded from imports.','hint'));
  info.append(descriptionBlock(source));
  const label=node('label',undefined,'source-enabled'),checkbox=node('input');checkbox.type='checkbox';checkbox.checked=source.enabled;checkbox.dataset.source=source.key;checkbox.dataset.action='enabled';checkbox.setAttribute('aria-label','Enable '+source.name);
  checkbox.onchange=()=>sourceAction('enabled',source.key,null,checkbox.checked);label.append(checkbox,document.createTextNode('Enabled'));
  const remove=node('button','Remove');remove.type='button';remove.dataset.source=source.key;remove.dataset.action='remove';remove.disabled=operationActive(source.operation);remove.onclick=()=>sourceAction('remove',source.key);
  controls.append(label,remove);row.append(info,controls);$('source-list').append(row);
 }
 // Starting or finishing a description run swaps its button; keep focus on the counterpart.
 const counterpart={describe:'cancel-describe','cancel-describe':'describe'}[focusAction];
 if(focusKey&&focusAction){const controls=[...$('source-list').querySelectorAll('[data-source]')].filter(x=>x.dataset.source===focusKey);(controls.find(x=>x.dataset.action===focusAction)||controls.find(x=>x.dataset.action===counterpart))?.focus();}
}
// Descriptions are optional extra data (decision 0008); each source generates them on request.
function plural(n,one,many){return `${Number(n).toLocaleString()} ${n===1?one:many}`;}
function describeActive(source){return source.operation?.operation==='describe'&&operationActive(source.operation);}
function descriptionSummary(source){
 const d=source.descriptions;if(!d)return 'Description counts appear after scanning.';
 const parts=[d.complete&&plural(d.complete,'description','descriptions')+' written',d.missing&&`${Number(d.missing).toLocaleString()} missing`,d.failed&&`${Number(d.failed).toLocaleString()} failed`].filter(Boolean);
 return parts.length?parts.join(' · '):d.unavailable?'Descriptions can be generated after assets are processed.':'No assets to describe.';
}
function descriptionBlocked(source){
 const d=source.descriptions||{};
 if(!source.enabled)return 'Enable this source to generate descriptions.';
 if(source.processing_paused)return 'Processing is paused. Select formats in General to generate descriptions.';
 if(operationActive(source.operation))return 'Available when the current operation for this source finishes.';
 if(!d.missing)return d.failed?'Nothing left to generate. Failed descriptions are recorded and not retried.':'Nothing to generate right now.';
 return '';
}
const DESCRIBE_RESULTS={complete:'Last run finished.',complete_with_faults:'Last run finished; some descriptions failed and were recorded.',cancelled:'Last run was cancelled; finished descriptions were published.',faulty:'Last run stopped.',interrupted:'Last run was interrupted.'};
function descriptionBlock(source){
 const block=node('div',undefined,'source-descriptions'),operation=source.operation||{},id='describe-help-'+source.key;
 const heading=node('p',undefined,'source-descriptions-summary');heading.append(node('strong','Descriptions '),document.createTextNode(descriptionSummary(source)));block.append(heading);
 if(describeActive(source)){
  const bar=node('progress');bar.max=100;bar.value=Math.round((operation.progress||0)*100);bar.setAttribute('aria-label','Description progress for '+source.name);
  const phase=`${operation.phase||'Working'}${operation.total?' · '+operation.completed+' / '+operation.total:''}`;bar.setAttribute('aria-valuetext',`${bar.value}% — ${phase}`);
  const cancel=node('button',operation.status==='cancelling'?'Cancelling…':'Cancel');cancel.type='button';cancel.disabled=operation.status==='cancelling';cancel.dataset.source=source.key;cancel.dataset.action='cancel-describe';cancel.onclick=()=>sourceAction('cancel',source.key);
  block.append(bar,node('p',phase,'source-progress-label'),cancel);return block;
 }
 const blocked=descriptionBlocked(source),button=node('button','Generate descriptions');button.type='button';button.dataset.source=source.key;button.dataset.action='describe';
 button.disabled=!!blocked;button.setAttribute('aria-describedby',id);button.onclick=()=>sourceAction('describe',source.key);
 const help=node('p',blocked||`Runs in the background on this computer’s GPU. Assets stay searchable by name and image meanwhile.`,'hint');help.id=id;
 block.append(button,help);
 if(operation.operation==='describe'&&DESCRIBE_RESULTS[operation.status])block.append(node('p',DESCRIBE_RESULTS[operation.status]+(operation.reason?' '+operation.reason:''),'hint'+(operation.reason?' source-describe-reason':'')));
 return block;
}
async function loadSources(){
 if(!state.api||state.loadingSources)return;state.loadingSources=true;
 try{
  const result=await state.api.sources();if(result.status==='faulty')throw Error(result.reason);
  state.sources=result.sources||[];renderSourceWarnings();updateNotifications(result.notifications||[]);
  const changed=state.sourcesRevision!==result.revision;state.sourcesRevision=result.revision;
  if(!$('settings-view').hidden)renderSourceSettings();
  if(!$('import-failures-view').hidden&&changed)await loadImportFailures();
  if(changed&&state.context&&result.revision!==state.context.sources_revision)await refreshContext();
 }catch(error){$('sources-message').textContent=error.message;}finally{state.loadingSources=false;}
}
async function sourceAction(action,key=null,directory=null,enabled=null){
 // Scans and processing never invalidate visible cards; library changes arrive through refreshContext.
 try{
  const result=await state.api.source_action(action,key,directory,enabled);if(result.status==='faulty')throw Error(result.reason);
  if(action==='cancel'){const source=state.sources.find(x=>x.key===key);if(source)source.operation={...source.operation,status:'cancelling',phase:result.reason};renderSourceWarnings();}
  $('sources-message').textContent=result.reason||'';
  if(action==='add')$('source-directory').value='';
  if(['enabled','remove'].includes(action)){closeDetail(state);await refreshContext(true);}
  await loadSources();
 }catch(error){$('sources-message').textContent=error.message;if($('settings-view').hidden)fail(error.message);await loadSources();}
}
function showLibraryView(view){
 LALPreview.pause();++state.detailGeneration;if(state.sourceBrowse)++state.sourceBrowse.detailGeneration;
 for(const id of ['library-view','settings-view','import-failures-view','source-browser-view'])$(id).hidden=id!==view;
 const skip=document.querySelector('.skip');skip.hidden=!['library-view','source-browser-view'].includes(view);skip.href=view==='source-browser-view'?'#source-grid':'#grid';
 if(view==='library-view'&&state.selected)selectAsset(state.selected,null,'three_quarter',false,state);
}
function sourceBrowseError(reason){$('source-browser-error').textContent=reason;$('source-browser-error').hidden=false;if(state.sourceBrowse)state.sourceBrowse.finished=true;$('source-load-more').hidden=true;}
function sourceApi(key){
 const api={preview_shell:()=>state.api.preview_shell()};
 for(const name of ['asset','thumbnail','preview_prepare','preview_file','preview_fault','preview_release'])api[name]=(...args)=>state.api['source_'+name](key,...args);
 return api;
}
async function openSourceBrowser(key){
 const source=state.sources.find(item=>item.key===key);if(!source)return;
 if(state.sourceBrowse){++state.sourceBrowse.generation;++state.sourceBrowse.detailGeneration;state.sourceBrowse.observer?.disconnect();}
 state.sourcesScroll=window.scrollY;state.sourceReturnKey=key;
 const collection={key,api:sourceApi(key),context:{generation:null,views:Object.keys(views)},items:[],cardNodes:new Map(),generation:0,detailGeneration:0,selected:null,total:0,loading:false,finished:false};
 state.sourceBrowse=collection;
 showLibraryView('source-browser-view');closeDetail(collection);
 $('source-browser-title').textContent=source.name;$('source-browser-path').textContent=source.path;
 $('source-browser-error').hidden=true;$('source-grid').replaceChildren();$('source-empty').hidden=true;$('source-load-more').hidden=true;
 $('source-collection').scrollTop=0;window.scrollTo(0,0);$('source-browser-title').focus({preventScroll:true});
 await browseSource(collection);
}
async function browseSource(collection=state.sourceBrowse){
 if(!collection||collection.loading||collection.finished||collection!==state.sourceBrowse)return;
 collection.loading=true;const generation=collection.generation;
 $('source-grid').setAttribute('aria-busy','true');$('source-load-more').disabled=true;
 $('source-browser-status').textContent=collection.items.length?`Loading more assets · ${collection.items.length} shown…`:'Loading saved source contents…';
 try{
  const result=await state.api.source_browse(collection.key,collection.items.length,40);
  if(collection!==state.sourceBrowse||generation!==collection.generation)return;
  if(result.status==='faulty')throw Error(result.reason);
  if(collection.context.generation&&collection.context.generation!==result.generation)throw Error('Saved source contents changed. Return to asset sources and reopen this source.');
  collection.context.generation=result.generation;collection.total=result.total_count;
  renderCards(result.items,generation,collection,collection.items.length>0);
  collection.finished=collection.items.length>=collection.total;
  const disabled=result.source.enabled?'':' · Disabled in library searches';
  $('source-browser-status').textContent=`${collection.total} ${collection.total===1?'saved asset':'saved assets'}${disabled}`;
  $('source-empty').textContent=result.reason||'This source has no saved assets.';
  $('source-empty').hidden=collection.items.length>0;$('source-load-more').hidden=collection.finished;
 }catch(error){if(collection===state.sourceBrowse&&generation===collection.generation){collection.finished=true;sourceBrowseError(error.message);$('source-browser-status').textContent=collection.items.length?`${collection.items.length} assets shown · could not load the rest`:'Source contents unavailable.';$('source-load-more').hidden=true;}}
 finally{collection.loading=false;if(collection===state.sourceBrowse&&generation===collection.generation){$('source-grid').setAttribute('aria-busy','false');$('source-load-more').disabled=false;}}
}
function maybeLoadSource(){
 const collection=state.sourceBrowse,area=$('source-collection');
 if(!$('source-browser-view').hidden&&area.scrollHeight-area.scrollTop-area.clientHeight<350)browseSource(collection);
}
$('source-load-more').onclick=()=>browseSource();
$('source-collection').addEventListener('scroll',maybeLoadSource);
$('close-source-browser').onclick=async()=>{
 const collection=state.sourceBrowse;++collection.generation;++collection.detailGeneration;collection.observer?.disconnect();LALPreview.dispose();
 showLibraryView('settings-view');selectSettingsTab('asset-sources');await loadSources();renderSourceSettings();
 window.scrollTo(0,state.sourcesScroll||0);
 [...$('source-list').querySelectorAll('[data-action="browse"]')].find(button=>button.dataset.source===state.sourceReturnKey)?.focus({preventScroll:true});
};
async function loadImportFailures(){
 if(state.loadingFailures)return;state.loadingFailures=true;
 $('import-failures-list').setAttribute('aria-busy','true');
 try{
  const result=await state.api.importing_failures();if(result.status==='faulty')throw Error(result.reason);
  const paths=result.paths||[],signature=JSON.stringify(paths);
  if(signature!==state.failurePaths){$('import-failures-list').replaceChildren(...paths.map(path=>node('li',path)));state.failurePaths=signature;}
  $('import-failures-list').hidden=!paths.length;$('import-failures-empty').hidden=!!paths.length;
  $('import-failures-summary').textContent=`${result.assets||0} ${(result.assets||0)===1?'asset':'assets'} with recorded failures · ${paths.length} ${paths.length===1?'path':'paths'}`;
  const unavailable=result.unavailable||[];$('import-failures-error').hidden=!unavailable.length;
  $('import-failures-error').textContent=unavailable.map(item=>`Could not read saved failures for ${item.source}: ${item.reason}`).join('\n');
 }catch(error){$('import-failures-error').hidden=false;$('import-failures-error').textContent=error.message;$('import-failures-summary').textContent='Could not load the failures report.';}
 finally{$('import-failures-list').setAttribute('aria-busy','false');state.loadingFailures=false;}
}
$('open-import-failures').onclick=async()=>{showLibraryView('import-failures-view');$('import-failures-title').focus();await loadImportFailures();};
$('close-import-failures').onclick=async()=>{showLibraryView('library-view');await loadSources();$('open-import-failures').focus();};
function selectSettingsTab(section,focus=false){
 for(const name of ['general','asset-sources']){
  const selected=name===section,tab=$(name+'-tab');
  tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;$(name+'-panel').hidden=!selected;
 }
 if(focus)$(section+'-tab').focus();
}
for(const section of ['general','asset-sources']){
 const tab=$(section+'-tab');tab.onclick=()=>selectSettingsTab(section);
 tab.onkeydown=event=>{
  if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
  event.preventDefault();selectSettingsTab(event.key==='Home'?'general':event.key==='End'?'asset-sources':section==='general'?'asset-sources':'general',true);
 };
}
async function loadGeneralSettings(){
 generalSettingsBusy(true);$('general-settings-message').textContent='Loading settings…';
 try{
  const result=await state.api.general_settings();if(result.status==='faulty')throw Error(result.reason);
  $('storage-budget').value=result.storage_budget_gib;for(const checkbox of $('processing-formats').querySelectorAll('input'))checkbox.checked=result.processing_formats.includes(checkbox.value);$('caption-batch-size').value=String(result.caption_batch_size);generalSettingsBusy(false);$('general-settings-message').textContent='';
 }catch(error){$('general-settings-message').textContent=error.message;}
}
function generalSettingsBusy(busy){for(const id of ['storage-budget','processing-formats','caption-batch-size','save-general-settings'])$(id).disabled=busy;}
$('general-settings-form').onsubmit=async event=>{
 event.preventDefault();if(!$('general-settings-form').reportValidity())return;
 const value=$('storage-budget').value,formats=[...$('processing-formats').querySelectorAll('input:checked')].map(input=>input.value);generalSettingsBusy(true);$('general-settings-message').textContent='Saving…';
 try{
  const result=await state.api.save_general_settings(value,formats,$('caption-batch-size').value);if(result.status==='faulty')throw Error(result.reason);
  $('storage-budget').value=result.storage_budget_gib;$('caption-batch-size').value=String(result.caption_batch_size);$('general-settings-message').textContent=result.processing_formats.length?`Saved. Storage budget: ${result.storage_budget_gib} GiB. Description batch size: ${result.caption_batch_size}. Selected formats apply to new processing batches.`:'Saved. Processing is paused because no formats are selected. Scanning and existing results remain available.';
  await loadSources();
 }catch(error){$('general-settings-message').textContent=error.message;}
 finally{generalSettingsBusy(false);}
};
$('open-settings').onclick=async()=>{showLibraryView('settings-view');selectSettingsTab('general');$('settings-title').focus();await Promise.all([loadGeneralSettings(),loadSources()]);};
$('close-settings').onclick=async()=>{showLibraryView('library-view');await loadSources();$('open-settings').focus();};
$('choose-source').onclick=async()=>{const result=await state.api.choose_source_directory();if(result.status==='selected')$('source-directory').value=result.directory;else if(result.status==='faulty')$('sources-message').textContent=result.reason;};
$('add-source').onclick=()=>{const directory=$('source-directory').value.trim();if(directory)sourceAction('add',null,directory);else $('sources-message').textContent='Choose an asset directory first.';};
// Notifications: saved notices about optional descriptions (decision 0008). They arrive with
// sources(), so the existing change poll is the only poll; actions call ordinary bridge methods.
state.notifications=[];state.notificationKeys=null;state.notificationSignature=null;
const relativeTime=new Intl.RelativeTimeFormat(undefined,{numeric:'auto'});
function ago(utc){const seconds=(Date.parse(utc)-Date.now())/1000;if(!Number.isFinite(seconds))return '';for(const [unit,size] of [['day',86400],['hour',3600],['minute',60]])if(Math.abs(seconds)>=size)return relativeTime.format(Math.round(seconds/size),unit);return 'just now';}
function elapsed(seconds){if(!seconds)return '';const minutes=Math.round(seconds/60);return minutes<1?`${seconds} s`:minutes<60?`${minutes} min`:`${Math.floor(minutes/60)} h ${minutes%60} min`;}
function notificationKey(item){return item.id+'@'+item.created_utc;}
function notificationContent(item){
 if(item.kind==='descriptions_ready')return {tone:'info',title:'Descriptions ready to generate',
  body:`${plural(item.missing,'asset has','assets have')} no description yet. They are already searchable by name and image; descriptions improve text search.`};
 const written=plural(item.written||0,'description','descriptions')+' written',remaining=item.remaining?` · ${Number(item.remaining).toLocaleString()} still missing`:'';
 switch(item.outcome){
  case 'complete':return {tone:'success',title:'Descriptions finished',body:`${written}${item.elapsed_seconds?' in '+elapsed(item.elapsed_seconds):''}. They are published and used by search.`};
  case 'complete_with_failures':return {tone:'warning',title:'Descriptions finished with failures',body:`${written} · ${Number(item.failed).toLocaleString()} failed. Failed descriptions are recorded and not retried; those assets stay searchable by name and image.`};
  case 'cancelled':return {tone:'info',title:'Description run cancelled',body:`${written} and published${remaining}.`};
  case 'stopped':return {tone:'fault',title:'Description run stopped',body:`${item.reason||'The run stopped.'} ${written} and published${remaining}.`};
  default:return {tone:'fault',title:'Description run interrupted',body:`${item.reason||'The run stopped unexpectedly.'} Finished descriptions are saved.`};
 }
}
function sourceExists(key){return state.sources.some(source=>source.key===key);}
function notificationButton(label,action,item,className){const button=node('button',label,className);button.type='button';button.dataset.notification=item.id;button.dataset.action=action;button.onclick=()=>notificationAction(action,item);return button;}
function notificationActions(item){
 const actions=[];if(!sourceExists(item.source_key))return actions;
 if(item.kind==='descriptions_ready')actions.push(notificationButton('Generate descriptions','generate',item,'primary'),notificationButton('Not now','dismiss',item));
 else{if(item.remaining&&['cancelled','stopped','interrupted'].includes(item.outcome))actions.push(notificationButton('Continue','generate',item,'primary'));actions.push(notificationButton('View source','view',item));}
 return actions;
}
function notificationElement(item,tag='li'){
 const content=notificationContent(item),root=node(tag,undefined,`notification tone-${content.tone}${item.read?'':' unread'}`);
 const head=node('div',undefined,'notification-head'),title=node('h3',content.title);
 const meta=node('p',[item.source_name,ago(item.created_utc)].filter(Boolean).join(' · '),'notification-meta');
 head.append(node('span',undefined,'notification-icon'),title);
 if(item.kind==='descriptions_report'){const close=notificationButton('×','dismiss',item,'notification-dismiss');close.setAttribute('aria-label','Dismiss: '+content.title+', '+item.source_name);head.append(close);}
 if(!item.read)title.prepend(node('span','Unread: ','sr'));
 root.append(head,meta,node('p',content.body,'notification-body'));
 const actions=notificationActions(item);if(actions.length){const row=node('div',undefined,'notification-actions');row.append(...actions);root.append(row);}
 return root;
}
function runningElement(source){
 const operation=source.operation,row=node('div',undefined,'notification running'),bar=node('progress');bar.max=100;bar.value=Math.round((operation.progress||0)*100);
 const phase=`${operation.phase||'Working'}${operation.total?' · '+operation.completed+' / '+operation.total:''}`;bar.setAttribute('aria-label','Description progress for '+source.name);bar.setAttribute('aria-valuetext',`${bar.value}% — ${phase}`);
 const head=node('div',undefined,'notification-head');head.append(node('span',undefined,'search-spinner'),node('h3','Generating descriptions'));
 const cancel=node('button',operation.status==='cancelling'?'Cancelling…':'Cancel');cancel.type='button';cancel.disabled=operation.status==='cancelling';cancel.dataset.notification='running-'+source.key;cancel.dataset.action='cancel';
 cancel.onclick=()=>sourceAction('cancel',source.key);const actions=node('div',undefined,'notification-actions');actions.append(cancel);
 row.append(head,node('p',source.name,'notification-meta'),bar,node('p',phase,'notification-body'),actions);return row;
}
function renderNotifications(){
 const running=state.sources.filter(describeActive),unread=state.notifications.filter(item=>!item.read).length;
 const signature=JSON.stringify([state.notifications,running.map(s=>[s.key,s.operation]),state.sources.map(s=>s.key),Math.floor(Date.now()/60000)]);
 const count=$('notifications-count');count.textContent=unread>9?'9+':String(unread);count.hidden=!unread;$('notifications-running-dot').hidden=!running.length||!!unread;
 $('open-notifications').setAttribute('aria-label',`Notifications${unread?', '+plural(unread,'unread','unread'):''}${running.length?', description run in progress':''}`);
 if(signature===state.notificationSignature)return;state.notificationSignature=signature;
 const panel=$('notifications-panel'),focused=panel.contains(document.activeElement)?document.activeElement.dataset:{};
 $('notifications-running').replaceChildren(...running.map(runningElement));
 $('notifications-list').replaceChildren(...state.notifications.map(item=>notificationElement(item)));
 $('notifications-empty').hidden=!!(state.notifications.length||running.length);$('notifications-read-all').disabled=!unread;
 if(focused.notification){const match=panel.querySelector(`[data-notification="${CSS.escape(focused.notification)}"][data-action="${CSS.escape(focused.action)}"]`);(match||$('notifications-title')).focus();}
}
function updateNotifications(items){
 const known=state.notificationKeys;state.notifications=items;state.notificationKeys=new Set(items.map(notificationKey));
 renderNotifications();
 // Only notices that arrive while the app is open pop up; earlier ones wait under the bell.
 if(known&&$('notifications-panel').hidden)for(const item of items)if(!item.read&&!known.has(notificationKey(item)))toastNotification(item);
}
function toast(element,tone){
 const region=$('toasts'),wrapper=node('div',undefined,'toast tone-'+tone),close=node('button','×','notification-dismiss');close.type='button';close.setAttribute('aria-label','Close');
 wrapper.append(element,close);region.append(wrapper);while(region.children.length>3)region.firstElementChild.remove();
 let timer;const remove=()=>wrapper.remove(),schedule=()=>{clearTimeout(timer);timer=setTimeout(remove,8000);};
 close.onclick=remove;wrapper.addEventListener('pointerenter',()=>clearTimeout(timer));wrapper.addEventListener('pointerleave',schedule);
 wrapper.addEventListener('focusin',()=>clearTimeout(timer));wrapper.addEventListener('focusout',event=>{if(!wrapper.contains(event.relatedTarget))schedule();});schedule();
 for(const button of wrapper.querySelectorAll('.notification-actions button'))button.addEventListener('click',remove);
}
function toastNotification(item){const element=notificationElement(item,'div');element.querySelector('.notification-dismiss')?.remove();toast(element,notificationContent(item).tone);}
function toastMessage(title,body,tone='info'){const element=node('div',undefined,'notification tone-'+tone),head=node('div',undefined,'notification-head');head.append(node('span',undefined,'notification-icon'),node('h3',title));element.append(head,node('p',body,'notification-body'));toast(element,tone);}
async function generateDescriptions(key){
 const source=state.sources.find(item=>item.key===key);
 try{
  const result=await state.api.source_action('describe',key,null,null);if(result.status==='faulty')throw Error(result.reason);
  if(result.status==='busy')throw Error(result.reason);
  // An open panel already shows the run's live progress row.
  if($('notifications-panel').hidden)toastMessage('Generating descriptions',`${source?.name||key} · runs in the background. Follow progress under the bell or in Settings → Asset sources.`);
 }catch(error){toastMessage('Could not start descriptions',error.message,'fault');}
 await loadSources();
}
async function saveNotification(action,identifier=null){
 const result=await state.api.notification_action(action,identifier);
 if(result.status==='faulty'){toastMessage('Could not update notifications',result.reason,'fault');return;}
 state.notifications=result.notifications;state.notificationKeys=new Set(result.notifications.map(notificationKey));renderNotifications();
}
async function openSourceSettings(key){
 setNotificationsPanel(false);showLibraryView('settings-view');selectSettingsTab('asset-sources');await loadSources();renderSourceSettings();
 // Prefer the description control; a disabled one cannot take focus, so fall back to the source name.
 const controls=[...$('source-list').querySelectorAll('[data-source]')].filter(x=>x.dataset.source===key&&!x.disabled);
 const target=controls.find(x=>['describe','cancel-describe'].includes(x.dataset.action))||controls.find(x=>x.dataset.action==='browse');
 target?.closest('.source-row')?.scrollIntoView({block:'center'});target?.focus({preventScroll:true});
}
async function notificationAction(action,item){
 if(action==='generate'){await generateDescriptions(item.source_key);return;}
 if(action==='view'){if(!item.read)await saveNotification('read',item.id);await openSourceSettings(item.source_key);return;}
 if(action==='dismiss'){const list=[...$('notifications-list').children],index=list.findIndex(el=>el.contains(document.activeElement));await saveNotification('dismiss',item.id);if(index>=0)($('notifications-list').children[index]?.querySelector('button')||$('notifications-title')).focus();}
}
function setNotificationsPanel(open){
 const panel=$('notifications-panel'),wasOpen=!panel.hidden;if(open===wasOpen)return;
 panel.hidden=!open;$('open-notifications').setAttribute('aria-expanded',String(open));
 if(open){state.notificationSignature=null;renderNotifications();for(const t of [...$('toasts').children])t.remove();$('notifications-title').focus();}
 // Closing the panel marks what was shown as read.
 else if(state.notifications.some(item=>!item.read))saveNotification('read_all');
}
$('open-notifications').onclick=()=>setNotificationsPanel($('notifications-panel').hidden);
$('notifications-read-all').onclick=()=>saveNotification('read_all');
document.addEventListener('pointerdown',event=>{if(!$('notifications-panel').hidden&&!event.target.closest('.notifications-anchor')&&!event.target.closest('.toasts'))setNotificationsPanel(false);});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('notifications-panel').hidden){event.preventDefault();event.stopImmediatePropagation();setNotificationsPanel(false);$('open-notifications').focus();}},true);
