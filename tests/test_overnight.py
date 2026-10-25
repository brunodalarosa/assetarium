"""Synthetic caption runs exercise owner retries without a real model or assets."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from test_incremental import library, ready
from test_captions import Backend, caption
from local_asset_library.catalog import save_json, detail
from local_asset_library.captions import file_hash, overlay_for
from local_asset_library.incremental import update_record
from local_asset_library.membership import records
from local_asset_library.library_index import index_library
from local_asset_library.overnight import (plan, create_run, caption_batch, outcomes, remaining,
    run_path, recover_inflight, verify_protected, record_fault, set_state, summary)
from local_asset_library.settings import save_general_settings
from local_asset_library.caption_batching import GpuMemoryError


class CaptionBackend(Backend):
    contract = {'model_id': 'synthetic', 'revision': 'synthetic'}
    settings = {'seed': 0}
    def close(self):
        self.closed = True


@pytest.fixture
def overnight(library):
    config, embedding = library
    work = ready(config)
    index_library(work, embedding)
    for name in ('src/local_asset_library/captions.py', 'src/local_asset_library/overnight.py',
                 'src/local_asset_library/embedding_backend.py', 'src/local_asset_library/library_index.py',
                 'runtime/embedding/uv.lock', 'docs/embedding-model.json',
                 'src/local_asset_library/incremental.py', 'src/local_asset_library/library_policy.py',
                 'scripts/overnight-descriptions.py', 'config.example.toml'):
        path = config.project_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic contract')
    rows = records(work)
    for row, state in zip(rows[:2], ('pending', 'failed')):
        row['description'] = None
        row['processing']['caption'] = state
        row['caption_provenance'] = None if state == 'pending' else {'prompt_version': 'v2', 'attempts': [{'error': 'Previous caption fault'}]}
        update_record(work, row)
    return config, work, embedding


def controller():
    path = Path(__file__).resolve().parents[1] / 'scripts/overnight-descriptions.py'
    spec = importlib.util.spec_from_file_location('overnight_controller', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_selection_skips_usable_caption_notes_and_warnings(overnight):
    config, work, _ = overnight
    rows = records(work)
    for row in rows[2:]:
        row['caption_provenance']['visual_faults'] = [{'severity': 'warning', 'evidence': 'Synthetic uncertain appearance', 'reason': 'Review only'}]
        update_record(work, row)
    result = plan(config)
    assert result['selected'] == 2 and result['skipped_usable'] == 4
    assert result['input_faults'] == [] and not result['model_inference_performed']


def test_failed_generation_moves_on_and_preserves_previous_evidence(overnight):
    config, work, embedding = overnight
    old_log = config.output_path('data', 'captions/previous-fault.json')
    save_json(old_log, {'status': 'failed', 'raw': 'previous evidence'})
    old_hash = file_hash(old_log)
    row = records(work)[0]
    overlay, path = overlay_for(work, row)
    overlay['notes'] = 'Owner note to preserve'
    save_json(path, overlay)
    before = path.read_bytes()
    identifier = create_run(config)
    backend = CaptionBackend(['{}', json.dumps(caption())])
    caption_batch(config, identifier, lambda _: backend)
    assert len(backend.calls) == 2 and backend.closed
    assert sorted(r['status'] for r in outcomes(config, identifier).values()) == ['complete', 'failed']
    assert not remaining(config, identifier)
    caption_batch(config, identifier, lambda _: pytest.fail('Resume must not load a model'))
    assert old_hash == file_hash(old_log) and before == path.read_bytes()
    index_library(work, embedding, description_only=True)
    assert verify_protected(config, identifier)['status'] == 'passed'
    set_state(config, identifier, phase='complete', status='complete_with_caption_faults')
    assert summary(config, identifier)['results']['failed'] == 1


def test_interruption_never_repeats_attempt_in_same_run(overnight):
    config, _, _ = overnight
    save_general_settings(config, 8, None, 1)  # One asset per batch: the single-asset contract.
    identifier = create_run(config)
    first = CaptionBackend([KeyboardInterrupt()])
    # The fake backend mimics an interrupt during actual generation.
    def interrupted(*args, **kwargs):
        first.calls.append(args)
        raise KeyboardInterrupt()
    first.generate = interrupted
    with pytest.raises(KeyboardInterrupt):
        caption_batch(config, identifier, lambda _: first)
    recover_inflight(config, identifier)
    assert len(outcomes(config, identifier)) == 1
    second = CaptionBackend([json.dumps(caption())])
    caption_batch(config, identifier, lambda _: second)
    assert len(first.calls) == 1 and len(second.calls) == 1
    assert not remaining(config, identifier)


def test_saved_response_is_recovered_without_second_generation(overnight, monkeypatch):
    config, _, _ = overnight
    from local_asset_library import overnight as module
    identifier = create_run(config)
    backend = CaptionBackend([json.dumps(caption())])
    original = module.apply_saved
    def interrupted(*args):
        raise KeyboardInterrupt()
    monkeypatch.setattr(module, 'apply_saved', interrupted)
    with pytest.raises(KeyboardInterrupt):
        caption_batch(config, identifier, lambda _: backend, limit=1)
    monkeypatch.setattr(module, 'apply_saved', original)
    recover_inflight(config, identifier)
    assert len(backend.calls) == 1
    assert next(iter(outcomes(config, identifier).values()))['status'] == 'complete'
    assert len(remaining(config, identifier)) == 1


def test_new_run_can_retry_fault_but_resume_cannot(overnight):
    config, _, _ = overnight
    first = create_run(config)
    caption_batch(config, first, lambda _: CaptionBackend(['{}', '{}']))
    assert not remaining(config, first)
    second = create_run(config)
    assert second != first and len(remaining(config, second)) == 2
    assert len(outcomes(config, first)) == 2


def test_pending_pack_selection_retains_faults_and_saved_selection(overnight):
    config, work, embedding = overnight
    # Establish the combined image/text state for the retained caption fault.
    index_library(work, embedding)
    pending = next(r for r in records(work) if r['processing']['caption'] == 'pending')
    result = plan(config, packs=[pending['pack_id']], pending_only=True, peak_reserve_mib=1024)
    assert result['selected'] == 1
    assert result['targets'][0]['asset_id'] == pending['asset_id']
    assert result['peak_additional_bytes'] == 1024**3
    assert result['skipped_out_of_scope'] == 1
    identifier = create_run(config, packs=[pending['pack_id']], pending_only=True, peak_reserve_mib=1024)
    assert remaining(config, identifier) == result['targets']
    caption_batch(config, identifier, lambda _: CaptionBackend([json.dumps(caption())]))
    assert not remaining(config, identifier)
    assert next(r for r in records(work) if r['processing']['caption'] == 'failed')
    index_library(work, embedding, description_only=True)
    assert verify_protected(config, identifier)['status'] == 'passed'


def test_unknown_pack_selection_is_rejected(overnight):
    config, _, _ = overnight
    with pytest.raises(ValueError, match='unknown pack'):
        plan(config, packs=['absent'])


def test_text_indexing_does_not_generate_or_modify_image_vectors(overnight):
    config, work, embedding = overnight
    from local_asset_library.overnight import image_rows
    images = image_rows(config)
    calls = len(embedding.calls)
    identifier = create_run(config)
    caption_batch(config, identifier, lambda _: CaptionBackend([json.dumps(caption()), json.dumps(caption())]))
    result = index_library(work, embedding, description_only=True)
    assert result['processed'] == 2
    assert image_rows(config) == images
    assert all(call[0] == 'document' for call in embedding.calls[calls:])
    assert verify_protected(config, identifier)['status'] == 'passed'


def test_missing_input_is_fault_without_model_loading(overnight):
    config, work, _ = overnight
    identifier = create_run(config)
    first = remaining(config, identifier)[0]
    row = detail(work, first['asset_id'])
    path = config.output_path('data', row['previews'][0]['path'][5:])
    path.unlink()
    caption_batch(config, identifier, lambda _: pytest.fail('Missing input must not load a model'), limit=1)
    receipt = outcomes(config, identifier)[first['asset_id']]
    assert receipt['status'] == 'failed' and receipt['errors']


def test_watchdog_stops_only_owned_worker_and_records_fault(overnight):
    config, _, _ = overnight
    identifier = create_run(config)
    task = remaining(config, identifier)[0]
    progress_path = run_path(config, identifier) / 'worker-progress.json'
    code = "import os,json,time,pathlib; pathlib.Path(os.environ['PROBE_PATH']).write_text(json.dumps({'worker_token':os.environ['OVERNIGHT_WORKER_TOKEN'],'pid':os.getpid(),'status':'running','current':json.loads(os.environ['PROBE_TASK'])})); time.sleep(60)"
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, PROBE_PATH=str(progress_path), PROBE_TASK=json.dumps(task)):
        result = controller().supervise(config, identifier, [sys.executable, '-c', code], 'caption', timeout=1)
    assert result['status'] == 'asset_timeout'
    assert outcomes(config, identifier)[task['asset_id']]['status'] == 'failed'
    assert len(summary(config, identifier)['worker_faults']) == 1


def test_protection_blocks_owner_correction_changes(overnight):
    config, work, _ = overnight
    row = records(work)[0]
    overlay, path = overlay_for(work, row)
    identifier = create_run(config)
    overlay['notes'] = 'Owner edited during run'
    save_json(path, overlay)
    with pytest.raises(ValueError, match='Protected'):
        verify_protected(config, identifier)


def test_resume_blocks_a_live_orphan_worker_without_killing_it(overnight):
    config, _, _ = overnight
    import os
    identifier = create_run(config)
    save_json(run_path(config, identifier) / 'worker-owner.json', {'pid': os.getpid(), 'token': 'test-owned-worker'})
    with pytest.raises(ValueError, match='still running'):
        controller().assert_worker_stopped(config, identifier)


def test_coordinator_completes_and_publishes_synthetic_run(overnight, monkeypatch):
    config, work, embedding = overnight
    from contextlib import nullcontext
    from local_asset_library.overnight import contract
    module = controller()
    value = json.loads((config.project_root / 'docs/library-membership.json').read_text())
    value['budget'] = {'total_allocated_bytes':8*1024**3,'peak_additional_allocated_bytes':2*1024**3}
    save_json(config.project_root / 'docs/library-membership.json', value)
    monkeypatch.setattr(module, 'load_project_config', lambda *args: config)
    monkeypatch.setattr(module, 'check_prerequisites', lambda _: contract(config))
    monkeypatch.setattr(module, 'storage', lambda *args: {'receipt':'synthetic-storage','allocated_bytes':100})
    monkeypatch.setattr(module, 'keep_awake', nullcontext)
    def synthetic_worker(config, identifier, command, phase):
        if phase == 'caption':
            caption_batch(config, identifier, lambda _: CaptionBackend([json.dumps(caption()), json.dumps(caption())]))
        else:
            index_library(work, embedding, description_only=True)
    monkeypatch.setattr(module, 'supervise', synthetic_worker)
    monkeypatch.setattr(sys, 'argv', ['overnight-descriptions.py', '--new-run'])
    assert module.main() == 0
    latest = json.loads(config.output_path('data', 'overnight-descriptions/latest.json').read_text())
    report = json.loads((run_path(config, latest['run_id']) / 'summary.json').read_text())
    assert latest['status'] == 'complete' and report['results']['complete'] == 2
    assert len(records(config)) == 6 and report['state']['generation'].startswith('v_')


def test_morning_report_separates_new_and_retained_index_faults(overnight):
    config, _, _ = overnight
    identifier = create_run(config)
    targets = remaining(config, identifier)
    save_json(run_path(config, identifier) / 'index-test.json', {'outcomes':[
        {'asset_id':targets[0]['asset_id'],'channel':'description','status':'failed','reused':False,'error':'Synthetic vector fault'},
        {'asset_id':targets[1]['asset_id'],'channel':'description','status':'failed','reused':True,'error':'Retained index fault'}]})
    report = summary(config, identifier)
    assert report['description_index']['new_failed'] == 1
    assert report['description_index']['retained_failed'] == 1
    assert report['description_index']['failures'][0]['error'] == 'Synthetic vector fault'


def test_batched_run_uses_one_generation_and_records_batch_provenance(overnight):
    config, _, _ = overnight
    identifier = create_run(config)
    backend = CaptionBackend([json.dumps(caption()), json.dumps(caption())])
    caption_batch(config, identifier, lambda _: backend)
    assert backend.batches == [2] and not remaining(config, identifier)
    saved = [json.loads(p.read_text(encoding='utf-8')) for p in (run_path(config, identifier) / 'attempts').glob('*.json')]
    assert {s['provenance']['generation_mode'] for s in saved} == {'batched-v1'}
    assert sorted(s['provenance']['batch']['position'] for s in saved) == [0, 1]
    assert {s['provenance']['batch']['size'] for s in saved} == {8}
    assert not (run_path(config, identifier) / 'inflight.json').exists()


def test_interrupted_batch_records_every_inflight_asset_once(overnight):
    config, _, _ = overnight
    identifier = create_run(config)
    first = CaptionBackend([])
    def interrupted(*args, **kwargs):
        first.calls.append(args)
        raise KeyboardInterrupt()
    first.generate = interrupted
    with pytest.raises(KeyboardInterrupt):
        caption_batch(config, identifier, lambda _: first)
    assert len(json.loads((run_path(config, identifier) / 'inflight.json').read_text())['asset_ids']) == 2
    recover_inflight(config, identifier)
    assert len(outcomes(config, identifier)) == 2 and not remaining(config, identifier)
    second = CaptionBackend([])
    caption_batch(config, identifier, lambda _: second)
    assert not second.calls


def test_gpu_memory_stop_leaves_overnight_assets_pending(overnight):
    config, _, _ = overnight
    save_general_settings(config, 8, None, 4)
    identifier = create_run(config)
    backend = CaptionBackend([GpuMemoryError('synthetic out of memory')])
    from local_asset_library.description_engines import MemoryLimitError  # The port's error; adapters translate theirs.
    with pytest.raises(MemoryLimitError, match='batch size 4'):
        caption_batch(config, identifier, lambda _: backend)
    assert not (run_path(config, identifier) / 'inflight.json').exists()
    assert not outcomes(config, identifier) and len(remaining(config, identifier)) == 2
