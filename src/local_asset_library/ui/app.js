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
function captionBadge(item){if(item.caption_faulty)return node('span','Caption fault','badge fault caption-quality-badge');if(item.caption_status==='warning')return node('span','Caption warning','badge warning caption-quality-badge');return null;}
function cardLabel(item){return `${item.name}, ${packName(item.pack)}${item.source_faulty ? ', source fault' : ''}${item.caption_faulty ? ', caption fault' : item.caption_status==='warning' ? ', caption warning' : ''}`;}
function refreshCaptionBadge(card,item,info){const latest={...item,...info};card.button.querySelector('.caption-quality-badge')?.remove();const flag=captionBadge(latest);if(flag)card.button.querySelector('.badges').append(flag);card.button.setAttribute('aria-label',cardLabel(latest));}
function badges(item){const el=node('div',undefined,'badges');if(item.source_faulty)el.append(node('span','Source fault','badge fault'));const caption=captionBadge(item);if(caption)el.append(caption);if(item.caption_owner_review!=='approved')el.append(node('span','Review '+(item.caption_owner_review||'pending'),'badge review'));return el;}
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
  else{const reason=payload.preview?.reason||payload.reason||result.reason||'Requested three-quarter preview unavailable';const placeholder=node('span','Preview unavailable','placeholder');placeholder.title=reason;placeholder.setAttribute('aria-label','Preview unavailable: '+reason);card.thumb.append(placeholder);const accessibleReason=node('span',reason,'sr');accessibleReason.id=(collection===state?'':'source-')+'preview-fault-'+item.asset_id;card.button.append(accessibleReason);card.button.setAttribute('aria-describedby',accessibleReason.id);card.button.querySelector('.badges').append(node('span','Preview fault','badge fault'));}
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
 const observations=section('Generated visual observations');observations.append(node('p','Provisional observations, separate from measured facts.','hint'));if(info.observations){observations.append(node('p',info.observations.description||display(info.observations)),rawDetails('Structured observations',info.observations));}else observations.append(node('p','No usable observation description.'));body.append(observations);
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
window.addEventListener('pywebviewready',async()=>{state.api=window.pywebview.api;try{state.context=await state.api.context();if(state.context.status==='faulty')throw Error(state.context.reason);$('scope').textContent=`Approved ${state.context.pilot_count}-asset library`;$('inventory').textContent=`${state.context.inventory_count} inventory records · ${state.context.generation}`;addOptions($('pack'),state.context.packs,packName);addOptions($('format'),state.context.formats,x=>x.toUpperCase());$('version').textContent=`Catalog ${state.context.versions.catalog.slice(0,10)} · index ${state.context.versions.index.slice(0,10)}`;$('version').title=JSON.stringify(state.context.versions,null,2);await browse();await refreshContext();await loadSources();if(state.context.managed_sources)await sourceAction('scan');$('query').focus();}catch(error){fail(error.message);status('Startup data is faulty. No model loading or fallback attempted.');$('grid').setAttribute('aria-busy','false');}});

const paging=node('nav',undefined,'paging');paging.setAttribute('aria-label','Asset pages');
for(const [id,label] of [['previous-page','Previous page'],['page-info',''],['next-page','Next page']]){const element=node(id==='page-info'?'span':'button',label);element.id=id;if(element.tagName==='BUTTON')element.type='button';paging.append(element);}$('grid').before(paging);
$('previous-page').onclick=()=>{state.offset=Math.max(0,state.offset-40);browse(false);};$('next-page').onclick=()=>{state.offset+=40;browse(false);};
const operations=node('div',undefined,'library-operations');
for(const [label,operation,dry] of [['Scan','scan',false],['Status','status',false]]){const button=node('button',label);button.type='button';button.onclick=async()=>{if(operation==='scan'&&state.context?.managed_sources){await sourceAction('scan');return;}const result=await state.api.operation(operation,dry);if(result.status==='faulty')fail(result.reason);else if(operation==='status'){await refreshContext();status('Processing and published coverage updated.');}else status(`${label} started. Evidence: ${result.evidence}`);};operations.append(button);}
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
  const source=context.working_coverage||context.coverage,coverage=Object.values(source.packs);
  const pending=coverage.reduce((n,p)=>n+(p.stages.caption.pending||0),0),failed=coverage.reduce((n,p)=>n+(p.stages.caption.failed||0),0);
  $('coverage').textContent=`${context.coverage.membership} in the library · ${pending} descriptions pending · ${failed} description failures`;
 }catch(error){fail(error.message);}
}
const coverageLine=node('p',undefined,'hint');coverageLine.id='coverage';operations.after(coverageLine);setInterval(()=>refreshContext(),20000);


const sourceCards=new Map();state.sources=[];state.sourcesRevision=null;state.loadingSources=false;
function operationActive(operation){return ['queued','scanning','processing','publishing','cancelling','verifying'].includes(operation?.status);}
function sourceMessage(source){if(source.scan_fault)return source.scan_fault;if(!source.scanned)return 'Waiting for the source scan. Assets must be processed before they appear in searches.';if(source.needs_processing)return `${source.pending||0} ${(source.pending||0)===1?'asset needs':'assets need'} processing or publication.`;if(source.failed)return 'Import finished. Recorded failures are listed in the importing failures report.';return 'Up to date and published.';}
function renderSourceWarnings(){
 const shown=new Set();
 for(const source of state.sources){
  const operation=source.operation||{},active=operationActive(operation);
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
  card.process.disabled=active||!source.enabled;card.process.title=source.enabled?'':'Enable this source in Settings before processing';
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
  const label=node('label',undefined,'source-enabled'),checkbox=node('input');checkbox.type='checkbox';checkbox.checked=source.enabled;checkbox.dataset.source=source.key;checkbox.dataset.action='enabled';checkbox.setAttribute('aria-label','Enable '+source.name);
  checkbox.onchange=()=>sourceAction('enabled',source.key,null,checkbox.checked);label.append(checkbox,document.createTextNode('Enabled'));
  const remove=node('button','Remove');remove.type='button';remove.dataset.source=source.key;remove.dataset.action='remove';remove.disabled=operationActive(source.operation);remove.onclick=()=>sourceAction('remove',source.key);
  controls.append(label,remove);row.append(info,controls);$('source-list').append(row);
 }
 if(focusKey&&focusAction)[...$('source-list').querySelectorAll('[data-source]')].find(x=>x.dataset.source===focusKey&&x.dataset.action===focusAction)?.focus();
}
async function loadSources(){
 if(!state.api||state.loadingSources)return;state.loadingSources=true;
 try{
  const result=await state.api.sources();if(result.status==='faulty')throw Error(result.reason);
  state.sources=result.sources||[];renderSourceWarnings();
  const changed=state.sourcesRevision!==result.revision;state.sourcesRevision=result.revision;
  if(!$('settings-view').hidden)renderSourceSettings();
  if(!$('import-failures-view').hidden&&changed)await loadImportFailures();
  if(changed&&state.context&&result.revision!==state.context.sources_revision)await refreshContext();
 }catch(error){$('sources-message').textContent=error.message;}finally{state.loadingSources=false;}
}
async function sourceAction(action,key=null,directory=null,enabled=null){
 ++state.generation;searchBusy(null);++state.detailGeneration;
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
 showLibraryView('settings-view');await loadSources();renderSourceSettings();
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
$('open-settings').onclick=async()=>{showLibraryView('settings-view');$('settings-title').focus();await loadSources();};
$('close-settings').onclick=async()=>{showLibraryView('library-view');await loadSources();$('open-settings').focus();};
$('choose-source').onclick=async()=>{const result=await state.api.choose_source_directory();if(result.status==='selected')$('source-directory').value=result.directory;else if(result.status==='faulty')$('sources-message').textContent=result.reason;};
$('add-source').onclick=()=>{const directory=$('source-directory').value.trim();if(directory)sourceAction('add',null,directory);else $('sources-message').textContent='Choose an asset directory first.';};
setInterval(loadSources,1500);
