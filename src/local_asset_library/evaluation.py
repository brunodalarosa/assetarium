"""Frozen pilot evaluation arithmetic; no inference, tuning or owner-approval inference."""
import json
import math
from pathlib import Path
from .captions import file_hash
from .config import ConfigError


def verify_freeze(root):
    root = Path(root)
    receipt = json.loads((root/'docs/evaluation/freeze.json').read_text(encoding='utf-8'))
    if not receipt.get('before_competing_rankings'):
        raise ConfigError('Evaluation must be frozen before comparisons')
    for name, sha in receipt['files'].items():
        path = root/name
        if not path.resolve().is_relative_to(root.resolve()) or file_hash(path) != sha:
            raise ConfigError('Frozen evaluation input changed: '+name)
    return receipt


def ordered_queries(spec):
    return sorted(spec, key=lambda q: q['split'] == 'held_out')


def percentile(values, fraction=.95):
    return sorted(values)[max(0, math.ceil(len(values)*fraction)-1)] if values else None


def relevance_metrics(ids, grades, k=5):
    """Complete graded pool; empty positive pool has no defined positive-quality metrics."""
    if len(ids) != len(set(ids)) or set(ids)-set(grades):
        raise ConfigError('Duplicate or unjudged result in evaluation')
    if any(type(g) is not int or not 0 <= g <= 3 for g in grades.values()):
        raise ConfigError('Invalid relevance grade')
    positive = {a for a,g in grades.items() if g >= 2}
    top = ids[:k]
    ideal = sorted(grades.values(),reverse=True)[:k]
    dcg = lambda gs: sum((2**g-1)/math.log2(i+2) for i,g in enumerate(gs))
    denom = dcg(ideal)
    return {'hit5': int(bool(set(top)&positive)) if positive else None,
            'ndcg5': dcg([grades[a] for a in top])/denom if denom else None,
            'reciprocal_rank5': next((1/(i+1) for i,a in enumerate(top) if a in positive),0) if positive else None,
            'returned':len(top),'relevant_returned':len(set(top)&positive),
            'positive_pool':len(positive)}


def filter_violations(result, query, records):
    """Independent check against catalog file evidence, not retrieval.matches()."""
    violations = []
    for item in result['results']:
        record = records[item['asset_id']]
        filters = query.get('filters',{})
        if 'pack' in filters and record['pack_id'] != filters['pack']:
            violations.append({'asset_id':item['asset_id'],'filter':'pack'})
        if 'format' in filters and not any(f['format']==filters['format'] and f['availability']=='available' and f.get('sha256') for f in record['files']):
            violations.append({'asset_id':item['asset_id'],'filter':'format'})
    return violations


def count_quality(entries, ids):
    picked = [e for e in entries if e['query_id'] in ids]
    valid = [e for e in picked if e.get('quality',{}).get('hit5') is not None]
    return {'queries':len(ids),'successful_evaluations':len(valid),
            'hits':sum(e['quality']['hit5'] for e in valid),
            'hit5':sum(e['quality']['hit5'] for e in valid)/len(valid) if valid else None,
            'ndcg5_mean':sum(e['quality']['ndcg5'] for e in valid)/len(valid) if valid else None,
            'mrr5_mean':sum(e['quality']['reciprocal_rank5'] for e in valid)/len(valid) if valid else None}


def expansion_gate(summary, protocol, labels_status):
    combined, baseline = summary['combined'], summary['keyword']
    c,b = combined['natural'],baseline['natural']
    complete = c['successful_evaluations']==c['queries'] and b['successful_evaluations']==b['queries']
    improvement = 100*(c['hit5']-b['hit5']) if complete else None
    exact_lost = len(set(baseline['exact_success_ids'])-set(combined['exact_success_ids']))
    a = protocol['acceptance']
    checks = {
        'natural_improvement': improvement is not None and improvement >= a['natural_language_hit5_improvement_percentage_points'],
        'exact_success_loss': exact_lost <= a['maximum_exact_name_successes_lost'],
        'verified_filters': combined['filter_violations']==0 and combined['failures']==0,
        'warm_latency': combined['warm_p95_seconds'] is not None and combined['warm_p95_seconds'] < a['warm_combined_p95_seconds_strictly_below'],
    }
    return {'status':'provisional' if labels_status!='owner_reviewed' else ('pass' if all(checks.values()) else 'fail'),
            'conditional_arithmetic':'pass' if all(checks.values()) else 'fail',
            'checks':checks,'natural_improvement_percentage_points':improvement,
            'exact_success_ids_lost':sorted(set(baseline['exact_success_ids'])-set(combined['exact_success_ids'])),
            'owner_approval':'pending','step7_authorized':False}
