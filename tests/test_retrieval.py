"""Synthetic vectors are explicit test doubles; production inference has no fallback."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import numpy as np
import pytest

from local_asset_library.catalog import scan, read_database, save_json, encoded, digest
from local_asset_library.captions import file_hash
from local_asset_library.config import Config, ConfigError
from local_asset_library.embedding_backend import normalize
from local_asset_library.retrieval import (SearchEngine, index_pilot, pilot_records, resolved_detail,
                                          description_input, index_database)


def unit(axis):
    value = np.zeros(768, dtype=np.float32)
    value[axis] = 1
    return value


class SyntheticBackend:
    contract = {"dimensions": 768, "revision": "synthetic-test-only", "dtype": "bfloat16",
                "query_prompt": "task: search result | query: ", "preprocessing": "synthetic"}

    def __init__(self):
        self.calls = []
        self.last_metrics = {"test_double": True}
        self.failure = None

    def text(self, text, role="query"):
        self.calls.append((role, text))
        if self.failure:
            raise RuntimeError(self.failure)
        return unit(0)

    def image(self, path):
        self.calls.append(("image", str(path)))
        if self.failure:
            raise RuntimeError(self.failure)
        return unit(0 if "item00" in str(path) else 1)


@pytest.fixture
def indexed(tmp_path):
    root, source = tmp_path / "project", tmp_path / "source"
    root.mkdir()
    source.mkdir()
    config = Config(root, source, None)
    (source / "pack").mkdir()
    for i in range(40):
        (source / "pack" / f"item{i:02}.obj").write_text("v 0 0 0\n", encoding="utf-8")
    scan(config)
    with closing(read_database(config)) as db:
        records = [json.loads(r[0]) for r in db.execute("SELECT record FROM assets ORDER BY identity")]
    for i, record in enumerate(records):
        record["processing"]["caption"] = record["processing"]["inspection"] = "complete"
        record["description"] = {"identity": {"label": "item", "certainty": "probable"},
             "description": "An observed red object. " * 18, "shape": ["round"], "colors": ["red"],
             "parts": ["body"], "style": ["stylized"], "distinguishing_features": ["leaf"], "uncertainties": []}
        record["suggested_uses"] = ["SECRET SPECULATIVE USE"]
        record["caption_provenance"] = {"fingerprint": "synthetic-caption", "input_views": [], "visual_faults": []}
        record["technical"] = {"inspected_path": record["files"][0]["path"], "inspected_sha256": record["files"][0]["sha256"],
             "inspected_format": "obj", "evaluated_instance_totals": {"triangles": i * 10}, "armatures": []}
        record["pack_id"] = "even" if i % 2 == 0 else "odd"
        record["previews"] = []
        for view in ("front", "side"):
            path = config.output_path("data", f"views/item{i:02}-{view}.png")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"test-double-pixels-{i}-{view}".encode())
            record["previews"].append({"path": path.relative_to(root).as_posix(), "sha256": file_hash(path),
                                       "view_label": view, "origin": "rendered"})
    with sqlite3.connect(config.output_path("data", "catalog.sqlite")) as db:
        db.executemany("UPDATE assets SET record=? WHERE asset_id=?", [(encoded(r), r["asset_id"]) for r in records])
    save_json(config.output_path("data", "pilot/selection-manifest.json"), {"assets": [{"asset_id": r["asset_id"]} for r in records]})
    backend = SyntheticBackend()
    save_json(config.output_path("data", "embeddings/capability.json"), {"contract_fingerprint": digest(backend.contract),
                  "actual_text_and_image_inference": True, "reference_image_query_support": True, "test_double": True})
    report = index_pilot(config, backend)
    assert report["complete"] == 120 and report["failed"] == 0
    return config, backend, records


@pytest.mark.parametrize("value", [np.zeros(768), np.full(768, np.nan), np.full(768, np.inf), np.ones(767), np.ones((1, 768))])
def test_invalid_vectors_rejected(value):
    with pytest.raises(ConfigError):
        normalize(value)


def test_finite_normalization():
    value = normalize(np.full(768, 1e30, dtype=np.float32))
    assert value.dtype == np.float32 and np.isfinite(value).all()
    assert np.isclose(np.linalg.norm(value), 1)


@pytest.mark.parametrize("change", [{"dimensions": 512}, {"revision": "other"}, {"dtype": "float16"},
                                   {"query_prompt": "wrong"}, {"preprocessing": "other"}])
def test_contract_mismatch(indexed, change):
    config, backend, _ = indexed
    wrong = {**backend.contract, **change}
    with pytest.raises(ConfigError, match="contract mismatch"):
        SearchEngine(config, backend, wrong).search("red object", "description")


def test_channels_duplicate_views_and_compact_size(indexed):
    config, backend, records = indexed
    response, evidence = SearchEngine(config, backend).search("item00", "combined")
    assert response["results"][0]["asset_id"] == records[0]["asset_id"]
    assert len({r["asset_id"] for r in response["results"]}) == len(response["results"])
    assert len(evidence["channel_rankings"]["image"]) == 40  # 80 individual views aggregate to 40 assets.
    assert set(evidence["channel_rankings"]) == {"keyword", "description", "image"}
    assert response["serialized_characters"] == len(encoded(response)) <= 6000
    response, _ = SearchEngine(config, backend).search("red", "combined", limit=20)
    assert not response["truncated"] and len(response["results"]) == 20
    assert response["serialized_characters"] == len(encoded(response)) <= 22000


def test_verified_filters_and_unknown_rejection(indexed):
    config, backend, records = indexed
    response, evidence = SearchEngine(config, backend).search("object", "combined", filters={"pack": "even", "format": "obj", "max_triangles": 25, "rigged": False})
    assert {r["asset_id"] for r in response["results"]} == {records[0]["asset_id"], records[2]["asset_id"]}
    for ranking in evidence["channel_rankings"].values():
        assert all(r["asset_id"] in {records[0]["asset_id"], records[2]["asset_id"]} for r in ranking)
    with pytest.raises(ConfigError, match="Unknown/unverified"):
        SearchEngine(config, backend).search("red", filters={"color": "red"})
    response, _ = SearchEngine(config, backend).search("red", "image", filters={"format": "fbx"})
    assert response["status"] == "no_match"


def test_unavailable_and_stale_sources_excluded(indexed):
    config, backend, records = indexed
    (config.source_root / "pack/item00.obj").unlink()
    (config.source_root / "pack/item01.obj").write_text("changed", encoding="utf-8")
    response, evidence = SearchEngine(config, backend).search("item00", "combined")
    assert all(r["asset_id"] not in {records[0]["asset_id"], records[1]["asset_id"]} for r in response["results"])
    assert len(evidence["excluded"]) == 2
    with pytest.raises(ConfigError):
        resolved_detail(config, records[0]["asset_id"])


def test_stale_preview_excluded_but_other_views_preserved(indexed):
    config, backend, records = indexed
    config.output_path("data", records[0]["previews"][0]["path"][5:]).write_bytes(b"changed")
    response, evidence = SearchEngine(config, backend).search("object", "image")
    assert records[0]["asset_id"] in {r["asset_id"] for r in response["results"]}
    assert len(evidence["excluded"]) == 1


def test_suggestions_excluded_and_correction_invalidates(indexed):
    config, backend, records = indexed
    text, _ = description_input(config, records[0])
    assert "SECRET" not in text
    overlay = {"schema_version": 1, "description": {"colors": ["blue"]}, "suggested_uses": None,
               "caption_review": "pending", "artistic_suitability": "pending", "notes": ""}
    save_json(config.output_path("data", f"captions/corrections/{records[0]['asset_id']}.json"), overlay)
    response, evidence = SearchEngine(config, backend).search("object", "description")
    assert records[0]["asset_id"] not in {r["asset_id"] for r in response["results"]}
    assert any("input fingerprint" in r["reason"] for r in evidence["excluded"])


def test_query_error_propagates(indexed):
    config, backend, _ = indexed
    backend.failure = "actual inference fault"
    with pytest.raises(RuntimeError, match="actual inference fault"):
        SearchEngine(config, backend).search("object", "combined")


def test_failed_index_never_retains_stale_vector_or_retries(indexed):
    config, backend, records = indexed
    with sqlite3.connect(config.output_path("data", "catalog.sqlite")) as db:
        record = deepcopy(records[0])
        record["description"]["colors"] = ["blue"]
        db.execute("UPDATE assets SET record=? WHERE asset_id=?", (encoded(record), record["asset_id"]))
    backend.failure = "inference failed"
    report = index_pilot(config, backend)
    assert report["failed"] == 1 and report["complete"] == 119
    calls = len(backend.calls)
    repeated = index_pilot(config, backend)
    assert len(backend.calls) == calls and repeated["failed"] == 1
    with closing(index_database(config, True)) as db:
        assert db.execute("SELECT count(*) FROM vectors WHERE asset_id=? AND channel='description'", (records[0]["asset_id"],)).fetchone()[0] == 0


def test_corrupt_vector_is_fatal(indexed):
    config, backend, _ = indexed
    with closing(index_database(config)) as db, db:
        db.execute("UPDATE vectors SET vector=? WHERE job_id=(SELECT job_id FROM vectors LIMIT 1)", (unit(3).tobytes(),))
    with pytest.raises(ConfigError, match="checksum"):
        SearchEngine(config, backend).search("object", "combined")


def test_reference_gate_and_boundary(indexed):
    config, backend, records = indexed
    response, evidence = SearchEngine(config, backend).search(mode="reference", reference=records[0]["previews"][0]["path"])
    assert response["results"][0]["asset_id"] == records[0]["asset_id"]
    assert set(evidence["channel_rankings"]) == {"image"}
    with pytest.raises(ConfigError, match="Reference must"):
        SearchEngine(config, backend).search(mode="reference", reference="https://example.org/image.png")
    save_json(config.output_path("data", "embeddings/capability.json"), {"contract_fingerprint": "wrong"})
    with pytest.raises(ConfigError, match="image-query capability"):
        SearchEngine(config, backend).search(mode="reference", reference=records[0]["previews"][0]["path"])


def test_no_match_and_explicit_weak_candidates(indexed):
    config, backend, _ = indexed
    response, _ = SearchEngine(config, backend).search("absent submarine", "keyword")
    assert response["status"] == "no_match" and not response["results"]
    response, evidence = SearchEngine(config, backend).search("object", "image", min_similarity=0.5)
    assert len(response["results"]) == 1 and response["results"][0]["match_status"] == "weak_unvalidated"
    assert len(evidence["channel_rankings"]["image"]) == 40
    response, _ = SearchEngine(config, backend).search("object", "image", filters={"pack": "odd"}, min_similarity=0.5)
    assert response["status"] == "no_match"


def test_detail_resolves_source_and_dependencies(indexed):
    config, _, records = indexed
    selected = resolved_detail(config, records[0]["asset_id"], "obj")
    assert Path(selected["selected_source"]["resolved_path"]).is_file()
    assert selected["record"]["suggested_uses"] == ["SECRET SPECULATIVE USE"]
    with pytest.raises(ConfigError):
        resolved_detail(config, records[0]["asset_id"], "fbx")


def test_missing_required_dependency_excluded_and_optional_fault_retained(indexed):
    config, backend, records = indexed
    for i, required in ((0, True), (1, False)):
        record = deepcopy(records[i])
        record["dependencies"] = [{"path": "pack/missing.png", "sha256": None,
                                   "status": "missing", "required_for_render": required}]
        record["inspection_run"] = {"source_faults": [{"status": "faulty", "kind": "missing_texture"}]}
        with sqlite3.connect(config.output_path("data", "catalog.sqlite")) as db:
            db.execute("UPDATE assets SET record=? WHERE asset_id=?", (encoded(record), record["asset_id"]))
    response, evidence = SearchEngine(config, backend).search("item00", "keyword")
    assert response["status"] == "no_match" and len(evidence["excluded"]) == 1
    response, _ = SearchEngine(config, backend).search("item01", "keyword")
    assert response["results"][0]["source_faulty"]
    selected = resolved_detail(config, records[1]["asset_id"])
    assert selected["dependencies"][0]["resolved_path"] is None
    assert selected["dependencies"][0]["status"] == "missing"


def test_nonunit_persisted_vector_rejected(indexed):
    import hashlib
    config, backend, _ = indexed
    blob = (unit(0) * 2).tobytes()
    with closing(index_database(config)) as db, db:
        db.execute("UPDATE vectors SET vector=?,vector_sha256=? WHERE job_id=(SELECT job_id FROM vectors LIMIT 1)",
                   (blob, hashlib.sha256(blob).hexdigest()))
    with pytest.raises(ConfigError, match="not normalized"):
        SearchEngine(config, backend).search("object", "combined")


def test_measured_filter_does_not_apply_to_alternate_format(indexed):
    config, backend, records = indexed
    record = deepcopy(records[0])
    alternate = config.source_root / "pack/item00.fbx"
    alternate.write_bytes(b"alternate test fixture")
    record["files"].append({"path": "pack/item00.fbx", "format": "fbx", "sha256": file_hash(alternate), "availability": "available"})
    with sqlite3.connect(config.output_path("data", "catalog.sqlite")) as db:
        db.execute("UPDATE assets SET record=? WHERE asset_id=?", (encoded(record), record["asset_id"]))
    response, _ = SearchEngine(config, backend).search("item00", "keyword", filters={"format": "fbx", "max_triangles": 100})
    assert response["status"] == "no_match"
    response, _ = SearchEngine(config, backend).search("item00", "keyword", filters={"format": "fbx"})
    assert response["results"][0]["name"] == "item00"


def test_keyword_description_uses_both_rankings_without_image_inference(indexed):
    from local_asset_library.retrieval import fuse
    config, backend, records = indexed
    backend.calls.clear()
    response, evidence = SearchEngine(config, backend).search("item00", "keyword_description")
    assert set(evidence["channel_rankings"]) == {"keyword", "description"}
    assert [r['asset_id'] for r in response['results']] == [r['asset_id'] for r in fuse(evidence['channel_rankings'])[:5]]
    assert response['results'][0]['asset_id'] == records[0]['asset_id']
    assert all(role == 'query' for role, _ in backend.calls)


def test_reference_excludes_parent_before_view_aggregation(indexed):
    config, backend, records = indexed
    parent = records[0]['previews'][0]
    response, evidence = SearchEngine(config, backend).search(mode='reference', reference=parent['path'],
                                                           exclude_image_hashes={parent['sha256']})
    result = next(r for r in evidence['channel_rankings']['image'] if r['asset_id'] == records[0]['asset_id'])
    assert result['input']['sha256'] == records[0]['previews'][1]['sha256']
    assert any(e.get('sha256') == parent['sha256'] for e in evidence['excluded'])
    _, evidence = SearchEngine(config, backend).search(mode='reference', reference=parent['path'],
        exclude_image_hashes={p['sha256'] for p in records[0]['previews']})
    assert all(r['asset_id'] != records[0]['asset_id'] for r in evidence['channel_rankings']['image'])
    with pytest.raises(ConfigError, match='only accepted'):
        SearchEngine(config, backend).search('object','combined',exclude_image_hashes={parent['sha256']})


def test_line_endings_alone_keep_embedding_contract_and_vectors(indexed):
    from local_asset_library import embedding_backend
    from local_asset_library.publication import line_ending_hashes
    config, backend, _ = indexed
    lock = config.project_root / "runtime/embedding/uv.lock"
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b"version = 1\nrevision = 3\n")
    adapter = line_ending_hashes(Path(embedding_backend.__file__))  # Never written; the other ending is simulated.

    def contract():
        return {**backend.contract, "adapter_sha256": adapter[0], "runtime_lock_sha256": file_hash(lock)}
    backend.contract = contract()
    save_json(config.output_path("data", "embeddings/capability.json"), {"contract": backend.contract,
              "contract_fingerprint": digest(backend.contract), "actual_text_and_image_inference": True,
              "reference_image_query_support": True, "test_double": True})
    assert index_pilot(config, backend)["complete"] == 120
    # A checkout may rewrite the adapter or runtime lock as CRLF (or back); inference reads the same text.
    lock.write_bytes(b"version = 1\r\nrevision = 3\r\n")
    flipped = SyntheticBackend()
    flipped.contract = {**contract(), "adapter_sha256": adapter[-1]}
    assert digest(flipped.contract) != digest(backend.contract)
    response, _ = SearchEngine(config, flipped).search("red object", "description")
    assert response["results"]
    report = index_pilot(config, flipped)
    assert report["complete"] == 120 and all(o["reused"] for o in report["outcomes"])
    assert not [c for c in flipped.calls if c[0] != "query"]
    lock.write_bytes(b"version = 1\r\nrevision = 4\r\n")
    with pytest.raises(ConfigError, match="contract mismatch"):
        SearchEngine(config, flipped, {**flipped.contract, "runtime_lock_sha256": file_hash(lock)}).search("red object", "description")
