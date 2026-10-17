"""Validated roots and the single boundary API for future stages.

These guards are application policy, not an OS sandbox. Future workers must use
them and must never accept source files as writable destinations.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PureWindowsPath
import os
import stat
import tomllib


class ConfigError(ValueError):
    """Invalid configuration or a path that crosses a project boundary."""


STORAGE_NAMES = {
    "data": "data", "models": "models", "cache": "cache",
    "logs": "logs", "scratch": "scratch", "environment": ".venv",
}


@lru_cache(maxsize=65536)
def _relative(value: str) -> Path:
    windows = PureWindowsPath(value)
    path = Path(value)
    if not value or path.is_absolute() or windows.anchor or ".." in windows.parts or ".." in path.parts:
        raise ConfigError("Path must be relative without parent traversal")
    # Prevent Windows alternate data streams and ambiguous trailing dots/spaces.
    if os.path.isreserved(value) or ":" in value or any(p.endswith((".", " ")) for p in windows.parts):
        raise ConfigError("Ambiguous Windows path")
    return path


_REPARSE_POINT = 0x400


def _inside(root: Path, relative: str) -> Path:
    candidate = root / _relative(relative)
    # Directories resolve once per pinned request (shared by many files); the
    # leaf is resolved too whenever it is a link, so escapes are still rejected.
    from .publication import request_memo
    target = request_memo(("resolved-directory", str(candidate.parent)), candidate.parent.resolve) / candidate.name
    try:
        info = os.lstat(target)
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT:
            target = target.resolve()
    except OSError:
        pass
    if target == root or not target.is_relative_to(root):
        raise ConfigError("Path escapes its permitted root")
    return target


@dataclass(frozen=True)
class Config:
    project_root: Path
    source_root: Path
    blender: Path | None
    models_root: Path | None = None
    catalog_generation: str | None = None
    sources_registry: Path | None = None
    source_key: str | None = None
    metadata_root: Path | None = None

    def source_directory(self, relative: str) -> Path:
        if self.sources_registry:
            from .sources import source_for_path
            return Path(source_for_path(self, relative)["path"])
        return self.source_root

    def source_relative(self, actual: Path, referring: str) -> str:
        root = self.source_directory(referring)
        relative = actual.relative_to(root).as_posix()
        return referring.split("/", 1)[0] + "/" + relative if self.sources_registry else relative

    def storage_root(self, area: str) -> Path:
        from .publication import request_memo
        return request_memo(("storage-root", area, str(self.project_root), str(self.models_root)),
                            lambda: self._storage_root(area))

    def _storage_root(self, area: str) -> Path:
        if area not in STORAGE_NAMES:
            raise ConfigError("Unknown output area")
        if area == "models" and self.models_root is not None:
            storage = self.models_root.resolve()
            if storage != self.models_root or not storage.is_dir():
                raise ConfigError("Shared model root changed or is missing")
        else:
            storage = (self.project_root / STORAGE_NAMES[area]).resolve()
            if not storage.is_relative_to(self.project_root) or storage == self.project_root:
                raise ConfigError("Storage escapes the repository")
        return storage

    def source_file(self, relative: str) -> Path:
        """Resolve an existing source file for reading only."""
        _relative(relative)
        if self.sources_registry:
            root = self.source_directory(relative)
            parts = relative.replace("\\", "/").split("/", 1)
            if len(parts) != 2 or "metadata-lal" in (p.casefold() for p in Path(parts[1]).parts):
                raise ConfigError("Generated metadata is not an original asset")
            target = _inside(root, parts[1])
        else:
            target = _inside(self.source_root, relative)
        if not target.is_file():
            raise ConfigError("Source file is missing or not a regular file")
        return target

    def open_source(self, relative: str):
        """No writable mode is exposed by this API."""
        return self.source_file(relative).open("rb")

    def output_path(self, area: str, relative: str) -> Path:
        _relative(relative)
        if area == "data" and self.sources_registry:
            from .sources import generated_path
            managed = generated_path(self, relative)
            if managed is not None:
                return managed
        if area == "data" and relative in {"catalog.sqlite", "embeddings/index.sqlite", "library/membership.json"}:
            from .publication import generation
            selected = self.catalog_generation or generation(self)
            if selected != "legacy":
                relative = "library/generations/" + selected + "/" + relative
        storage = self.storage_root(area)
        target = _inside(storage, relative)
        if not self.sources_registry and target.is_relative_to(self.source_root):
            raise ConfigError("Cannot write into the source collection")
        return target


def project_config_path(project_root: Path) -> Path:
    """Ignored local overrides win; the tracked example is the shared default."""
    local = Path(project_root) / "config.local.toml"
    return local if local.is_file() else Path(project_root) / "config.example.toml"


def load_project_config(project_root: Path) -> Config:
    return load_config(project_config_path(project_root), project_root)


def load_config(path: Path, project_root: Path) -> Config:
    root = project_root.resolve()
    try:
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
        managed = raw.get("schema_version") == 2 and isinstance(raw.get("sources"), dict)
        if (not managed and not isinstance(raw.get("source"), dict)) or not isinstance(raw.get("storage"), dict) or not isinstance(raw.get("tools", {}), dict):
            raise ConfigError("Configuration sections must be tables")
        if raw.get("schema_version") != 1 and not managed:
            raise ConfigError("Unsupported configuration schema")
        source = raw.get("source", {"read_only": True, "root": str(root.parent / ".lal-managed-sources")})
        if source.get("read_only") is not True:
            raise ConfigError("Source must be explicitly read-only")
        source_root = Path(source["root"])
        if not source_root.is_absolute():
            raise ConfigError("Source root must be absolute")
        source_root = source_root.resolve()
        if not managed and not source_root.is_dir():
            raise ConfigError("Source directory is missing")
        if source_root.is_relative_to(root) or root.is_relative_to(source_root):
            raise ConfigError("Source and repository roots must not overlap")
        storage_settings = dict(raw["storage"])
        model_setting = storage_settings.get("models")
        models_root = None
        if model_setting != "models":
            if not isinstance(model_setting, str):
                raise ConfigError("Model root must be an absolute directory")
            candidate = Path(model_setting)
            windows = PureWindowsPath(model_setting)
            if (not candidate.is_absolute() or ".." in windows.parts or ".." in candidate.parts
                    or windows.drive.startswith("\\\\") or model_setting.startswith("\\\\")
                    or any(os.path.isreserved(p) or ":" in p or p.endswith((".", " "))
                           for p in windows.parts[1:])):
                raise ConfigError("Invalid shared model root")
            models_root = candidate.resolve()
            if not models_root.is_dir():
                raise ConfigError("Shared model directory is missing")
            if any(models_root.is_relative_to(other) or other.is_relative_to(models_root)
                   for other in (root, source_root)):
                raise ConfigError("Shared model root must not overlap source or repository")
            storage_settings["models"] = "models"
        if storage_settings != STORAGE_NAMES:
            raise ConfigError("Storage must use the fixed ignored project directories")
        blender = raw.get("tools", {}).get("blender")
        registry = None
        if managed:
            if raw["sources"].get("registry") != "data/library/sources.json":
                raise ConfigError("Sources registry must use data/library/sources.json")
            registry = _inside(root, "data/library/sources.json")
        config = Config(root, source_root, Path(blender) if blender else None, models_root,
                        sources_registry=registry)
        for area in STORAGE_NAMES:
            config.output_path(area, "boundary-check")
        return config
    except (KeyError, TypeError, OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Invalid configuration: {exc}") from exc
