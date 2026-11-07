"""Every store records its format version, and a newer one is refused before anything changes (safe upgrades).

A release reads only the formats it knows. A store written by a newer release stays exactly as it is and the open
fails with a visible reason, so going back to an older Assetarium never rewrites newer data. Check before any DDL:
``CREATE TABLE IF NOT EXISTS`` on a newer database is already a change.
"""
from .config import ConfigError


def newer(name, found, known):
    return ConfigError(f'{name} was written by a newer Assetarium (format {found}; this version reads {known}). '
                       'Nothing was changed; update Assetarium to use it')


def checked(db, name, known):
    """``db`` once its ``user_version`` is ``known``; an unversioned database (0) is stamped, any other is refused."""
    found = db.execute('PRAGMA user_version').fetchone()[0]
    if found == known:
        return db
    if found == 0:
        db.execute(f'PRAGMA user_version={int(known)}')
        return db
    db.close()
    if found > known:
        raise newer(name, found, known)
    raise ConfigError(f'{name} has an unknown format {found}; nothing was changed')


def newer_refused(value, name, known):
    """``value`` (a JSON object read from ``name``) unless a newer Assetarium wrote it; then nothing may rewrite it."""
    found = value.get('schema_version') if isinstance(value, dict) else None
    if type(found) is int and found > known:
        raise newer(name, found, known)
    return value


def read_versioned(path, name, known):
    from .publication import read_json
    return newer_refused(read_json(path), name, known)
