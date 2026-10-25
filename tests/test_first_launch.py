"""Zero-edit first launch (P0): an empty project with the shipped example config starts and offers setup."""
from pathlib import Path
import shutil

import pytest

from local_asset_library import source_operations
from local_asset_library.config import ConfigError, load_project_config
from local_asset_library.desktop import DesktopBridge, page_html
from test_sources import managed  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fresh_clone(tmp_path):
    """What a fresh clone has besides code: the tracked example config and docs, and no data/, no config.local.toml."""
    root = tmp_path / 'clone'
    for relative in ('config.example.toml', 'docs/caption-model.json', 'docs/embedding-model.json'):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, root / relative)
    return root


def test_empty_project_starts_every_view_and_opens_setup(fresh_clone, monkeypatch):
    monkeypatch.setattr(source_operations.subprocess, 'Popen', lambda *a, **kw: pytest.fail('Nothing is spawned at startup'))
    config = load_project_config(fresh_clone)
    assert not (fresh_clone / 'config.local.toml').exists() and config.models_root is None and config.blender is None
    bridge = DesktopBridge(config, prestart_worker=False)
    try:
        results = {name: getattr(bridge, name)() for name in
                   ('context', 'sources', 'general_settings', 'interface_settings', 'changes', 'importing_failures', 'setup_state')}
        results['collections'] = bridge.collections()
        results['browse'] = bridge.browse({}, 0, 40)
        results['scan'] = bridge.source_action('scan')
        assert not [name for name, value in results.items() if value.get('status') == 'faulty'], results
        assert results['setup_state']['auto_open'] and results['scan']['status'] == 'idle'
        html, _ = page_html(config)
        assert 'BUNDLED_SCRIPT' not in html and len(html) > 100_000
    finally:
        bridge._close()
    assert not (fresh_clone / 'data/library/settings.json').exists()  # Launching never writes settings.


def test_missing_base_environment_says_how_to_create_it(managed):
    config, _, one, _ = managed
    assert not (config.project_root / '.venv').exists()
    with pytest.raises(ConfigError, match='uv.(ps1|sh) sync --locked'):
        source_operations.start(config, 'scan', one['key'])
    assert source_operations.operation_status(source_operations.bound(config, one))['status'] == 'faulty'
