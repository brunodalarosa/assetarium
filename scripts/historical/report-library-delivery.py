"""Summarize actual Step 8 receipts; never generates assets or repairs failures."""
from collections import Counter,defaultdict
from contextlib import closing
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_project_config
from local_asset_library.incremental import coverage
from local_asset_library.membership import records
from local_asset_library.catalog import save_json
from local_asset_library.retrieval import index_database
from local_asset_library.publication import generation
config=load_project_config(ROOT)
scope=coverage(config)
if scope['membership']!=883 or generation(config)=='legacy':
    raise RuntimeError('Full approved membership has not been published')
selected=records(config)
stages={stage:dict(Counter(r['processing'].get(stage,'unknown') for r in selected)) for stage in ('inventory','inspection','previews','caption','embeddings')}
if any(stages[s].get('pending',0) for s in stages):raise RuntimeError('Pending stages remain')
quality=Counter();owner=Counter();source_kinds=Counter();caption_reasons=Counter()
for pack in scope['packs'].values():
    quality.update(pack['captions']);owner.update(pack['owner_review'])
for record in selected:
    source_kinds.update(f.get('kind','unknown') for f in (record.get('inspection_run') or {}).get('source_faults',[]))
    if record['processing']['caption']=='failed':
        caption_reasons.update(a.get('error','unclassified generation failure') for a in (record.get('caption_provenance') or {}).get('attempts',[]) if a.get('status')!='valid')
batch_resources={};times=Counter();counts=Counter()
for path in (ROOT/'data/library/batches').glob('*.json'):
    value=json.loads(path.read_text(encoding='utf-8'));stage=value['stage'];times[stage]+=value.get('elapsed_seconds',0);counts[stage]+=1
    resource=value.get('resources',{})
    maxima=batch_resources.setdefault(stage,{})
    for key in ('cuda_peak_allocated_bytes','cuda_peak_reserved_bytes','process_peak_rss_bytes_sampled','rss_bytes'):
        if key in resource:maxima[key]=max(maxima.get(key,0),resource[key])
with closing(index_database(config,readonly=True)) as db:
    vectors=dict(db.execute('SELECT channel,COUNT(*) FROM vectors GROUP BY channel'))
    jobs=[{'channel':c,'status':s,'count':n} for c,s,n in db.execute('SELECT channel,status,COUNT(*) FROM jobs GROUP BY channel,status')]
storage=[]
for path in (ROOT/'data/storage').glob('step8-*.json'):
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('status')=='passed':storage.append({'receipt':path.relative_to(ROOT).as_posix(),'allocated_bytes':value['totals']['allocated_bytes'],'mtime':path.stat().st_mtime})
storage.sort(key=lambda r:r['mtime'])
tests=[]
for path in (ROOT/'data').glob('step8-tests-*.xml'):
    value=ET.parse(path).getroot();suite=value.find('testsuite') if value.tag!='testsuite' else value
    tests.append({'receipt':path.relative_to(ROOT).as_posix(),'tests':int(suite.get('tests',0)),
        'failures':int(suite.get('failures',0)),'errors':int(suite.get('errors',0)),'seconds':float(suite.get('time',0))})
gui=json.loads((ROOT/'data/gui/step8-enlarged-final/report.json').read_text(encoding='utf-8'))
retrieval=json.loads((ROOT/'data/library/verification/step8-enlarged-final/report.json').read_text(encoding='utf-8'))
preservation=json.loads((ROOT/'data/library/verification/step8-preservation-final/report.json').read_text(encoding='utf-8'))
nochange=json.loads((ROOT/'data/library/verification/step8-no-change/report.json').read_text(encoding='utf-8'))
if any(check['status']!='passed' for check in (gui,retrieval,preservation,nochange)):
    raise RuntimeError('A required final verification has not passed; preserve its receipt and resolve the application/check defect')
if retrieval.get('server_exit')!=0 or not retrieval.get('gui_closed'):
    raise RuntimeError('Final retrieval worker lifecycle did not finish cleanly')
operation=ROOT/'data/library/operations/05f20af242f34a5b8a366bda31e1c687'
bulk=json.loads((operation/'result.json').read_text(encoding='utf-8'))
bulk_seconds=(operation/'result.json').stat().st_mtime-(operation/'before.json').stat().st_mtime
final_tests=next(t for t in tests if t['receipt']=='data/step8-tests-final-prepared.xml')
if final_tests['errors'] or final_tests['failures']:
    raise RuntimeError('Final prepared-runtime test suite did not pass')
latency={surface:{'minimum_seconds':min(c[surface+'_seconds'] for c in retrieval['cases']),
                  'maximum_seconds':max(c[surface+'_seconds'] for c in retrieval['cases'])}
         for surface in ('gui','mcp')}
pack_table='\n'.join([
    '| Pack | Assets | Inspected | Valid captions | Caption failures | Complete / partial index | Notes / warnings | Source faults | Owner pending |',
    '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',
    *[f"| {name} | {p['assets']} | {p['stages']['inspection'].get('complete',0)} | {p['stages']['caption'].get('complete',0)} | {p['stages']['caption'].get('failed',0)} | {p['stages']['embeddings'].get('complete',0)} / {p['stages']['embeddings'].get('partial',0)} | {p['captions'].get('review_note',0)} / {p['captions'].get('warning',0)} | {p['source_faults']} | {p['owner_review'].get('pending',0)} |" for name,p in sorted(scope['packs'].items())]
])
report={'stage':8,'date':datetime.now(timezone.utc).isoformat(),'status':'implemented_and_processed_with_preserved_faults',
    'scope':{'membership':883,'packs':8,'generation':generation(config),'subagents':False,'source_edits':False,
        'models_or_dependencies_installed':False,'play_shapes_modified':False,'step9_implemented':False},
    'approval':{'scope':'Bruno: Yes','implementation':'Bruno: Approved','revised_batch_runtime':'Bruno: Yes. Proceed and do not ask more confirmations for this task.',
        'estimated_total_hours':[6,10],'revised_bulk_hours':[4,6],'peak_additional_allocated_bytes':2147483648,'total_allocated_ceiling_bytes':8589934592},
    'coverage':scope,'stages':stages,'vectors':vectors,'vector_jobs':jobs,'caption_quality':dict(quality),'owner_reviews':dict(owner),
    'source_fault_kinds':dict(source_kinds),'caption_failure_reasons':dict(caption_reasons),
    'processing':{'bulk_elapsed_seconds':bulk_seconds,'bulk_receipt':str((operation/'result.json').relative_to(ROOT)),
        'stage_batch_seconds':dict(times),'batch_counts':dict(counts),'resource_peaks':batch_resources,
        'method':'Actual job batch durations; wrapper startup/model loads/verification outside stage timers add elapsed time. Allocator/RSS measurements are process-level.'},
    'storage':{'receipts':storage,'peak_allocated_bytes':max(r['allocated_bytes'] for r in storage),
        'latest_allocated_bytes':storage[-1]['allocated_bytes'],'bulk':bulk['storage'],
        'peak_growth_from_bulk_baseline_bytes':max(r['allocated_bytes'] for r in storage)-bulk['storage']['before_allocated'],
        'method':'Unique allocated project bytes; excludes external originals and shared models'},
    'verification':{'tests':tests,'native_gui':{'status':gui['status'],'receipt':'data/gui/step8-enlarged-final/report.json','checks':gui['checks']},
        'actual_gui_mcp_retrieval':retrieval,'retrieval_latency':latency,'originals_and_pilot':preservation,'no_change':nochange,
        'synthetic_live_publication':'data/gui/step8-live-publication-parity/report.json'},
    'faults_and_limitations':['Caption generation/schema failures were retained with raw attempts; no automatic retry or fabricated caption.',
        'Usable renders/source evidence survive caption failure; source geometry/texture faults remain visible.',
        'New captions await AI/owner visual review; notes/warnings apply only where findings are recorded.',
        'Semantic suggestions can include unrelated candidates; no universal absence detector or ranking fallback.',
        'Physical scale, alternate-format geometry equivalence and binary dependency completeness remain qualified.',
        'Owner relevance, usability, artistic suitability and comprehensive accessibility approval remain separate.',
        'Enlarged keyword queries measured about three seconds; this exceeds the earlier two-second warm-search target. The UI remains available during requests.',
        'Retained test/check failures include invoking image tests in the base runtime without Pillow and an incomplete new interruption-status fixture; the prepared-runtime suite and corrected fixture passed.',
        'Pre-update app/MCP connections must restart to use the new membership/publication/worker behavior.']}
save_json(ROOT/'docs/step8-verification.json',report)
summary=f"""\n## Step 8 — reliable updates and expanded backend/GUI (October 12, 2026)\n\nBruno approved the eight-pack, 883-asset scope and implementation/storage plan,\nthen approved the corrected 4–6-hour batch estimate and requested completion\nwithout further confirmation. The earlier 1.5–3-hour batch estimate was an\narithmetic error; no bulk processing began before its correction/approval.\nNo subagents, original-pack/Play Shapes edits, dependency/model installation,\nclient-registration changes, optional classification or clustering were performed.\n\nImplemented explicit bounded membership, persistent stage/vector checkpoints,\ninput-specific invalidation, isolated faults, deletion/rename identity rules,\npreserved owner overlays and immutable transactional catalog/index generations.\nThe original forty-asset pilot results/evidence remain preserved. GUI browsing\nis paged to forty cards, thumbnails load near the viewport with three-request\nconcurrency, and selection/filters/keyboard access survive updates. Opening\nremains lightweight. Manual scan/process/refresh/status and dry runs are\ndocumented in docs/library-updates.md; current contract is\ndocs/library-membership.json. GPU leases coordinate owned workers; models unload\nfor queued peers/batches, while browse/keyword/detail remain available.\n\nActual membership: **883 assets, eight packs**. Stage coverage: `{json.dumps(stages)}`.\nVectors: `{json.dumps(vectors)}`. Caption quality: `{json.dumps(dict(quality))}`.\nOwner states: `{json.dumps(dict(owner))}`. Per-pack/stage counts, usable partial\nresults, source faults, pending AI reviews, caption notes/warnings and failures\nare separately recorded in docs/step8-verification.json. Failed captions retain\nraw canonical attempts and reasons; none were retried or manufactured.\n\nActual stage batch durations (seconds): `{json.dumps(dict(times))}`. These exclude\nsome wrapper/model-load, status, storage and publication overhead. Before/after\nand per-batch fresh base-Python receipts are under data/storage/step8-*.json.\nPeak measured project allocation: **{max(r['allocated_bytes'] for r in storage)/1024**3:.3f} GiB**;\nlatest: **{storage[-1]['allocated_bytes']/1024**3:.3f} GiB**, excluding external\noriginals/shared weights, below the approved 8 GiB full-library ceiling.\n\nVerification: synthetic source/dependency changes, deletions, renames, metadata\nand vector corruption, interruption/resume, owner overlays, measured-filter\nboundaries and input/contract changes. Native 316-asset fixtures checked lazy\npages, detail, keyboard handlers, resizing and a live STDIO/GUI publication\nupdate. Enlarged real GUI and all-mode actual GUI/MCP checks: **{gui['status']} /\n{retrieval['status']}**. Full original SHA-256/size/mtime and protected pilot\nfield/image checks: **{preservation['status']}**, {preservation['original_source_entries']}\nsource entries. No-change processing/publication: **{nochange['status']}**, no\nrender/caption/embedding inference. Test receipt counts overlap and are not\nadded as distinct tests. Exact receipts and remaining limits are versioned in\ndocs/step8-verification.json.\n\nApplication/check faults were corrected with their original receipts retained:\nnative GUI membership lookup and narrow-header overflow; stable SQLite content\ncomparison for no-change publication; Windows native-library initialization\nbefore the worker input thread; and Windows manifest file-sharing races. These\nwere application/test defects, not retries/repairs of faulty original assets.\nNo owner caption/artistic/usability/accessibility approval is granted by these\ntechnical checks. Reopen the app/restart pre-update MCP connections. Checked\nlocal commit only; no push. Step 9 remains optional and unimplemented.\n"""
summary += f"\n{pack_table}\n\nBulk coordinator elapsed: **{bulk_seconds/3600:.2f} hours**, within the revised\n4–6-hour processing estimate. Measured final query ranges, including startup and\nGPU handoffs: `{json.dumps(latency)}`. Native next-page time was\n**{gui['page_seconds']:.3f} seconds**; the window remained available during search.\nThe older two-second warm-search target is not met by these enlarged queries.\nOriginal failed application/test receipts remain retained, including the base\nruntime without Pillow and an incomplete interruption-status fixture. The\nprepared-runtime suite passed {final_tests['tests']} tests, and the corrected\ninterruption-status subset passed separately.\n"
with (ROOT/'docs/progress.md').open('a',encoding='utf-8') as stream:stream.write(summary)
print(json.dumps({'membership':883,'stages':stages,'vectors':vectors,'latest_allocated_gib':storage[-1]['allocated_bytes']/1024**3}))
