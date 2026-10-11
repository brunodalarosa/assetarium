"""Publish rank-blind, model-generated judgments from manually inspected preview sheets.

No caption or retrieval-result inputs. Run once before benchmark; never overwrite a freeze.
"""
from pathlib import Path
from datetime import datetime, timezone
import html
import json

from local_asset_library.catalog import save_json
from local_asset_library.captions import file_hash
from local_asset_library.config import load_config
from local_asset_library.retrieval import pilot_records

root = Path(__file__).resolve().parents[1]
freeze = root / 'docs/evaluation/freeze.json'
if freeze.exists():
    raise SystemExit('Already frozen; do not relabel after viewing rankings')
config = load_config(root / 'config.example.toml', root)
spec = json.loads((root / 'docs/evaluation/queries.json').read_text())
records = pilot_records(config)
assert len(records) == 40
# Numbers are the stable pilot manifest order, as displayed on the five inspected sheets.
# grade 3 = directly satisfies; 2 = useful but qualified; 1 = weak/partial; 0 = irrelevant.
judgments = {
    'E01': {2:3}, 'E02': {3:3}, 'E03': {14:3}, 'E04': {8:3},
    'E05': {20:3}, 'E06': {35:3}, 'E07': {30:3}, 'E08': {38:3},
    'N01': {3:3}, 'N02': {4:3}, 'N03': {10:3}, 'N04': {12:3,11:1,26:1,27:1},
    'N05': {18:3,35:3}, 'N06': {34:3,20:2}, 'N07': {25:3,9:1}, 'N08': {19:3,33:3},
    'S01': {17:3,16:1,31:1,32:1}, 'S02': {14:3,13:1,28:1},
    'S03': {40:2,23:1}, 'S04': {38:2,36:1,37:1}, 'S05': {21:3,22:3,39:3},
    'S06': {3:3,4:2,1:2,2:2}, 'F01': {17:3}, 'F02': {26:3},
    'F03': {10:3}, 'F04': {33:3},
    'Z01': {}, 'Z02': {}, 'Z03': {}, 'Z04': {}, 'Z05': {}, 'Z06': {},
    'R01': {4:3,1:1,2:1,3:1}, 'R02': {14:3,13:2,28:2},
    'R03': {38:3,36:2,37:2,21:1,22:1,39:1}, 'R04': {32:3,31:2,16:1,17:1},
}
notes = {
    'N06': 'Quaternius fridge has clear upper/lower doors; Kenney fridge has stacked handles but door separation is less clear.',
    'S02': 'Only the double-cheese view visibly has two yellow cheese layers; other burgers are partial matches.',
    'S03': 'Mossy rock visibly has green patches but appears gray, not clearly brown: qualified grade 2, requires owner review.',
    'S04': 'Snow tree has white caps over green leafy clusters, not an entirely white canopy: qualified grade 2, requires owner review.',
    'S06': 'Broad style request permits several wheeled vehicles; emergency van most directly boxy.',
    'R01': 'Cross-view tractor identity has a target; no other pilot asset judged usefully similar (grade >=2).',
    'R02': 'Other burgers are useful similar assets; not the exact double-cheese construction.',
    'R03': 'Other birches share crown/trunk geometry; season/colors differ.',
    'R04': 'Other Quaternius chair shares wooden slatted back, differs in cushion/color.',
}
assets = [{'asset_id': r['asset_id'], 'alias': r['pack_id']+'/'+r['display_name'],
           'name': r['display_name'], 'pack': r['pack_id'],
           'formats': sorted({f['format'] for f in r['files']}),
           'preview': next(p['path'] for p in r['previews'] if p.get('origin')=='rendered' and p['view_label']=='three_quarter')}
          for r in records]
labels = {'version': spec['version'], 'status': 'provisional_model_generated', 'owner_review': 'pending',
          'author': 'Codex visual judgments; not Bruno',
          'ground_truth': 'Inspected actual three-quarter/side preview sheets, source identities and verified format metadata; captions and competing rankings not read for labeling.',
          'limitations': 'Prior step 5 demonstrations were seen. Query held-out subset is frozen, never used for tuning; these are not unseen assets. Negative absence is limited to 40 assets.',
          'grade_definition': {'0':'irrelevant', '1':'weak/partial', '2':'useful qualified match', '3':'direct match'},
          'complete_pool': [a['asset_id'] for a in assets], 'assets': assets, 'queries': {}}
for q in spec['queries'] + spec['references']:
    labels['queries'][q['id']] = {
        'grades': {r['asset_id']: judgments[q['id']].get(i+1,0) for i,r in enumerate(records)},
        'basis': notes.get(q['id'], 'Direct preview geometry/color evidence plus source identity for exact-name requests; all other pilot items assessed irrelevant.'),
        'review': 'pending'}
save_json(root/'docs/evaluation/labels-provisional.json', labels)
# Establish the natural-language gate subset before any comparative rankings.
protocol_path = root/'docs/evaluation/protocol.json'
protocol = json.loads(protocol_path.read_text())
protocol['natural_language_gate_ids'] = [q['id'] for q in spec['queries'] if q['category'] in {'natural','shape_color_style_variant','filter_natural'}]
assert len(protocol['natural_language_gate_ids']) == 17
save_json(protocol_path, protocol)

# Rank-blind review: labels and deliberate distractors, always original manifest order.
# Owner can reveal all 40 candidates to correct model omissions; no retrieval scores/order.
review = config.output_path('data','evaluation/relevance-review.html')
sections = []
for q in spec['queries'] + spec['references']:
    entry = labels['queries'][q['id']]
    positive = {i for i,g in enumerate(entry['grades'].values()) if g > 0}
    pool = positive | {0,9,16,25,32,39}
    cards = []
    for i,a in enumerate(assets):
        grade = entry['grades'][a['asset_id']]
        options = ''.join(f'<option value="{g}" {"selected" if grade==g else ""}>{g}</option>' for g in range(4))
        cards.append(f'<label class="card {"extra" if i not in pool else ""}"><img loading="lazy" src="../../{html.escape(a["preview"])}"><span>{html.escape(a["alias"])}</span><small>{html.escape(", ".join(a["formats"]))}</small><select data-query="{q["id"]}" data-asset="{a["asset_id"]}">{options}</select></label>')
    title = q.get('text', 'Reference crop: '+q.get('asset',''))
    reference = f'<img class="reference" src="references/{q["id"]}.png">' if q['id'].startswith('R') else ''
    sections.append(f'<section id="{q["id"]}"><h2>{q["id"]} — {html.escape(title)}</h2><p>{q["split"]}; {html.escape(entry["basis"])}</p>{reference}<label><input type="checkbox" data-reviewed="{q["id"]}"> I reviewed relevance for this query, including possible omissions.</label><button onclick="this.closest(\'section\').classList.toggle(\'all\')">Show/hide all 40 assets</button><div class="grid">{"".join(cards)}</div></section>')
payload = json.dumps(labels).replace('</','<\\/')
review.write_text('''<!doctype html><html><meta charset="utf-8"><title>Pilot relevance review — pending Bruno</title><style>
body{font:16px system-ui;max-width:1250px;margin:30px auto;background:#f5f5f5;color:#222}header{background:white;padding:20px}section{margin:24px 0;padding:20px;background:white}.grid{display:flex;flex-wrap:wrap;gap:8px}.card{width:165px;border:1px solid #ccc;padding:6px;display:flex;flex-direction:column}.card img{width:160px;height:150px;object-fit:contain;background:#555}.card span{overflow-wrap:anywhere}.card small{color:#555}.extra{display:none}.all .extra{display:flex}button,select{padding:8px;margin:8px}.reference{width:180px;background:#555}
</style><header><h1>Rank-blind relevance review</h1><p>Provisional labels generated by Codex from actual views, source names and formats. No competing rankings or scores appear here. Bruno has not approved these labels.</p><p>Grades: 0 irrelevant; 1 weak/partial; 2 useful qualified match; 3 direct match. Check each query after reviewing. Use all 40 candidates when the shortlist misses a relevant item. Negatives should remain all zero only if absent from this pilot. Reference crops require separate same-asset versus other-asset judgment. Saving does not approve step 7.</p><button onclick="exportLabels()">Export reviewed labels</button><p id="status"></p></header>'''+''.join(sections)+'''<script>
const labels = '''+payload+''';
function exportLabels(){for(const el of document.querySelectorAll('select'))labels.queries[el.dataset.query].grades[el.dataset.asset]=Number(el.value);
let count=0;for(const el of document.querySelectorAll('[data-reviewed]')){labels.queries[el.dataset.reviewed].review=el.checked?'owner_reviewed':'pending';if(el.checked)count++;}
labels.owner_review=count===36?'reviewed':'partial';labels.status=count===36?'owner_reviewed':'provisional_with_partial_owner_review';labels.author='Bruno review of Codex provisional labels';labels.exported_at=new Date().toISOString();
document.getElementById('status').textContent=count+'/36 queries reviewed. Export this file as data/evaluation/owner-labels.json; request recomputation before a quality verdict.';
const blob=new Blob([JSON.stringify(labels,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='owner-labels.json';a.click();URL.revokeObjectURL(a.href);}
</script></html>''',encoding='utf-8')
paths = ['docs/evaluation/protocol.json','docs/evaluation/queries.json','docs/evaluation/labels-provisional.json',
         'data/evaluation/prelabel/image-evidence.json','data/evaluation/references/manifest.json','data/evaluation/relevance-review.html']
save_json(freeze, {'version':spec['version'],'frozen_at':datetime.now(timezone.utc).isoformat(),
                  'before_competing_rankings':True,'owner_review':'pending',
                  'files':{p:file_hash(root/p) for p in paths}})
print(json.dumps({'freeze':str(freeze),'review':str(review),'queries':36,'owner_review':'pending'}))
