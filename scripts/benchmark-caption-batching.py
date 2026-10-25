"""Read-only caption batching benchmark: pipeline model, prompt and sampling at several batch sizes.

Reads one source's working catalog and rendered views and writes only under
data/evidence/caption-batch-benchmark/<run-name>. Never publishes, checkpoints or
touches owner overlays; batch 1 uses the unchanged QwenBackend.generate. Failures
(including out-of-memory) are recorded per batch and never retried. Batches above 1
use the production caption_batching module, so reruns measure the pipeline itself.

  .\\scripts\\caption-runtime.ps1 run --locked --no-sync --offline --project runtime/caption python
      scripts/benchmark-caption-batching.py --source "<key>" --run-name <name> [--dry-run]
"""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from local_asset_library.config import ConfigError, load_project_config
from local_asset_library.sources import get_source, bound
from local_asset_library.incremental import working, CAPTION_PROMPT_VERSION
from local_asset_library.catalog import read_database, parse_record
from local_asset_library.captions import image_inputs, parse_caption
from local_asset_library.gpu_queue import lease

MAX_NEW_TOKENS = 1100  # Production single-attempt limit (incremental.run_caption, max_attempts=1).


def spaced(items, count):
    """Deterministic spread across a sorted list instead of its first entries."""
    count = min(count, len(items))
    return [items[i * len(items) // count] for i in range(count)] if count else []


def views(record):
    return sum(p.get('origin') == 'rendered' for p in record['previews'])


def select(work, per_folder, explicit):
    with closing(read_database(work)) as db:
        rows = db.execute("SELECT asset_id,pack_id,name,CAST(record AS BLOB) FROM assets ORDER BY asset_id").fetchall()
    records = {row[0]: parse_record(*row) for row in rows}
    if explicit:
        missing = [i for i in explicit if i not in records]
        if missing:
            raise ConfigError('Unknown asset IDs: ' + ', '.join(missing))
        return [records[i] for i in explicit]
    groups = defaultdict(lambda: ([], []))
    for record in records.values():
        provenance = record.get('caption_provenance') or {}
        if record['processing'].get('caption') == 'complete' and provenance.get('prompt_version') == CAPTION_PROMPT_VERSION:
            groups[record['source_relative_identity'].split('/', 1)[0]][views(record) >= 4].append(record)
    chosen = []
    for folder in sorted(groups):
        three, four = groups[folder]
        picks = spaced(four, per_folder // 2)
        picks += spaced(three, per_folder - len(picks))
        picks += spaced([r for r in four if r not in picks], per_folder - len(picks))
        chosen += picks
    return chosen


def stored(record):
    provenance = record.get('caption_provenance') or {}
    attempt = (provenance.get('attempts') or [{}])[-1]
    metrics = attempt.get('metrics') or {}
    return {'raw': attempt.get('raw'), 'caption': record.get('description'),
            'elapsed_seconds': metrics.get('elapsed_seconds'), 'generated_tokens': metrics.get('generated_tokens')}


def compare(caption, reference):
    if not caption or not reference:
        return {}
    colors = {c.casefold() for c in caption['colors']}, {c.casefold() for c in reference['colors']}
    return {'label_match': caption['identity']['label'].casefold() == reference['identity']['label'].casefold(),
            'colors_jaccard': round(len(colors[0] & colors[1]) / max(1, len(colors[0] | colors[1])), 3),
            'description_words': len(caption['description'].split())}


def outcome(raw, error=None):
    if error:
        return {'status': 'inference_failed', 'error': error, 'raw': raw, 'caption': None}
    try:
        caption = parse_caption(raw)
        caption.pop('suggested_uses')
        return {'status': 'complete', 'raw': raw, 'caption': caption}
    except (ValueError, TypeError) as exc:
        return {'status': 'invalid_output', 'error': str(exc), 'raw': raw, 'caption': None}


def generate_single(backend, item, prompt):
    """Production path, unchanged: QwenBackend.generate."""
    started = time.perf_counter()
    try:
        raw, metrics = backend.generate(item['inputs'], prompt, max_new_tokens=MAX_NEW_TOKENS)
        rows = [{**outcome(raw), 'generated_tokens': metrics['generated_tokens'], 'input_tokens': metrics['input_tokens'],
                 'hit_token_limit': metrics['generated_tokens'] >= MAX_NEW_TOKENS}]
    except Exception as exc:  # Timeouts, token exhaustion and OOM are results here.
        rows = [outcome(None, f'{type(exc).__name__}: {exc}')]
    return rows, time.perf_counter() - started


def generate_batch(backend, batch, prompt):
    """The production batched path (caption_batching.generate_batch), timed end to end."""
    from local_asset_library.caption_batching import GpuMemoryError, generate_batch as pipeline_batch
    started = time.perf_counter()
    try:
        results = pipeline_batch(backend, [item['inputs'] for item in batch], prompt, MAX_NEW_TOKENS)
    except GpuMemoryError as exc:
        return [outcome(None, f'GpuMemoryError: {exc}') for _ in batch], time.perf_counter() - started
    wall, rows = time.perf_counter() - started, []
    for result in results:
        if isinstance(result, BaseException):
            rows.append({**outcome(None, f'{type(result).__name__}: {result}'),
                         'hit_token_limit': 'token limit' in str(result)})
            continue
        raw, metrics = result
        rows.append({**outcome(raw), 'generated_tokens': metrics['generated_tokens'],
                     'input_tokens': metrics['input_tokens'], 'hit_token_limit': False})
    return rows, wall


def summarize(rows, sizes):
    summary = {}
    for size in sizes:
        selected = [r for r in rows if r['batch_size'] == size]
        batches = {r['batch_index']: r['batch_wall_seconds'] for r in selected}
        wall = sum(batches.values())
        complete = [r for r in selected if r['status'] == 'complete']
        matches = [r['comparison']['label_match'] for r in complete if r.get('comparison')]
        summary[size] = {'assets': len(selected), 'complete': len(complete),
                         'invalid_output': sum(r['status'] == 'invalid_output' for r in selected),
                         'inference_failed': sum(r['status'] == 'inference_failed' for r in selected),
                         'hit_token_limit': sum(bool(r.get('hit_token_limit')) for r in selected),
                         'wall_seconds': round(wall, 2), 'seconds_per_asset': round(wall / max(1, len(selected)), 2),
                         'generated_tokens_per_second': round(sum(r.get('generated_tokens') or 0 for r in selected) / max(wall, 1e-9), 1),
                         'mean_generated_tokens': round(sum(r.get('generated_tokens') or 0 for r in complete) / max(1, len(complete)), 1),
                         'label_match_rate_vs_stored': round(sum(matches) / len(matches), 3) if matches else None,
                         'mean_colors_jaccard_vs_stored': round(sum(r['comparison']['colors_jaccard'] for r in complete) / len(complete), 3) if complete else None,
                         'exact_raw_match_vs_stored': sum(bool(r.get('exact_raw_match')) for r in selected),
                         'cuda_peak_allocated_bytes': selected[0]['cuda_peak_allocated_bytes'] if selected else None,
                         'cuda_peak_reserved_bytes': selected[0]['cuda_peak_reserved_bytes'] if selected else None}
    base = summary.get(1, {}).get('seconds_per_asset')
    for value in summary.values():
        value['speedup_vs_batch_1'] = round(base / value['seconds_per_asset'], 2) if base and value['seconds_per_asset'] else None
    return summary


def caption_cell(caption, status=None, error=None, tokens=None):
    if not caption:
        return f'<td class="fault"><b>{html.escape(status or "missing")}</b><br>{html.escape(error or "")}</td>'
    identity = caption['identity']
    meta = f'<small>{tokens} tokens</small>' if tokens else ''
    return (f'<td><b>{html.escape(identity["label"])}</b> <small>({html.escape(identity["certainty"])})</small><br>'
            f'{html.escape(caption["description"])}<br><small>Colors: {html.escape(", ".join(caption["colors"]))}</small><br>{meta}</td>')


def review_page(work, items, rows, summary, sizes):
    head = ''.join(f'<th>Batch {s}</th>' for s in sizes)
    stats = ''.join(f'<tr><td>{s}</td><td>{v["seconds_per_asset"]}</td><td>{v["speedup_vs_batch_1"]}</td>'
                    f'<td>{v["generated_tokens_per_second"]}</td><td>{v["complete"]}/{v["assets"]}</td>'
                    f'<td>{v["label_match_rate_vs_stored"]}</td><td>{round((v["cuda_peak_allocated_bytes"] or 0) / 2**30, 2)}</td></tr>'
                    for s, v in summary.items())
    articles = []
    for item in items:
        record = item['record']
        images = ''.join(f'<figure><img src="{work.output_path("data", p["path"][5:]).as_uri()}" alt="">'
                         f'<figcaption>{html.escape(p["view_label"])}</figcaption></figure>' for p in item['inputs'])
        reference = item['stored']
        cells = caption_cell(reference['caption'], tokens=reference.get('generated_tokens'))
        for size in sizes:
            row = next((r for r in rows if r['asset_id'] == record['asset_id'] and r['batch_size'] == size), None)
            cells += caption_cell(row['caption'], row['status'], row.get('error'), row.get('generated_tokens')) if row else '<td>not run</td>'
        articles.append(f'<article><h2>{html.escape(record["display_name"])}</h2><p><code>{record["asset_id"]}</code> · '
                        f'{html.escape(record["source_relative_identity"].split("/", 1)[0])} · {len(item["inputs"])} views</p>'
                        f'<div class="views">{images}</div><table><tr><th>Stored (pipeline)</th>{head}</tr><tr>{cells}</tr></table></article>')
    return ('<!doctype html><meta charset="utf-8"><title>Caption batching benchmark</title>'
            '<style>body{font:15px system-ui;margin:2rem;background:#f3f2ee;color:#222;max-width:1600px}'
            'article{background:#fff;padding:1rem;margin:1.5rem 0;border-radius:8px}.views{display:flex;flex-wrap:wrap;gap:6px}'
            'figure{margin:0}img{width:220px;background:#525252}table{border-collapse:collapse;width:100%;margin-top:.5rem}'
            'td,th{border:1px solid #ddd;padding:.5rem;vertical-align:top;text-align:left}.fault{background:#fff1ef}</style>'
            '<h1>Caption batching benchmark</h1><p>Same model, prompt and sampling as the pipeline. Sampling is random, so '
            'compare batched outputs against how much the batch 1 rerun differs from the stored description.</p>'
            '<table><tr><th>Batch</th><th>s/asset</th><th>Speedup</th><th>Tokens/s</th><th>Valid</th><th>Label match vs stored</th>'
            f'<th>Peak GiB</th></tr>{stats}</table>' + ''.join(articles))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', required=True)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--batch-sizes', default='1,2,4,8')
    parser.add_argument('--per-folder', type=int, default=5)
    parser.add_argument('--assets', help='Comma-separated asset IDs (reuse a previous selection)')
    parser.add_argument('--dry-run', action='store_true', help='Check selection and input hashes; load no model, write nothing')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', args.run_name):
        raise SystemExit('Run name must be 1-64 letters, digits, dot, dash or underscore')
    sizes = sorted({int(s) for s in args.batch_sizes.split(',')})
    if not sizes or sizes[0] < 1 or sizes[-1] > 16:
        raise SystemExit('Batch sizes must be between 1 and 16')
    config = load_project_config(root)
    scoped = bound(config, get_source(config, args.source))
    work = working(scoped)
    output = config.output_path('data', 'evidence/caption-batch-benchmark/' + args.run_name)
    if output.exists():
        raise SystemExit(f'Run already exists; choose a new --run-name: {output}')
    items, skipped = [], []
    for record in select(work, args.per_folder, args.assets.split(',') if args.assets else None):
        try:
            items.append({'record': record, 'inputs': image_inputs(work, record), 'stored': stored(record)})
        except (OSError, ValueError) as exc:
            skipped.append({'asset_id': record['asset_id'], 'reason': str(exc)})
    for item in items:
        record = item['record']
        print(f"{record['asset_id']}  {len(item['inputs'])} views  {record['source_relative_identity'].split('/', 1)[0]} / {record['display_name']}")
    for skip in skipped:
        print('SKIPPED', skip['asset_id'], skip['reason'])
    print(f'{len(items)} assets selected, {len(skipped)} skipped; batch sizes {sizes}')
    if args.dry_run or not items:
        return
    prompt = (root / f'prompts/caption-{CAPTION_PROMPT_VERSION}.txt').read_text(encoding='utf-8')
    with lease(config, 'benchmark-caption-batching', timeout=30):
        from local_asset_library.caption_backend import QwenBackend
        backend = QwenBackend(scoped, json.loads((root / 'docs/caption-model.json').read_text(encoding='utf-8')))
        torch = backend.torch
        output.mkdir(parents=True)
        report = {'source': args.source, 'run_name': args.run_name, 'prompt_version': CAPTION_PROMPT_VERSION,
                  'batch_sizes': sizes, 'max_new_tokens': MAX_NEW_TOKENS, 'settings': backend.settings,
                  'model': {k: backend.contract[k] for k in ('model_id', 'revision', 'versions', 'device', 'cuda')},
                  'load_seconds': round(backend.load_seconds, 2), 'cuda_free_total_bytes_at_load': list(torch.cuda.mem_get_info()),
                  'assets': [i['record']['asset_id'] for i in items], 'skipped': skipped, 'started_utc': datetime.now(timezone.utc).isoformat()}
        try:
            _, warmup = generate_single(backend, items[0], prompt)  # CUDA warm-up, excluded from results.
            report['warmup_seconds'] = round(warmup, 2)
            rows = []
            with (output / 'outputs.jsonl').open('w', encoding='utf-8') as stream:
                for size in sizes:
                    torch.cuda.empty_cache()
                    torch.cuda.reset_peak_memory_stats()
                    size_rows = []
                    for index in range(0, len(items), size):
                        batch = items[index:index + size]
                        results, wall = generate_single(backend, batch[0], prompt) if size == 1 else generate_batch(backend, batch, prompt)
                        for item, result in zip(batch, results):
                            reference = item['stored']
                            row = {'batch_size': size, 'batch_index': index // size, 'batch_assets': len(batch),
                                   'batch_wall_seconds': round(wall, 3), 'asset_id': item['record']['asset_id'], **result,
                                   'comparison': compare(result['caption'], reference['caption']),
                                   'exact_raw_match': result['raw'] is not None and result['raw'] == reference['raw']}
                            size_rows.append(row)
                            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                            stream.flush()
                        print(f'batch {size} #{index // size}: {wall:.1f}s, ' + ', '.join(r['status'] for r in results), flush=True)
                    for row in size_rows:
                        row.update(cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                                   cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
                    rows += size_rows
        finally:
            backend.close()
    report['summary'] = summarize(rows, sizes)
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'review.html').write_text(review_page(work, items, rows, report['summary'], sizes), encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))
    print('Wrote', output)


if __name__ == '__main__':
    main()
