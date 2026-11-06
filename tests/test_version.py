"""One release number everywhere the app names itself; runtime environments keep theirs (AGENTS.md → Versioning).

The caption and search fingerprints hash runtime/*/uv.lock, and a runtime version bump rewrites that lock, so a
release that bumped them would send every description and search vector back to be redone.
"""
import json
from pathlib import Path
import tomllib

from local_asset_library import __version__

ROOT = Path(__file__).resolve().parents[1]


def project_version(path):
    return tomllib.loads(path.read_text(encoding='utf-8'))['project']['version']


def test_app_version_fields_agree():
    lock = tomllib.loads((ROOT / 'uv.lock').read_text(encoding='utf-8'))
    locked = next(p['version'] for p in lock['package'] if p['name'] == 'local-asset-library')
    frontend = json.loads((ROOT / 'frontend/package.json').read_text(encoding='utf-8'))['version']
    assert project_version(ROOT / 'pyproject.toml') == __version__ == locked == frontend
    assert f'Version **{__version__}**' in (ROOT / 'README.md').read_text(encoding='utf-8')


def test_runtime_versions_stay_fixed():
    assert {p.parent.name: project_version(p) for p in sorted((ROOT / 'runtime').glob('*/pyproject.toml'))} == {
        'caption': '0.1.0', 'embedding': '0.1.0', 'embedding-cpu': '0.1.0', 'mcp': '0.1.0'}
