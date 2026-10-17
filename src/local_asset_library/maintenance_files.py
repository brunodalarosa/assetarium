"""Contained, manifest-driven removal of explicitly retired generated files."""
import os
from pathlib import Path

from .config import ConfigError
from .publication import verified_hash


def contained(root, path):
    root, path = Path(root).absolute(), Path(path).absolute()
    if root.resolve() != root or path == root or not path.is_relative_to(root):
        raise ConfigError('Cleanup target is outside the approved generated-data root')
    current = path
    while current != root:
        if current.is_symlink() or current.is_junction() or current.resolve() != current:
            raise ConfigError('Cleanup refuses links or redirected paths: ' + str(current))
        current = current.parent
    if root.is_symlink() or root.is_junction():
        raise ConfigError('Cleanup root is a link')
    return path


def tree_files(root, target):
    """Validate an entire tree before removing any file; never follow links."""
    target = contained(root, target)
    if target.is_file():
        return [target]
    if not target.is_dir():
        raise ConfigError('Cleanup target is missing: ' + str(target))
    result = []
    def fail(exc):
        raise exc
    for directory, dirs, files in os.walk(target, followlinks=False, onerror=fail):
        for name in dirs:
            contained(root, Path(directory) / name)
        for name in files:
            result.append(contained(root, Path(directory) / name))
    return sorted(result)


def manifest(root, targets):
    files = sorted({path for target in targets for path in tree_files(root, target)})
    return [{'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
             'sha256': verified_hash(path, fresh=True)} for path in files]


def remove_manifest(root, rows):
    """Recheck each file immediately before unlinking; retain changed items."""
    removed, faults = [], []
    for row in rows:
        try:
            path = contained(root, Path(root) / row['path'])
            if path.stat().st_size != row['bytes'] or verified_hash(path, fresh=True) != row['sha256']:
                raise ConfigError('Generated file changed after cleanup planning')
            path.unlink()
            removed.append(row['path'])
        except (OSError, ValueError) as exc:
            faults.append({'path': row['path'], 'status': 'faulty', 'reason': str(exc)})
    return {'removed': removed, 'faults': faults}


def remove_empty_parents(root, rows):
    parents = set()
    for row in rows:
        path = contained(root, Path(root) / row['path']).parent
        while path != Path(root):
            parents.add(path)
            path = path.parent
    removed, faults = [], []
    for path in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        try:
            contained(root, path)
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
                removed.append(path.relative_to(root).as_posix())
        except (OSError, ValueError) as exc:
            faults.append({'path': path.relative_to(root).as_posix(), 'status': 'faulty', 'reason': str(exc)})
    return {'removed': removed, 'faults': faults}
