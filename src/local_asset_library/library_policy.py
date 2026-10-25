"""Neutral library policy for every install: registered sources define membership.

The original owner's pack approvals and allowances are historical evidence
(``docs/history/library-membership-2026-10-14.json``) and are never read. An older install
that still has its own ``docs/library-membership.json`` keeps that contract unchanged. The
neutral default budget keeps the historical numbers, so behavior without saved settings is
the same either way.
"""
import json

GIB = 1024 ** 3
DEFAULT_BUDGET = {'total_allocated_bytes': 10 * GIB, 'peak_additional_allocated_bytes': 3 * GIB}
APPROVAL = 'Sources the owner registered and enabled in Settings → Asset sources.'
LEGACY = 'docs/library-membership.json'


def legacy(config):
    path = config.project_root / LEGACY
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def contract(config):
    """The membership contract incremental processing validates (decision 0009: general, not pack-specific)."""
    return legacy(config) or {'schema_version': 1, 'approved': True, 'approval': APPROVAL, 'packs': [],
                              'budget': dict(DEFAULT_BUDGET)}


def default_budget(config):
    """Budget used until the user saves one in Settings → General."""
    return dict((legacy(config) or {}).get('budget') or DEFAULT_BUDGET)


def library_mode(config):
    """Registered sources (every current install) or an older pack contract use incremental processing."""
    return bool(config.sources_registry) or legacy(config) is not None
