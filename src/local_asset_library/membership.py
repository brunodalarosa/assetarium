"""Explicit approved membership, never an unguarded full-catalog fallback."""
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
    raise ConfigError("Library membership is missing; refresh the library to create it")


def records(config):
    scope = membership(config)
    with closing(read_database(config)) as db:
        available = {r[0]: parse_record(*r) for r in db.execute("SELECT asset_id,pack_id,name,CAST(record AS BLOB) FROM assets")}
    if any(i not in available for i in scope["asset_ids"]):
        raise ConfigError("Membership/catalog mismatch")
    from .sources import visible
    return visible(config, [available[i] for i in scope["asset_ids"]])
