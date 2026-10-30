from contextlib import closing
import json
from pathlib import Path
import sqlite3
import struct
import subprocess
import zipfile

import pytest

from local_asset_library.catalog import (
    asset_id, build_inventory, check_fts5, compact_search_result, detail, encoded, pilot, query, scan, verify_source,
)
from local_asset_library.config import Config, ConfigError


@pytest.fixture
def catalog_config(tmp_path):
    root, source = tmp_path / "project", tmp_path / "source"
    root.mkdir()
    source.mkdir()
    return Config(root, source, None)


def put(config, path, content="fixture"):
    target = config.source_root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content if isinstance(content, bytes) else content.encode())
    return target


def exports(config, pack="pack", names=("chair", "chair-round")):
    for name in names:
        put(config, f"{pack}/Models/OBJ format/{name}.obj", f"mtllib {name}.mtl\n")
        put(config, f"{pack}/Models/OBJ format/{name}.mtl", "map_Kd Textures/palette.png\n")
        put(config, f"{pack}/Models/FBX format/{name}.fbx")
    put(config, f"{pack}/Models/OBJ format/Textures/palette.png", b"texture fixture")


def test_non_cc0_pack_readme_is_preserved_without_cc0_claim(catalog_config):
    put(catalog_config, 'licensed/Models/chair.fbx')
    put(catalog_config, 'licensed/README.md', 'Synty one-time purchase license. NOT CC0. Do not redistribute.')
    put(catalog_config, 'README-licenses.txt', 'All original packs CC0.\n1. original.zip - original pack')
    _, assets, _, _ = build_inventory(catalog_config)
    evidence = assets[0]['license_evidence']
    assert any(e['path'] == 'licensed/README.md' and 'NOT CC0' in e['excerpt'] for e in evidence)
    assert all(e['license_identifier'] == 'unknown' for e in evidence)


def test_actual_fts5_and_literal_search(catalog_config):
    with closing(sqlite3.connect(":memory:")) as db:
        check_fts5(db)
    exports(catalog_config)
    scan(catalog_config)
    results = query(catalog_config, "chair round")
    assert len(results) == 1 and results[0]["name"] == "chair-round"
    assert {f["format"] for f in results[0]["files"]} == {"obj", "fbx"}
    assert all(Path(f["path"]).is_file() for f in results[0]["files"])
    assert not query(catalog_config, 'chair OR unknown')  # OR is a literal term.
    assert not query(catalog_config, "absent submarine")
    with pytest.raises(ConfigError):
        query(catalog_config, "chair", 100)


def test_duplicate_names_and_unrelated_subdirectories(catalog_config):
    exports(catalog_config, "first", ("chair",))
    exports(catalog_config, "second", ("chair",))
    put(catalog_config, "first/unrelated/chair.obj")
    put(catalog_config, "first/other/chair.fbx")
    _, assets, ambiguities, _ = build_inventory(catalog_config)
    assert len(assets) == 4
    assert len({a["asset_id"] for a in assets}) == 4
    assert len(ambiguities) == 1
    assert len(ambiguities[0]["asset_ids"]) == 4
    assert sorted(len(a["files"]) for a in assets) == [1, 1, 2, 2]


def test_mismatched_export_manifests_do_not_merge(catalog_config):
    exports(catalog_config, names=("chair",))
    put(catalog_config, "pack/Models/FBX format/extra.fbx")
    _, assets, ambiguities, _ = build_inventory(catalog_config)
    assert len(assets) == 3
    assert all(len(a["files"]) == 1 for a in assets)
    assert ambiguities[0]["name"] == "chair"


def test_same_folder_formats_are_not_automatically_equivalent(catalog_config):
    put(catalog_config, "pack/models/chair.obj")
    put(catalog_config, "pack/models/chair.fbx")
    assert len(build_inventory(catalog_config)[1]) == 2


def test_kaykit_export_layout_groups_manifests_with_namespace(catalog_config):
    for pack in ('City', 'Platformer'):
        for folder, extension in [('fbx', 'fbx'), ('fbx(unity)', 'fbx'), ('gltf', 'gltf'), ('obj', 'obj')]:
            for color in ('blue', 'red'):
                put(catalog_config, f'KayKit/{pack}/Assets/{folder}/{color}/arch.{extension}',
                    '{"asset":{"version":"2.0"}}' if extension == 'gltf' else 'fixture')
    assets = build_inventory(catalog_config)[1]
    assert len(assets) == 4
    assert all(len(record['files']) == 4 for record in assets)
    assert len({r['source_relative_identity'] for r in assets}) == 4
    assert all(r['grouping']['geometry_equivalence'] == 'unverified' for r in assets)


def test_nested_source_licenses_do_not_leak_between_subpacks(catalog_config):
    for pack in ('City', 'Platformer'):
        put(catalog_config, f'KayKit/{pack}/Assets/gltf/arch.gltf', '{"asset":{"version":"2.0"}}')
        put(catalog_config, f'KayKit/{pack}/License.txt', 'Creative Commons Zero. ' + pack)
        put(catalog_config, f'KayKit/{pack}/More Assets.url', 'URL=https://example.invalid')
    assets = build_inventory(catalog_config)[1]
    assert len(assets) == 2
    for record in assets:
        assert len(record['license_evidence']) == 1
        assert Path(record['license_evidence'][0]['path']).parent in Path(record['files'][0]['path']).parents


def test_nested_export_names_preserve_namespace(catalog_config):
    for directory, suffix in (("OBJ format", "obj"), ("FBX format", "fbx")):
        for folder in ("kitchen", "office"):
            put(catalog_config, f"pack/Models/{directory}/{folder}/chair.{suffix}")
    _, assets, ambiguities, _ = build_inventory(catalog_config)
    assert len(assets) == 2
    assert {a["source_relative_identity"] for a in assets} == {"Models/@exports/kitchen/chair", "Models/@exports/office/chair"}
    assert len(ambiguities) == 1


def test_ids_determinism_content_changes_and_renames(catalog_config):
    exports(catalog_config)
    first = scan(catalog_config)
    second = scan(catalog_config)
    assert first["logical_fingerprint"] == second["logical_fingerprint"]
    before = build_inventory(catalog_config)[1]
    put(catalog_config, "pack/Models/FBX format/chair.fbx", "changed synthetic geometry")
    after = build_inventory(catalog_config)[1]
    assert [a["asset_id"] for a in before] == [a["asset_id"] for a in after]
    assert before[0]["files"] != after[0]["files"]
    assert asset_id("pack", "old.obj") != asset_id("pack", "new.obj")
    assert asset_id("first", "chair.obj") != asset_id("second", "chair.obj")


def test_preview_lookup_keeps_row_order_labels_and_exact_versus_directional_matches(catalog_config):
    exports(catalog_config)
    put(catalog_config, "pack/Models/OBJ format/chair_NE.obj", "v 0 0 0\n")
    for name in ("chair_SW", "chair_NE", "chair"):
        put(catalog_config, f"pack/Isometric/{name}.png")
    put(catalog_config, "pack/Previews/chair.png")
    by_name = {a["display_name"]: a for a in build_inventory(catalog_config)[1]}
    # One image is a directional view of "chair" and the exact preview of "chair_NE"; rows keep path order.
    assert [(p["source_path"], p["view_label"]) for p in by_name["chair"]["previews"]] == [
        ("pack/Isometric/chair.png", "Isometric"), ("pack/Isometric/chair_NE.png", "Isometric_NE"),
        ("pack/Isometric/chair_SW.png", "Isometric_SW"), ("pack/Previews/chair.png", "Previews")]
    assert [(p["source_path"], p["view_label"]) for p in by_name["chair_NE"]["previews"]] == [
        ("pack/Isometric/chair_NE.png", "Isometric")]


def test_variants_previews_texture_and_missing_dependency(catalog_config):
    exports(catalog_config)
    put(catalog_config, "pack/Previews/chair.png")
    put(catalog_config, "pack/Isometric/chair_NE.png")
    put(catalog_config, "pack/Preview.png")
    put(catalog_config, "pack/Models/OBJ format/chair-round.mtl", "map_Kd missing.png")
    rows, assets, _, _ = build_inventory(catalog_config)
    by_name = {a["display_name"]: a for a in assets}
    assert len(by_name["chair"]["previews"]) == 2
    assert not by_name["chair-round"]["previews"]
    assert by_name["chair-round"]["variants"][0]["asset_id"] == by_name["chair"]["asset_id"]
    assert any(d["role"] == "texture" and d["status"] == "available" for d in by_name["chair"]["dependencies"])
    assert any(d["status"] == "missing" for d in by_name["chair-round"]["dependencies"])
    assert any(r["role"] == "pack_contact_sheet" for r in rows)
    # The chair's texture is a model texture: a dependency with its evidence, not a selectable image (decision 0023).
    assert any(r["role"] == "model_dependency_image" and "map_Kd" in r["deferred_reason"] for r in rows)
    assert all(a["description"] is None and not a["embeddings"] for a in assets)


def test_zip_duplicates_and_incomplete_archives(catalog_config):
    exports(catalog_config)
    for archive_name, contents in (("pack", {"Models/FBX format/chair.fbx": "fixture"}),
                                   ("unknown", {"chair.fbx": "fixture"})):
        target = catalog_config.source_root / "zips" / f"{archive_name}.zip"
        target.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(target, "w") as archive:
            for name, value in contents.items():
                archive.writestr(name, value)
    rows, assets, _, archives = build_inventory(catalog_config)
    assert len(assets) == 2
    assert {a["status"] for a in archives} == {"excluded_verified_duplicate", "excluded_unmatched_archive"}
    assert len([r for r in rows if r["role"] == "archive"]) == 2
    # A mismatching ZIP never claims verified duplication, and is never extracted.
    with zipfile.ZipFile(catalog_config.source_root / "zips/pack.zip", "w") as archive:
        archive.writestr("../escape.obj", "x")
    evidence = build_inventory(catalog_config)[3]
    assert next(a for a in evidence if a["pack"] == "pack")["status"] == "excluded_archive_needs_review"
    assert not (catalog_config.source_root.parent / "escape.obj").exists()


def test_dependency_boundary_rejection_and_legitimate_parent(catalog_config):
    put(catalog_config, "pack/mesh.obj", "mtllib ../shared.mtl")
    put(catalog_config, "shared.mtl", "map_Kd ../../outside.png")
    assets = build_inventory(catalog_config)[1]
    deps = assets[0]["dependencies"]
    assert deps[0]["status"] == "available" and deps[0]["path"] == "shared.mtl"
    assert deps[1]["status"] == "rejected" and deps[1]["path"] is None
    with pytest.raises(ConfigError):
        catalog_config.source_file("../outside.obj")


def test_glb_external_uri_dae_and_unresolved_mtl_options(catalog_config):
    document = {"asset": {"version": "2.0"}, "images": [{"uri": "Textures/palette.png"}, {"uri": "https://example.invalid/image.png"}], "buffers": [{"uri": "missing.bin"}]}
    payload = json.dumps(document).encode()
    payload += b" " * ((-len(payload)) % 4)
    glb = struct.pack("<4sII", b"glTF", 2, len(payload) + 20) + struct.pack("<I4s", len(payload), b"JSON") + payload
    put(catalog_config, "pack/mesh.glb", glb)
    put(catalog_config, "pack/Textures/palette.png")
    put(catalog_config, "pack/mesh.dae", '<COLLADA><library_images><image><init_from>Textures/palette.png</init_from></image></library_images></COLLADA>')
    put(catalog_config, "pack/other.obj", "mtllib other.mtl")
    put(catalog_config, "pack/other.mtl", "map_Kd -s 1 1 1 palette.png")
    assets = build_inventory(catalog_config)[1]
    glb_asset = next(a for a in assets if a["source_relative_identity"] == "mesh.glb")
    assert {d["status"] for d in glb_asset["dependencies"]} == {"available", "missing", "rejected"}
    dae = next(a for a in assets if a["source_relative_identity"] == "mesh.dae")
    assert dae["dependencies"][0]["status"] == "available"
    other = next(a for a in assets if a["display_name"] == "other")
    assert any(i["issues"] for i in other["dependency_inspection"])


def test_unsupported_and_malformed_candidates_are_visible(catalog_config):
    put(catalog_config, "pack/model.ply")
    put(catalog_config, "pack/broken.glb", b"not glb")
    rows, assets, _, _ = build_inventory(catalog_config)
    assert len(assets) == 2
    assert any(r["role"] == "unsupported_candidate" for r in rows)
    assert next(a for a in assets if a["display_name"] == "model")["processing"]["inspection"] == "unsupported"
    assert next(a for a in assets if a["display_name"] == "broken")["dependency_inspection"][0]["issues"]


def test_deleted_sources_and_stale_records_excluded(catalog_config):
    target = put(catalog_config, "pack/chair.obj")
    scan(catalog_config)
    assert len(query(catalog_config, "chair")) == 1
    target.unlink()  # Synthetic fixture only.
    assert not query(catalog_config, "chair")
    with pytest.raises(ConfigError, match="differs"):
        verify_source(catalog_config)


def test_source_binding_and_later_stage_guard(catalog_config):
    put(catalog_config, "pack/chair.obj")
    scan(catalog_config)
    other = catalog_config.source_root.parent / "other"
    other.mkdir()
    with pytest.raises(ConfigError, match="does not match"):
        query(Config(catalog_config.project_root, other, None), "chair")
    database = catalog_config.output_path("data", "catalog.sqlite")
    with closing(sqlite3.connect(database)) as db, db:
        old = json.loads(db.execute("SELECT record FROM assets").fetchone()[0])
        old["owner_overlay"] = {"review": "keep"}
        db.execute("UPDATE assets SET record=?", (json.dumps(old),))
    with pytest.raises(ConfigError, match="corrections"):
        scan(catalog_config)
    assert detail(catalog_config, old["asset_id"])["owner_overlay"] == {"review": "keep"}


def test_pilot_reproducibility_and_incomplete_selection(catalog_config):
    for n in range(8):
        exports(catalog_config, f"pack{n}", tuple(f"chair-{i}" for i in range(5)))
    scan(catalog_config)
    selection = {"selection_version": "fixture-v1", "rationale": "synthetic coverage",
                 "assets": [{"pack": f"pack{n}", "identity": f"Models/@exports/chair-{i}", "rationale": "fixture"} for n in range(8) for i in range(5)]}
    path = catalog_config.project_root / "selection.json"
    path.write_text(json.dumps(selection))
    first = pilot(catalog_config, path)
    content = Path(first["manifest"]).read_bytes()
    pilot(catalog_config, path)
    assert Path(first["manifest"]).read_bytes() == content
    assert first["assets"] == 40 and first["coverage"]["with_dependencies"] == 40
    selection["assets"].pop()
    path.write_text(json.dumps(selection))
    with pytest.raises(ConfigError, match="40 distinct"):
        pilot(catalog_config, path)


def test_compact_budget_and_long_query(catalog_config):
    result = compact_search_result("chair", [{"asset_id": str(i), "files": [{"path": "x" * 1800}]} for i in range(5)])
    assert result["truncated"] and len(result["results"]) < 5
    assert len(encoded(result)) == result["serialized_characters"] <= 6000
    assert result["estimated_tokens"] <= 1500
    with pytest.raises(ConfigError, match="256"):
        query(catalog_config, "x" * 257)


def test_scanner_does_not_follow_directory_links(catalog_config):
    outside = catalog_config.project_root.parent / "outside"
    outside.mkdir()
    (outside / "secret.obj").write_text("never read")
    pack = catalog_config.source_root / "pack"
    pack.mkdir()
    link = pack / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        assert result.returncode == 0, result.stderr.decode(errors="replace")
    rows, assets, _, _ = build_inventory(catalog_config)
    assert not assets
    assert len(rows) == 1 and rows[0]["status"] == "excluded_directory_link"
    assert rows[0]["sha256"] is None
    with pytest.raises(ConfigError):
        catalog_config.source_file("pack/linked/secret.obj")


def test_windows_dependency_separators_and_shared_license_scope(catalog_config):
    put(catalog_config, "pack/mesh.obj", 'mtllib "Materials\\mesh.mtl"')
    put(catalog_config, "pack/Materials/mesh.mtl", 'map_Kd "..\\Textures\\palette.png"')
    put(catalog_config, "pack/Textures/palette.png")
    put(catalog_config, "README-licenses.txt", "All packs CC0\n1. pack.zip\nSource: https://example.invalid/pack\n\n2. other.zip\nSource: https://example.invalid/other\n")
    asset = build_inventory(catalog_config)[1][0]
    assert all(d["status"] == "available" for d in asset["dependencies"])
    assert len(asset["dependencies"]) == 2
    assert asset["license_evidence"][0]["urls"] == ["https://example.invalid/pack"]


def test_stale_status_and_missing_id(catalog_config):
    put(catalog_config, "pack/chair.obj")
    scan(catalog_config)
    with closing(sqlite3.connect(catalog_config.output_path("data", "catalog.sqlite"))) as db, db:
        db.execute("UPDATE assets SET availability='stale'")
    assert not query(catalog_config, "chair")
    with pytest.raises(ConfigError, match="Unknown"):
        detail(catalog_config, "absent")


def test_search_handles_generated_views_and_missing_view_paths(catalog_config):
    put(catalog_config, "pack/chair.obj")
    scan(catalog_config)
    image = catalog_config.output_path("data", "inspection/chair/front.png")
    image.parent.mkdir(parents=True)
    image.write_bytes(b"synthetic preview fixture")
    with closing(sqlite3.connect(catalog_config.output_path("data", "catalog.sqlite"))) as db, db:
        record = json.loads(db.execute("SELECT record FROM assets").fetchone()[0])
        record["previews"] = [{"source_path":"pack/missing.png","origin":"supplied"},
                              {"path":"data/inspection/chair/front.png","origin":"rendered"}]
        db.execute("UPDATE assets SET record=?", (json.dumps(record),))
    result = query(catalog_config, "chair")[0]
    assert result["preview"] == "data/inspection/chair/front.png" and result["preview_root"] == "project"
    image.unlink()
    assert query(catalog_config, "chair")[0]["preview"] is None
