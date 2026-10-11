"""Step 2 inventory and keyword baseline. Never imports or executes model files."""

from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import sqlite3
import struct
import time
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

from .config import Config, ConfigError

SOURCE_ID = "playful-lowpoly-v1"
SCANNER_VERSION = "inventory-v1"
MODELS = {".obj", ".fbx", ".glb", ".gltf", ".blend", ".dae", ".stl"}
UNSUPPORTED = {".3ds", ".ply", ".usd", ".usda", ".usdc", ".usdz", ".max", ".ma", ".mb", ".lwo", ".vox"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".tga", ".bmp", ".dds", ".exr", ".hdr"}
EXPORT_DIRS = {
    "FBX format": {".fbx"}, "OBJ format": {".obj"}, "GLB format": {".glb"},
    "GLTF format": {".glb", ".gltf"}, "DAE format": {".dae"}, "STL format": {".stl"},
    "FBX": {".fbx"}, "OBJ": {".obj"}, "Blends": {".blend"},
}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


def asset_id(pack, identity):
    # v1: JSON tuple, UTF-8, SHA-256, first 128 bits; no absolute paths or file hashes.
    return "asset_" + digest([SOURCE_ID, pack, identity])[:32]


def file_hash(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        result.update(chunk)
    return result.hexdigest()


def check_fts5(connection):
    try:
        connection.execute("CREATE VIRTUAL TABLE temp.fts_probe USING fts5(value)")
        connection.execute("INSERT INTO fts_probe VALUES ('working')")
        if connection.execute("SELECT count(*) FROM fts_probe WHERE fts_probe MATCH 'working'").fetchone()[0] != 1:
            raise sqlite3.OperationalError("FTS5 MATCH probe failed")
        connection.execute("DROP TABLE temp.fts_probe")
    except sqlite3.Error as exc:
        raise ConfigError(f"Python SQLite {sqlite3.sqlite_version} cannot run FTS5: {exc}. Fix the project Python build; no fallback index is used.") from exc


def walk_source(config):
    """Sorted inventory; directory links are visible exclusions, never traversed."""
    rows = []
    for directory, dirs, files in os.walk(config.source_root, followlinks=False):
        dirs.sort()
        for name in list(dirs):
            path = Path(directory) / name
            if path.is_symlink() or path.is_junction():
                dirs.remove(name)
                rows.append({"path": path.relative_to(config.source_root).as_posix(), "role": "boundary_exclusion",
                             "status": "excluded_directory_link", "sha256": None, "size": None, "mtime_ns": None})
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(config.source_root).as_posix()
            row = {"path": relative, "role": "unclassified", "status": "available"}
            try:
                source = config.source_file(relative)
                before = source.stat()
                with config.open_source(relative) as stream:
                    row["sha256"] = file_hash(stream)
                after = source.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ConfigError(f"Source changed while hashing: {relative}")
                row.update(size=after.st_size, mtime_ns=after.st_mtime_ns)
            except (ConfigError, OSError) as exc:
                row.update(status="rejected", error=str(exc), sha256=None, size=None, mtime_ns=None)
            rows.append(row)
    return sorted(rows, key=lambda row: row["path"])


def snapshot(rows):
    return [{key: row.get(key) for key in ("path", "sha256", "size", "mtime_ns")} for row in rows]


def read_text(config, path):
    with config.open_source(path) as stream:
        return stream.read().decode("utf-8-sig", errors="replace")


def classify(path):
    p = PurePosixPath(path)
    suffix = p.suffix.lower()
    folders = {part.lower() for part in p.parts[:-1]}
    if suffix in MODELS:
        return "model"
    if suffix in UNSUPPORTED:
        return "unsupported_candidate"
    if suffix == ".zip":
        return "archive"
    if suffix in IMAGES:
        if "textures" in folders or "texture" in folders:
            return "texture"
        if folders & {"previews", "isometric", "side"}:
            return "individual_preview"
        if p.stem.lower().startswith("preview"):
            return "pack_contact_sheet"
        if p.stem.lower().startswith("sample"):
            return "pack_sample"
        return "unclassified_image"
    if suffix == ".mtl":
        return "material"
    if suffix in {".bin"}:
        return "buffer"
    if "license" in p.name.lower() or suffix == ".url":
        return "license_source_evidence"
    if suffix in {".html", ".txt", ".md"}:
        return "documentation"
    return "unclassified"


def export_slot(pack_relative):
    p = PurePosixPath(pack_relative)
    matches = [(i, part) for i, part in enumerate(p.parts[:-1]) if part in EXPORT_DIRS and p.suffix.lower() in EXPORT_DIRS[part]]
    if len(matches) != 1:
        return None
    index, directory = matches[0]
    anchor = PurePosixPath(*p.parts[:index]).as_posix()
    key = PurePosixPath(*p.parts[index + 1:]).with_suffix("").as_posix()
    return anchor, directory, key


def group_models(pack, model_rows):
    """Only equal full relative-name sets in sibling, format-specific directories."""
    slots = defaultdict(lambda: defaultdict(list))
    for row in model_rows:
        slot = export_slot(row["path"].split("/", 1)[1])
        if slot:
            anchor, directory, key = slot
            slots[anchor][directory].append((key, row))
    approved = {}
    for anchor, directories in sorted(slots.items()):
        sets = defaultdict(list)
        for directory, entries in directories.items():
            keys = tuple(sorted(key for key, _ in entries))
            # Duplicate logical keys in an export tree are insufficient evidence.
            if len(keys) == len(set(keys)):
                sets[keys].append(directory)
        for keys, dirs in sets.items():
            if len(dirs) >= 2:
                evidence = {"method": "sibling-export-manifest-v1", "anchor": anchor,
                            "directories": sorted(dirs), "matching_name_count": len(keys),
                            "name_manifest_sha256": digest(keys),
                            "basis": "Known format-specific sibling folders; identical complete relative stem sets. Geometry equivalence not inspected."}
                for directory in dirs:
                    for key, row in directories[directory]:
                        identity = (PurePosixPath(anchor) / "@exports" / key).as_posix()
                        approved[row["path"]] = (identity, evidence)
    groups = defaultdict(list)
    evidence_by_identity = {}
    for row in model_rows:
        identity, evidence = approved.get(row["path"], (row["path"].split("/", 1)[1], {
            "method": "separate-file-v1", "basis": "No sufficient export-layout evidence; retained independently."}))
        groups[identity].append(row)
        evidence_by_identity[identity] = evidence
    return [(identity, sorted(files, key=lambda f: f["path"]), evidence_by_identity[identity])
            for identity, files in sorted(groups.items())]


def dependencies(config, row, inventory):
    """Measured text/GLB references only; binary FBX/Blend remain uninspected."""
    path = row["path"]
    extension = PurePosixPath(path).suffix.lower()
    references, issues = [], []
    if extension in {".fbx", ".blend"}:
        return [], ["Binary material/dependency inspection pending step 3"], "pending"
    try:
        if extension in {".obj", ".mtl"}:
            text = read_text(config, path)
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                command, _, value = line.partition(" ")
                if command == "mtllib":
                    # An exact existing filename (including spaces) wins; otherwise OBJ permits several names.
                    direct = (PurePosixPath(path).parent / value).as_posix()
                    refs = [value] if direct in inventory else [v.strip('"') for v in shlex.split(value, posix=False)]
                    references.extend((ref, "material", "OBJ mtllib") for ref in refs)
                elif command.lower().startswith("map_") or command.lower() in {"bump", "disp", "decal", "refl"}:
                    refs = shlex.split(value, posix=True)
                    if refs:
                        # Options have variable arity; expose them rather than guessing filename boundaries.
                        if value.startswith("-"):
                            issues.append(f"Unresolved MTL map options: {line}")
                        else:
                            references.append((value.strip('"'), "texture", f"MTL {command}"))
        elif extension in {".gltf", ".glb"}:
            if extension == ".gltf":
                document = json.loads(read_text(config, path))
            else:
                with config.open_source(path) as stream:
                    header = stream.read(12)
                    if len(header) != 12:
                        raise ValueError("Short GLB header")
                    magic, version, total = struct.unpack("<4sII", header)
                    if magic != b"glTF" or version != 2 or total != row["size"]:
                        raise ValueError("Invalid GLB v2 header/length")
                    chunk = stream.read(8)
                    if len(chunk) != 8:
                        raise ValueError("Missing GLB JSON chunk")
                    size, kind = struct.unpack("<I4s", chunk)
                    if kind != b"JSON" or size > row["size"] - 20:
                        raise ValueError("Invalid GLB JSON chunk")
                    document = json.loads(stream.read(size).decode("utf-8").rstrip("\x00 "))
            for section, role in (("buffers", "buffer"), ("images", "texture")):
                for item in document.get(section, []):
                    uri = item.get("uri")
                    if uri and not uri.startswith("data:"):
                        references.append((uri, role, f"glTF {section}.uri"))
        elif extension == ".dae":
            # XML parsing resolves no external entities. No scripts or model importers run.
            document = ET.fromstring(read_text(config, path))
            for image in document.iter():
                if image.tag.split("}")[-1] == "image":
                    for child in image:
                        if child.tag.split("}")[-1] == "init_from" and child.text:
                            references.append((child.text.strip(), "texture", "DAE image/init_from"))
    except (ValueError, OSError, ET.ParseError) as exc:
        issues.append(f"Dependency parse failed: {exc}")
    result = []
    for reference, role, evidence in references:
        reference = unquote(reference).replace("\\", "/")
        dep = {"reference": reference, "role": role, "evidence": evidence, "from": path,
               "path": None, "sha256": None, "status": "missing"}
        try:
            if urlsplit(reference).scheme or reference.startswith(("/", "\\")):
                raise ConfigError("Absolute or remote dependency is not permitted")
            # Parent references are legitimate in formats, but must resolve inside the source root.
            target = (config.source_file(path).parent / reference).resolve()
            if not target.is_relative_to(config.source_root) or target == config.source_root:
                raise ConfigError("Dependency escapes source root")
            relative = target.relative_to(config.source_root).as_posix()
            dep["path"] = relative
            if relative in inventory and inventory[relative]["status"] == "available":
                config.source_file(relative)  # Apply reserved-name and resolved-link policy too.
                dep.update(status="available", sha256=inventory[relative]["sha256"])
        except (ConfigError, ValueError, OSError) as exc:
            dep.update(status="rejected", error=str(exc))
        result.append(dep)
    state = "partial" if issues else "references_parsed"
    return result, issues, state


def archive_evidence(config, row, inventory, packs):
    """Verify every non-directory ZIP member against an extracted pack; never extract."""
    p = PurePosixPath(row["path"])
    if p.stem not in packs:
        return {"status": "excluded_unmatched_archive", "reason": "No extracted pack with archive stem; not a model candidate"}
    evidence = {"status": "excluded_archive_needs_review", "pack": p.stem, "members": 0, "verified": 0, "issues": []}
    try:
        with config.open_source(row["path"]) as stream, zipfile.ZipFile(stream) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                evidence["members"] += 1
                name = member.filename.replace("\\", "/")
                if name.startswith("/") or ".." in PurePosixPath(name).parts:
                    evidence["issues"].append({"member": name, "reason": "unsafe member path"})
                    continue
                target = p.stem + "/" + name
                extracted = inventory.get(target)
                if not extracted or extracted.get("size") != member.file_size:
                    evidence["issues"].append({"member": name, "reason": "missing extracted counterpart or size mismatch"})
                    continue
                # Cap malicious expansion at the already-hashed extracted file's length.
                with archive.open(member) as content:
                    same = file_hash(content) == extracted["sha256"]
                if same:
                    evidence["verified"] += 1
                else:
                    evidence["issues"].append({"member": name, "reason": "hash mismatch"})
        if evidence["members"] > 0 and evidence["members"] == evidence["verified"]:
            evidence["status"] = "excluded_verified_duplicate"
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        evidence["issues"].append({"reason": str(exc)})
    return evidence


def license_evidence(config, pack, inventory):
    paths = [path for path, row in inventory.items() if row["role"] == "license_source_evidence"
             and (path.startswith(pack + "/") or path == "README-licenses.txt") and row["status"] == "available"]
    result = []
    for path in sorted(paths):
        text = read_text(config, path)
        if path == "README-licenses.txt":
            # Keep the collection claim and the particular pack's download/source block.
            blocks = re.split(r"(?m)(?=^\d+\. )", text)
            relevant = [block.split("\n\n", 1)[0] for block in blocks if pack + ".zip" in block]
            text = blocks[0] + "\n" + "\n".join(relevant) + ("\n" + text[text.find("Note:"):] if "Note:" in text else "")
        # Shared README is collection-maintainer evidence, not a bundled author license.
        result.append({"path": path, "sha256": inventory[path]["sha256"],
                       "kind": "collection_note" if path == "README-licenses.txt" else "supplied_pack_file",
                       "license_identifier": "CC0-1.0" if re.search(r"\bCC0\b|Creative Commons Zero", text, re.I) else "unknown",
                       "excerpt": text[:2400], "urls": re.findall(r"https?://[^\s<>\"']+", text),
                       "verification": "local supplied evidence; web/license interpretation not performed"})
    return result


def build_inventory(config):
    rows = walk_source(config)
    inventory = {row["path"]: row for row in rows}
    for row in rows:
        if row["role"] != "boundary_exclusion":
            row["role"] = classify(row["path"])
    packs = sorted({row["path"].split("/")[0] for row in rows
                    if "/" in row["path"] and row["role"] in {"model", "unsupported_candidate"}})
    assets, ambiguities = [], []
    for pack in packs:
        candidates = [row for row in rows if row["path"].startswith(pack + "/") and row["role"] in {"model", "unsupported_candidate"}]
        license_rows = license_evidence(config, pack, inventory)
        for identity, files, grouping in group_models(pack, candidates):
            name = PurePosixPath(files[0]["path"]).stem
            asset = {"schema_version": 1, "asset_id": asset_id(pack, identity), "source_id": SOURCE_ID,
                     "pack_id": pack, "source_relative_identity": identity, "display_name": name,
                     "availability": "available" if any(f["status"] == "available" for f in files) else "missing",
                     "files": [{"path": f["path"], "format": PurePosixPath(f["path"]).suffix[1:].lower(),
                                "sha256": f["sha256"], "availability": f["status"]} for f in files],
                     "grouping": {"evidence": [grouping], "unresolved_ambiguities": [], "geometry_equivalence": "unverified"},
                     "dependencies": [], "dependency_inspection": [], "previews": [], "variants": [],
                     "technical": None, "description": None, "caption_provenance": None, "embeddings": [],
                     "owner_overlay": {}, "license_evidence": license_rows,
                     "processing": {"inventory": "complete", "inspection": "pending", "previews": "pending",
                                    "caption": "pending", "embeddings": "pending"},
                     "provenance": {"scanner": SCANNER_VERSION}}
            ranking = {"glb": 0, "gltf": 1, "obj": 2, "fbx": 3, "dae": 4, "blend": 5, "stl": 6}
            usable = [f for f in asset["files"] if f["availability"] == "available" and "." + f["format"] in MODELS]
            asset["primary_inspection_path"] = min(usable, key=lambda f: (ranking[f["format"]], f["path"]))["path"] if usable else None
            if not usable:
                asset["processing"]["inspection"] = "unsupported"
            visited = set()
            pending = [f for f in files if f["status"] == "available"]
            while pending:
                file = pending.pop(0)
                if file["path"] in visited:
                    continue
                visited.add(file["path"])
                deps, issues, state = dependencies(config, file, inventory)
                asset["dependency_inspection"].append({"path": file["path"], "method": "reference-parser-v1", "status": state, "issues": issues})
                asset["dependencies"].extend(deps)
                for dep in deps:
                    if dep["status"] == "available" and dep["role"] == "material":
                        pending.append(inventory[dep["path"]])
            # Match exact names only in recognized preview trees at the matching export anchor.
            anchors = {export_slot(f["path"].split("/", 1)[1])[0] for f in files if export_slot(f["path"].split("/", 1)[1])}
            for preview in rows:
                p = PurePosixPath(preview["path"])
                exact_name = p.stem == name
                directional = p.parent.name == "Isometric" and p.stem in {name + "_" + direction for direction in ("NE", "NW", "SE", "SW")}
                if preview["role"] != "individual_preview" or preview["status"] != "available" or p.parts[0] != pack or not (exact_name or directional):
                    continue
                anchor = PurePosixPath(*p.parts[1:-2]).as_posix()
                if any(a in {anchor, (PurePosixPath(anchor) / "Models").as_posix()} for a in anchors):
                    asset["previews"].append({"source_path": preview["path"], "sha256": preview["sha256"],
                                              "view_label": p.parent.name + ("_" + p.stem.rsplit("_", 1)[1] if directional else ""),
                                              "origin": "supplied", "association": "exact stem with directional suffix in Isometric layout" if directional else "exact stem under pack preview layout"})
            asset["provenance"]["inventory_fingerprint"] = digest(asset["files"])
            assets.append(asset)
    # Never merge remaining same names; report within-pack collisions and cross-pack repeated names.
    by_name = defaultdict(list)
    for asset in assets:
        by_name[asset["display_name"].casefold()].append(asset)
    for name, matching in sorted(by_name.items()):
        if len(matching) > 1:
            case = {"name": name, "asset_ids": sorted(a["asset_id"] for a in matching),
                    "reason": "same_name_separate_identity", "review": "No equivalence implied, including across packs"}
            ambiguities.append(case)
            for asset in matching:
                asset["grouping"]["unresolved_ambiguities"].append(case)
    # Variants are filename suggestions, not verified visual relationships, and never merged.
    for asset in assets:
        parts = re.split(r"[-_]", asset["display_name"])
        if len(parts) > 1:
            base = parts[0].casefold()
            related = [a for a in assets if a["pack_id"] == asset["pack_id"] and a["asset_id"] != asset["asset_id"]
                       and a["grouping"]["evidence"][0].get("anchor") == asset["grouping"]["evidence"][0].get("anchor")
                       and re.split(r"[-_]", a["display_name"])[0].casefold() == base]
            asset["variants"] = [{"asset_id": a["asset_id"], "relationship": "filename_variant_candidate",
                                  "evidence": f"Shared filename prefix {parts[0]!r}; unreviewed"} for a in sorted(related, key=lambda a: a["asset_id"])]
    archives = []
    for row in rows:
        if row["role"] == "archive" and row["status"] == "available":
            evidence = archive_evidence(config, row, inventory, packs)
            row["archive_evidence"] = evidence
            row["catalog_status"] = evidence["status"]
            archives.append({"path": row["path"], **evidence})
        else:
            row["catalog_status"] = row["status"] if row["status"] != "available" else row["role"]
    assets.sort(key=lambda a: (a["pack_id"], a["source_relative_identity"]))
    return rows, assets, ambiguities, archives


def search_text(asset):
    name = asset["display_name"]
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return " ".join([name, spaced, asset["pack_id"], asset["source_relative_identity"],
                     " ".join(f["path"] for f in asset["files"])])


def write_database(config, rows, assets, metadata):
    path = config.output_path("data", "catalog.sqlite")
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        check_fts5(db)
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, 1}:
            raise ConfigError(f"Unknown SQLite schema version: {version}")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, pack_id TEXT NOT NULL,
                identity TEXT NOT NULL, name TEXT NOT NULL, availability TEXT NOT NULL, record TEXT NOT NULL,
                UNIQUE(source_id,pack_id,identity));
            CREATE TABLE IF NOT EXISTS inventory (path TEXT PRIMARY KEY, role TEXT NOT NULL, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(asset_id),
                format TEXT NOT NULL, sha256 TEXT, availability TEXT NOT NULL);
            CREATE VIRTUAL TABLE IF NOT EXISTS asset_fts USING fts5(asset_id UNINDEXED, keywords, tokenize='unicode61');
            PRAGMA user_version=1;
        """)
        # Rebuild only step 2 inventory; refuse to erase downstream work/corrections.
        for (payload,) in db.execute("SELECT record FROM assets"):
            old = json.loads(payload)
            if old.get("owner_overlay") or old.get("technical") or old.get("description") or old.get("embeddings"):
                raise ConfigError("Catalog contains later-stage work or owner corrections; step 2 scan cannot overwrite it")
        db.execute("DELETE FROM files")
        db.execute("DELETE FROM assets")
        db.execute("DELETE FROM inventory")
        db.execute("DELETE FROM asset_fts")
        db.execute("DELETE FROM metadata")
        db.executemany("INSERT INTO metadata VALUES (?,?)", [(k, encoded(v)) for k, v in sorted(metadata.items())])
        db.executemany("INSERT INTO inventory VALUES (?,?,?)", [(r["path"], r["role"], encoded(r)) for r in rows])
        for asset in assets:
            db.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?)", (asset["asset_id"], asset["source_id"], asset["pack_id"],
                       asset["source_relative_identity"], asset["display_name"], asset["availability"], encoded(asset)))
            db.executemany("INSERT INTO files VALUES (?,?,?,?,?)", [(f["path"], asset["asset_id"], f["format"], f["sha256"], f["availability"]) for f in asset["files"]])
            db.execute("INSERT INTO asset_fts VALUES (?,?)", (asset["asset_id"], search_text(asset)))
    return path


def read_database(config):
    path = config.output_path("data", "catalog.sqlite")
    if not path.is_file():
        raise ConfigError("Catalog missing; run scan first")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    metadata = dict((key, json.loads(value)) for key, value in db.execute("SELECT key,value FROM metadata"))
    if metadata.get("source_root") != str(config.source_root) or metadata.get("source_id") != SOURCE_ID:
        db.close()
        raise ConfigError("Catalog source does not match configuration; run scan for this source")
    return db


def query(config, text, limit=5):
    if len(text) > 256:
        raise ConfigError("Keyword query must be at most 256 characters")
    if not 1 <= limit <= 20:
        raise ConfigError("Search limit must be between 1 and 20")
    tokens = re.findall(r"[^\W_]+", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text), flags=re.UNICODE)
    if not tokens:
        return []
    # Treat input as literal terms, never user-supplied FTS operators.
    match = " AND ".join('"' + term.replace('"', '""') + '"' for term in tokens)
    result = []
    with closing(read_database(config)) as db:
        for (payload,) in db.execute("""SELECT a.record FROM asset_fts f JOIN assets a ON a.asset_id=f.asset_id
            WHERE asset_fts MATCH ? AND a.availability='available' ORDER BY bm25(asset_fts), a.asset_id""", (match,)):
            asset = json.loads(payload)
            paths = []
            for file in asset["files"]:
                try:
                    actual = config.source_file(file["path"])
                    if file["availability"] == "available":
                        paths.append({"format": file["format"], "path": str(actual)})
                except (ConfigError, OSError):
                    pass
            if paths:
                preview_reference = None
                preview_root = None
                for preview in asset["previews"]:
                    try:
                        if preview.get("source_path"):
                            config.source_file(preview["source_path"])
                            preview_reference, preview_root = preview["source_path"], "source"
                        elif preview.get("path", "").startswith("data/"):
                            actual_preview = config.output_path("data", preview["path"].removeprefix("data/"))
                            if actual_preview.is_file():
                                preview_reference, preview_root = preview["path"], "project"
                        if preview_reference:
                            break
                    except (ConfigError, OSError):
                        continue
                result.append({"asset_id": asset["asset_id"], "name": asset["display_name"], "pack": asset["pack_id"],
                               "files": paths, "preview": preview_reference, "preview_root": preview_root,
                               "availability": "available", "matching_channels": ["filename_keyword"]})
            if len(result) == limit:
                break
    return result


def compact_search_result(text, results):
    result = {"query": text, "results": list(results), "truncated": False,
              "character_cap": 6000, "serialized_characters": 0, "estimated_tokens": 0,
              "token_estimate_method": "ceil(serialized characters / 4); heuristic, not a tokenizer"}
    while True:
        # Character and token fields are included in their own serialized size.
        for _ in range(8):
            size = len(encoded(result))
            result.update(serialized_characters=size, estimated_tokens=(size + 3) // 4)
        if len(encoded(result)) <= result["character_cap"] or not result["results"]:
            return result
        result["results"].pop()
        result["truncated"] = True


def detail(config, identifier):
    with closing(read_database(config)) as db:
        row = db.execute("SELECT record FROM assets WHERE asset_id=?", (identifier,)).fetchone()
    if row is None:
        raise ConfigError("Unknown asset ID")
    return json.loads(row[0])


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def summary(rows, assets, ambiguities, archives):
    packs = []
    for pack in sorted({a["pack_id"] for a in assets}):
        selected = [a for a in assets if a["pack_id"] == pack]
        pack_rows = [r for r in rows if r["path"].startswith(pack + "/")]
        packs.append({"pack": pack, "logical_records": len(selected), "model_files": sum(len(a["files"]) for a in selected),
                      "alternate_files": sum(max(0, len(a["files"]) - 1) for a in selected),
                      "assets_with_previews": sum(bool(a["previews"]) for a in selected),
                      "missing_previews": sum(not a["previews"] for a in selected),
                      "formats": dict(sorted(Counter(f["format"] for a in selected for f in a["files"]).items())),
                      "file_roles": dict(sorted(Counter(r["role"] for r in pack_rows).items())),
                      "dependency_references": sum(len(a["dependencies"]) for a in selected),
                      "dependency_issues": sum(d["status"] != "available" for a in selected for d in a["dependencies"]),
                      "dependency_parser_issues": sum(bool(i["issues"]) and i["status"] != "pending" for a in selected for i in a["dependency_inspection"]),
                      "bundled_license_files": sorted({e["path"] for a in selected for e in a["license_evidence"] if e["kind"] == "supplied_pack_file" and e["license_identifier"] != "unknown"}),
                      "ambiguous_records": sum(bool(a["grouping"]["unresolved_ambiguities"]) for a in selected),
                      "unsupported_candidates": sum(a["processing"]["inspection"] == "unsupported" for a in selected)})
    return {"scanner_version": SCANNER_VERSION, "sqlite_version": sqlite3.sqlite_version, "fts5": True,
            "logical_records": len(assets), "model_files": sum(len(a["files"]) for a in assets),
            "alternate_files": sum(max(0, len(a["files"]) - 1) for a in assets), "inventory_entries": len(rows),
            "packs": packs, "ambiguities": ambiguities, "archives": archives,
            "unsupported_candidates": [a["asset_id"] for a in assets if a["processing"]["inspection"] == "unsupported"],
            "dependency_issues": [{"asset_id": a["asset_id"], **d} for a in assets for d in a["dependencies"] if d["status"] != "available"],
            "unclassified_files": [r["path"] for r in rows if r["role"].startswith("unclassified")],
            "limitations": ["Export-layout grouping is provenance evidence, not geometry verification.",
                            "Binary FBX/Blend dependencies pending inspection; embedded textures are not extracted.",
                            "Variant links are unreviewed filename suggestions; unknown physical scale remains unknown.",
                            "No rendered views, captions, embeddings, or license web verification.",
                            "Identity renames/grouping-policy changes require explicit migration; no automatic rename claim."]}


def scan(config):
    started = time.perf_counter()
    with sqlite3.connect(":memory:") as db:
        check_fts5(db)
    rows, assets, ambiguities, archives = build_inventory(config)
    baseline = snapshot(rows)
    # Second full read before publishing: byte hashes and sizes plus modification times.
    after = snapshot(walk_source(config))
    if baseline != after:
        raise ConfigError("Source changed during scan; catalog was not published")
    fingerprint = digest([{k: r[k] for k in ("path", "sha256", "size")} for r in baseline])
    metadata = {"schema_version": 1, "scanner_version": SCANNER_VERSION, "source_id": SOURCE_ID,
                "source_root": str(config.source_root), "source_fingerprint": fingerprint,
                "logical_fingerprint": digest(assets), "scan_utc": datetime.now(timezone.utc).isoformat()}
    database = write_database(config, rows, assets, metadata)
    report = summary(rows, assets, ambiguities, archives)
    report.update(source_fingerprint=fingerprint, logical_fingerprint=metadata["logical_fingerprint"],
                  elapsed_seconds=round(time.perf_counter() - started, 3))
    save_json(config.output_path("data", "reports/catalog-summary.json"), report)
    save_json(config.output_path("data", "evidence/source-baseline.json"), baseline)
    save_json(config.output_path("data", "evidence/scan-immutability.json"), {
        "verified": True, "entries": len(baseline), "method": "Two complete read-only SHA-256/size/mtime inventories, including ZIPs; identical before catalog publication",
        "source_fingerprint": fingerprint, "scan_utc": metadata["scan_utc"],
        "scope": "All traversed files; directory links excluded. No claim about access times or external concurrent changes after verification."})
    return {"catalog": str(database), "logical_records": len(assets), "source_fingerprint": fingerprint,
            "logical_fingerprint": metadata["logical_fingerprint"], "source_unchanged": True,
            "elapsed_seconds": report["elapsed_seconds"],
            "summary": str(config.output_path("data", "reports/catalog-summary.json"))}


def verify_source(config):
    baseline_path = config.output_path("data", "evidence/source-baseline.json")
    if not baseline_path.is_file():
        raise ConfigError("Source baseline missing; run scan first")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = snapshot(walk_source(config))
    before = {r["path"]: r for r in baseline}
    after = {r["path"]: r for r in current}
    changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    result = {"verified": not changed, "entries_before": len(baseline), "entries_after": len(current),
              "changed_paths": changed, "method": "Full SHA-256/size/mtime comparison with scan baseline",
              "verified_utc": datetime.now(timezone.utc).isoformat()}
    save_json(config.output_path("data", "evidence/source-verification.json"), result)
    if changed:
        raise ConfigError(f"Source differs from baseline in {len(changed)} entries; see source-verification.json")
    return result


def pilot(config, selection_path):
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    with closing(read_database(config)) as db:
        assets = [json.loads(row[0]) for row in db.execute("SELECT record FROM assets ORDER BY pack_id,identity")]
        metadata = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM metadata")}
    lookup = {(a["pack_id"], a["source_relative_identity"]): a for a in assets}
    chosen = []
    for entry in selection["assets"]:
        key = (entry["pack"], entry["identity"])
        if key not in lookup:
            raise ConfigError(f"Pilot selection is absent: {key}")
        asset = lookup[key]
        for f in asset["files"]:
            config.source_file(f["path"])
        chosen.append({"asset_id": asset["asset_id"], "pack": asset["pack_id"], "identity": asset["source_relative_identity"],
                       "name": asset["display_name"], "rationale": entry["rationale"], "files": asset["files"],
                       "dependencies": asset["dependencies"], "previews": asset["previews"],
                       "primary_inspection_path": asset["primary_inspection_path"]})
    counts = Counter(a["pack"] for a in chosen)
    if len(chosen) != 40 or len({a["asset_id"] for a in chosen}) != 40 or len(counts) != 8 or set(counts.values()) != {5}:
        raise ConfigError("Pilot must contain 40 distinct logical assets: five from each of eight packs")
    manifest = {"schema_version": 1, "selection_version": selection["selection_version"],
                "selection_sha256": digest(selection), "source_fingerprint": metadata["source_fingerprint"],
                "rationale": selection["rationale"], "assets": chosen,
                "coverage": {"by_pack": dict(sorted(counts.items())),
                             "formats": sorted({f["format"] for a in chosen for f in a["files"]}),
                             "with_previews": sum(bool(a["previews"]) for a in chosen),
                             "missing_previews": sum(not a["previews"] for a in chosen),
                             "with_dependencies": sum(bool(a["dependencies"]) for a in chosen)}}
    path = config.output_path("data", "pilot/selection-manifest.json")
    save_json(path, manifest)
    return {"manifest": str(path), "assets": len(chosen), "coverage": manifest["coverage"], "selection_sha256": manifest["selection_sha256"]}
