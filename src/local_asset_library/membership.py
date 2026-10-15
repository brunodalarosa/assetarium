"""Explicit approved membership, never an unguarded full-catalog fallback."""
import json
from contextlib import closing
import re

from .catalog import read_database, digest,parse_record
from .config import ConfigError
from .publication import read_json


def membership(config):
    path = config.output_path("data", "library/membership.json")
    if path.exists():
        value = read_json(path)
        ids = value.get("asset_ids", [])
        if (value.get("schema_version") != 1 or (not ids and not config.sources_registry) or len(ids) != len(set(ids))
                or any(not isinstance(i, str) or not re.fullmatch(r"asset_[0-9a-f]{32}", i) for i in ids)
                or value.get("fingerprint") != digest(ids)):
            raise ConfigError("Configured library membership is invalid")
        return value
    manifest = json.loads(config.output_path("data", "pilot/selection-manifest.json").read_text(encoding="utf-8"))
    ids = [a["asset_id"] for a in manifest["assets"]]
    if len(ids) != 40 or len(set(ids)) != 40:
        raise ConfigError("Require the existing 40-asset pilot or configured membership")
    return {"schema_version": 1, "asset_ids": ids, "fingerprint": digest(ids), "scope": "pilot"}


def records(config):
    scope = membership(config)
    with closing(read_database(config)) as db:
        available = {r[0]: parse_record(*r) for r in db.execute("SELECT asset_id,pack_id,name,CAST(record AS BLOB) FROM assets")}
    if any(i not in available for i in scope["asset_ids"]):
        raise ConfigError("Membership/catalog mismatch")
    from .sources import visible
    return visible(config, [available[i] for i in scope["asset_ids"]])
