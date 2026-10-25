"""Contained, manifest-driven removal of explicitly retired generated files.

Filesystem calls use Windows long-path syntax so deep generated trees (over 260
characters) are validated and removed like any other; reported paths stay plain.
"""
import os
from pathlib import Path
import stat

from .config import ConfigError
from .publication import filesystem_path, verified_hash

_PREFIXES = ('\\\\?\\UNC\\', '\\\\?\\')


def _plain(value):
    value = str(value)
    if value.startswith(_PREFIXES[0]):
        return '\\\\' + value[len(_PREFIXES[0]):]
    return value.removeprefix(_PREFIXES[1])


def _is_link(path):
    native = filesystem_path(path)
    return os.path.islink(native) or os.path.isjunction(native)


def _redirected(path):
    return os.path.normcase(_plain(os.path.realpath(filesystem_path(path)))) != os.path.normcase(str(path))


def contained(root, path, checked=None):
    """``checked`` shares already validated directories within one operation."""
    root, path = Path(root).absolute(), Path(path).absolute()
    if _redirected(root) or path == root or not path.is_relative_to(root):
        raise ConfigError('Cleanup target is outside the approved generated-data root')
    current = path
    while current != root:
        if checked is not None and current in checked:
            break
        if _is_link(current) or _redirected(current):
            raise ConfigError('Cleanup refuses links or redirected paths: ' + str(current))
        if checked is not None and current != path:
            checked.add(current)
        current = current.parent
    if _is_link(root):
        raise ConfigError('Cleanup root is a link')
    return path


def tree_files(root, target):
    """Validate an entire tree before removing any file; never follow links."""
    checked = set()
    target = contained(root, target, checked)
    if os.path.isfile(filesystem_path(target)):
        return [target]
    if not os.path.isdir(filesystem_path(target)):
        raise ConfigError('Cleanup target is missing: ' + str(target))
    result = []
    def fail(exc):
        raise exc
    for directory, dirs, files in os.walk(filesystem_path(target), followlinks=False, onerror=fail):
        directory = Path(_plain(directory))
        for name in dirs:
            contained(root, directory / name, checked)
        for name in files:
            result.append(contained(root, directory / name, checked))
    return sorted(result)


def manifest(root, targets):
    files = sorted({path for target in targets for path in tree_files(root, target)})
    return [{'path': path.relative_to(root).as_posix(), 'bytes': os.stat(filesystem_path(path)).st_size,
             'sha256': verified_hash(path, fresh=True)} for path in files]


def remove_manifest(root, rows, clear_readonly=False):
    """Recheck each file immediately before unlinking; retain changed items.

    ``clear_readonly`` lifts the read-only attribute that immutable publications
    carry, only after the planned bytes were re-verified.
    """
    removed, faults, checked = [], [], set()
    for row in rows:
        try:
            path = contained(root, Path(root) / row['path'], checked)
            native = filesystem_path(path)
            if os.stat(native).st_size != row['bytes'] or verified_hash(path, fresh=True) != row['sha256']:
                raise ConfigError('Generated file changed after cleanup planning')
            if clear_readonly and not os.access(native, os.W_OK):
                os.chmod(native, stat.S_IREAD | stat.S_IWRITE)
            os.unlink(native)
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
            native = filesystem_path(path)
            if os.path.isdir(native) and not os.listdir(native):
                os.rmdir(native)
                removed.append(path.relative_to(root).as_posix())
        except (OSError, ValueError) as exc:
            faults.append({'path': path.relative_to(root).as_posix(), 'status': 'faulty', 'reason': str(exc)})
    return {'removed': removed, 'faults': faults}


def remove_empty_tree(root, target):
    """Remove empty directories left inside a validated target (links never followed)."""
    faults = []
    native_target = filesystem_path(target)
    if not os.path.isdir(native_target):
        return faults
    for directory, dirs, files in os.walk(native_target, topdown=False, followlinks=False):
        try:
            path = contained(root, Path(_plain(directory)))
            if not os.listdir(filesystem_path(path)):
                os.rmdir(filesystem_path(path))
        except (OSError, ValueError) as exc:
            faults.append({'path': _plain(directory), 'status': 'faulty', 'reason': str(exc)})
    return faults
