"""Collection exports: JSON for agents, a PNG sample sheet, Markdown and a printable report.

Exports read the library and write only the file(s) the owner chose; originals stay
where they are and are referenced by absolute path. Members whose files cannot be
resolved are exported with their fault instead of being dropped or guessed.
"""
import base64
from datetime import datetime, timezone
import html
from io import BytesIO
import json
from pathlib import Path
import re

from .config import ConfigError

KINDS = {'json': ('.json', 'JSON file (*.json)'), 'png': ('.png', 'PNG image (*.png)'),
         'md': ('.md', 'Markdown file (*.md)'), 'pdf': ('.pdf', 'PDF document (*.pdf)')}
VISUAL = {'model_3d', 'image'}
TYPE_NAMES = {'model_3d': '3D model', 'image': '2D image', 'audio': 'Audio'}


def default_directory(config):
    return config.storage_root('data') / 'exports/collections'


def file_name(name):
    """A Windows-safe file stem from a collection name."""
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name).strip(' .') or 'Collection'
    return stem[:80]


def member_config(config, entry):
    if entry['in_library']:
        return config
    from .sources import bound, get_source
    return bound(config, get_source(config, entry['source_key']))


def files(config, entry):
    """Absolute source paths for one member, or the reason they are unavailable."""
    if entry['availability'] == 'unavailable':
        return {'status': 'unavailable', 'reason': entry.get('reason')}
    from .retrieval import observations, resolved_detail
    try:
        scoped = member_config(config, entry)
        result = resolved_detail(scoped, entry['asset_id'])
        record = result['record']
        description = observations(scoped, record) or {}
        technical = record.get('technical') or {}
    except (OSError, ValueError) as exc:
        return {'status': 'faulty', 'reason': str(exc)[:400]}
    measured = {k: technical.get(k) for k in ('width', 'height', 'format') if technical.get(k) is not None}
    triangles = (technical.get('evaluated_instance_totals') or {}).get('triangles')
    if triangles is not None:
        measured['triangles'] = triangles
    return {'status': 'available', 'selected_source': result['selected_source']['resolved_path'],
            'selected_format': result['selected_source']['format'],
            'alternates': [{'format': f['format'], 'path': str(scoped.source_file(f['path']))} for f in record['files']
                           if f['path'] != result['selected_source']['path']],
            'dependencies': [{'path': d.get('resolved_path'), 'status': d.get('status'), **({'fault': d['fault']} if d.get('fault') else {})}
                             for d in result['dependencies']],
            'texture_overrides': [{'image': o.get('image'), 'path': o['resolved_path']} for o in result.get('texture_overrides', [])],
            'measured': measured,
            'description': {k: description.get(k) for k in ('identity', 'description') if description.get(k)}}


def package(config, value):
    """The JSON export: the collection and, per member, everything an agent needs to use it."""
    members = []
    for position, entry in enumerate(value['items'], 1):
        members.append({'position': position, 'asset_id': entry['asset_id'], 'name': entry['name'],
                        'asset_type': entry['asset_type'], 'label': entry['label'], 'notes': entry['notes'],
                        'tags': entry['tags'], 'source': {'key': entry['source_key'], 'name': entry['source_name']},
                        'formats': entry.get('formats', []), 'availability': entry['availability'],
                        **({'reason': entry['reason']} if entry.get('reason') else {}),
                        'files': files(config, entry)})
    return {'schema_version': 1, 'kind': 'assetarium_collection',
            'meaning': ('A collection is an owner-organized bundle of assets, not an asset. Labels and notes belong to this '
                        'collection; files stay at their original paths and are referenced, never copied.'),
            'collection_id': value['collection_id'], 'name': value['name'], 'description': value['description'],
            'updated_at': value['updated_at'], 'exported_at': datetime.now(timezone.utc).isoformat(),
            'asset_count': len(members), 'members': members}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def font(size, bold=False):
    from PIL import ImageFont
    for name in (('segoeuib.ttf', 'arialbd.ttf') if bold else ('segoeui.ttf', 'arial.ttf')):
        candidate = Path('C:/Windows/Fonts') / name
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size)


def fitted(draw, text, typeface, width):
    if draw.textlength(text, font=typeface) <= width:
        return text
    while text and draw.textlength(text + '…', font=typeface) > width:
        text = text[:-1]
    return text + '…'


def wrapped(draw, text, typeface, width, lines):
    words, result, line = text.split(), [], ''
    for word in words:
        trial = (line + ' ' + word).strip()
        if draw.textlength(trial, font=typeface) <= width:
            line = trial
            continue
        result.append(line)
        line = word
        if len(result) == lines:
            break
    if len(result) < lines and line:
        result.append(line)
    if len(result) == lines and ' '.join(result) != ' '.join(words):
        result[-1] = fitted(draw, result[-1] + ' …', typeface, width)
    return [r for r in result if r]


def sample_sheet(value, thumbnails):
    """A PNG grid of visual members with names and labels; non-visual members are counted below."""
    from PIL import Image, ImageDraw
    visual = [e for e in value['items'] if e['asset_type'] in VISUAL]
    skipped = len(value['items']) - len(visual)
    columns = max(1, min(4, len(visual)))
    tile, thumb_height, text_height, gap, margin = 300, 194, 66, 20, 40
    rows = (len(visual) + columns - 1) // columns
    width = max(margin * 2 + columns * tile + (columns - 1) * gap, 760)
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    title, body, small, label_font = font(30, True), font(15), font(13), font(13, True)
    description = wrapped(probe, value['description'], body, width - 2 * margin, 2) if value['description'] else []
    header = 70 + 22 * len(description) + 56
    footer = 46
    height = header + rows * (thumb_height + text_height) + max(0, rows - 1) * gap + footer + (24 if not visual else 0)
    sheet = Image.new('RGB', (width, height), '#f8fafc')
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 32), fitted(draw, value['name'], title, width - 2 * margin), font=title, fill='#0f172a')
    y = 78
    for line in description:
        draw.text((margin, y), line, font=body, fill='#475569')
        y += 22
    draw.text((margin, y + 6), f"{len(value['items'])} assets · exported {datetime.now().strftime('%B %d, %Y')} from Assetarium",
              font=small, fill='#64748b')
    for index, entry in enumerate(visual):
        x = margin + (index % columns) * (tile + gap)
        top = header + (index // columns) * (thumb_height + text_height + gap)
        draw.rounded_rectangle((x, top, x + tile, top + thumb_height + text_height), 14, fill='#ffffff', outline='#e2e8f0')
        draw.rounded_rectangle((x + 8, top + 8, x + tile - 8, top + thumb_height), 10, fill='#eef2f6')
        blob = thumbnails.get(entry['asset_id'])
        if blob:
            with Image.open(BytesIO(blob)) as source:
                image = source.convert('RGBA')
                # Fill the tile: small previews grow with hard edges, large ones shrink smoothly.
                scale = min((tile - 24) / image.width, (thumb_height - 16) / image.height)
                image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                                     Image.Resampling.NEAREST if scale >= 2 else Image.Resampling.LANCZOS)
                sheet.paste(image, (x + (tile - image.width) // 2, top + 8 + (thumb_height - 8 - image.height) // 2), image)
        else:
            reason = 'Unavailable' if entry['availability'] == 'unavailable' else 'Preview unavailable'
            draw.text((x + tile // 2, top + thumb_height // 2), reason, font=small, fill='#94a3b8', anchor='mm')
        draw.text((x + 14, top + thumb_height + 12), fitted(draw, entry['name'], label_font, tile - 28), font=label_font, fill='#0f172a')
        second = entry['label'] or entry['source_name'] or ''
        draw.text((x + 14, top + thumb_height + 34), fitted(draw, second, small, tile - 28), font=small,
                  fill='#4f46e5' if entry['label'] else '#64748b')
    note = (f'{skipped} non-visual asset(s) (such as audio) are listed in the JSON and Markdown exports.' if skipped else
            'Labels shown in color; unlabeled assets show their source.')
    if not visual:
        note = 'This collection has no visual assets. ' + note
    draw.text((margin, height - 32), note, font=small, fill='#64748b')
    stream = BytesIO()
    sheet.save(stream, format='PNG', optimize=True)
    return stream.getvalue()


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.casefold()).strip('-')[:40] or 'asset'


def markdown(value, data, thumbnails, folder_name):
    """Markdown with relative image links; thumbnails are written beside it by the caller."""
    lines = [f"# {value['name']}", '']
    if value['description']:
        lines += [value['description'], '']
    lines += [f"_{len(value['items'])} assets · exported {datetime.now().strftime('%B %d, %Y')} from Assetarium. "
              'Files stay at their original locations; paths below point to them._', '']
    if value['items']:
        lines += ['| # | Asset | Label | Type | Source |', '|---|---|---|---|---|']
        for index, entry in enumerate(value['items'], 1):
            cell = lambda text: (text or '—').replace('|', '\\|').replace('\n', ' ')
            lines.append(f"| {index} | {cell(entry['name'])} | {cell(entry['label'])} | {TYPE_NAMES.get(entry['asset_type'], entry['asset_type'] or '—')} | {cell(entry['source_name'])} |")
        lines.append('')
    images = {}
    for index, (entry, member) in enumerate(zip(value['items'], data['members']), 1):
        heading = f"{entry['label']} — {entry['name']}" if entry['label'] else entry['name']
        lines += [f'## {index}. {heading}', '']
        if thumbnails.get(entry['asset_id']):
            image = f"{index:02}-{slug(entry['name'])}.png"
            images[image] = thumbnails[entry['asset_id']]
            lines += [f"![{entry['name']}](<{folder_name}/{image}>)", '']
        facts = [('Label', entry['label'] or '—'), ('Tags', ', '.join(entry['tags']) or '—'),
                 ('Type', TYPE_NAMES.get(entry['asset_type'], entry['asset_type'] or 'Unknown') +
                  (' · ' + ', '.join(entry.get('formats', [])) if entry.get('formats') else '')),
                 ('Source', entry['source_name'] or '—')]
        found = member['files']
        if found['status'] == 'available':
            facts.append(('File', f"`{found['selected_source']}`"))
            if found['measured']:
                facts.append(('Measured', ', '.join(f'{k} {v}' for k, v in found['measured'].items())))
        else:
            facts.append(('Availability', f"{found['status']} — {found.get('reason') or 'no reason recorded'}"))
        facts.append(('Asset ID', f"`{entry['asset_id']}`"))
        lines += [f'- **{k}:** {v}' for k, v in facts] + ['']
        if entry['notes']:
            lines += ['**Notes**', ''] + ['> ' + line if line else '>' for line in entry['notes'].split('\n')] + ['']
    return '\n'.join(lines).rstrip() + '\n', images


def report_html(value, data, thumbnails):
    """Printable report rendered by the app's own WebView2; every value is escaped."""
    e = lambda text: html.escape(str(text or ''))
    cards = []
    for index, (entry, member) in enumerate(zip(value['items'], data['members']), 1):
        blob = thumbnails.get(entry['asset_id'])
        image = (f'<img src="data:image/png;base64,{base64.b64encode(blob).decode("ascii")}" alt="">' if blob else
                 f'<span class="none">{"Unavailable" if entry["availability"] == "unavailable" else "No preview"}</span>')
        found = member['files']
        path = (f'<p class="path">{e(found["selected_source"])}</p>' if found['status'] == 'available' else
                f'<p class="fault">{e(found["status"].capitalize())}: {e(found.get("reason"))}</p>')
        tags = ''.join(f'<span class="tag">{e(t)}</span>' for t in entry['tags'])
        notes = f'<p class="notes">{e(entry["notes"])}</p>' if entry['notes'] else ''
        label = f'<span class="label">{e(entry["label"])}</span>' if entry['label'] else ''
        kind = TYPE_NAMES.get(entry['asset_type'], entry['asset_type'] or '')
        cards.append(f'<article><div class="thumb">{image}</div><div class="body"><p class="index">{index:02}</p>'
                     f'<h2>{e(entry["name"])}</h2>{label}<p class="meta">{e(kind)} · {e(entry["source_name"])}</p>'
                     f'{tags and f"<p class=tags>{tags}</p>"}{notes}{path}</div></article>')
    style = ('@page{size:A4;margin:14mm}#print-report{font:12px/1.45 "Segoe UI",system-ui,sans-serif;color:#0f172a}'
             '#print-report header{border-bottom:1px solid #e2e8f0;padding-bottom:12px;margin-bottom:14px}'
             '#print-report h1{font-size:26px;margin:0 0 6px}#print-report .lead{color:#475569;margin:0 0 6px;white-space:pre-wrap}'
             '#print-report .stamp{color:#64748b;font-size:11px;margin:0}'
             '#print-report article{display:flex;gap:14px;padding:10px 0;border-bottom:1px solid #eef2f6;break-inside:avoid}'
             '#print-report .thumb{flex:0 0 150px;height:97px;border-radius:8px;background:#eef2f6;display:flex;align-items:center;justify-content:center;overflow:hidden}'
             '#print-report .thumb img{max-width:100%;max-height:100%;object-fit:contain}#print-report .none{color:#94a3b8;font-size:11px}'
             '#print-report .body{min-width:0;flex:1}#print-report .index{color:#94a3b8;font-size:10px;margin:0}'
             '#print-report h2{font-size:14px;margin:0 6px 2px 0;display:inline}'
             '#print-report .label{display:inline-block;background:#eef2ff;color:#4338ca;border-radius:4px;padding:0 6px;font-size:11px;font-weight:600}'
             '#print-report .meta{color:#64748b;margin:2px 0}#print-report .tag{display:inline-block;background:#f1f5f9;color:#475569;border-radius:4px;padding:0 5px;margin:0 4px 0 0;font-size:10.5px}'
             '#print-report .tags{margin:3px 0}#print-report .notes{white-space:pre-wrap;margin:4px 0;border-left:2px solid #c7d2fe;padding-left:8px}'
             '#print-report .path{font:10px/1.3 Consolas,monospace;color:#475569;word-break:break-all;margin:4px 0 0}'
             '#print-report .fault{color:#b91c1c;margin:4px 0 0}')
    stamp = f"{len(value['items'])} assets · exported {datetime.now().strftime('%B %d, %Y')} from Assetarium · files stay at their original locations"
    body = ''.join(cards) or '<p class="lead">This collection has no assets yet.</p>'
    lead = f'<p class="lead">{e(value["description"])}</p>' if value['description'] else ''
    return (f'<style>{style}</style><div id="print-report"><header><h1>{e(value["name"])}</h1>{lead}'
            f'<p class="stamp">{e(stamp)}</p></header>{body}</div>')


def checked_target(config, target, kind):
    """Scripted exports (verification) may only write under data/exports; dialogs choose freely."""
    root = (config.storage_root('data') / 'exports').resolve()
    path = Path(target).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != KINDS[kind][0]:
        raise ConfigError('Scripted exports must write a ' + KINDS[kind][0] + ' file under data/exports')
    return path


def member_thumbnails(value, read):
    """Verified card images of visual members; a member without one is exported without a picture."""
    thumbnails = {}
    for entry in value['items']:
        if entry['asset_type'] not in VISUAL or entry['availability'] == 'unavailable':
            continue
        try:
            result = read(entry)
            if result.get('image'):
                thumbnails[entry['asset_id']] = base64.b64decode(result['image'])
        except (OSError, ValueError):
            pass  # Its availability says why.
    return thumbnails


def write_export(config, collection_id, kind, path, read_thumbnail):
    """Write a JSON, PNG or Markdown export (shared by the desktop app and the CLI)."""
    from .asset_collections import detail
    if kind not in {'json', 'png', 'md'}:
        raise ConfigError('Unknown export kind')
    value = detail(config, collection_id)
    thumbnails = {} if kind == 'json' else member_thumbnails(value, read_thumbnail)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = [path]
    if kind == 'png':
        path.write_bytes(sample_sheet(value, thumbnails))
    else:
        data = package(config, value)
        if kind == 'json':
            write_json(path, data)
        else:
            folder = path.stem + '-thumbnails'
            text, images = markdown(value, data, thumbnails, folder)
            path.write_text(text, encoding='utf-8')
            if images:
                (path.parent / folder).mkdir(exist_ok=True)
            for image, blob in images.items():
                (path.parent / folder / image).write_bytes(blob)
                written.append(path.parent / folder / image)
    return {'status': 'exported', 'kind': kind, 'path': str(path), 'files': len(written)}
