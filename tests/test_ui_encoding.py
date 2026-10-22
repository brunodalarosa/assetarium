"""All app-owned UI sources and the packaged desktop shell preserve Unicode."""
from pathlib import Path
import re
import sys

import pytest

from local_asset_library import desktop
from local_asset_library.desktop import create_window
from ui_text import MOJIBAKE


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'src/local_asset_library/ui'
SOURCES = sorted(p for p in UI.rglob('*') if p.is_file() and 'vendor' not in p.parts
                 and p.suffix in {'.js', '.html', '.css'})
SOURCES += sorted(p for p in (ROOT / 'frontend/src').rglob('*') if p.suffix in {'.ts', '.tsx', '.css'})
SOURCES += [ROOT / 'src/local_asset_library' / name for name in
            ('desktop.py', 'desktop_service.py', 'interactive_preview.py', 'settings.py')]


@pytest.mark.parametrize('path', SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_app_owned_ui_text_is_utf8_without_mojibake(path):
    text = path.read_bytes().decode('utf-8', errors='strict')
    bad = [(number, match.group()) for number, line in enumerate(text.splitlines(), 1)
           for match in MOJIBAKE.finditer(line)]
    assert not bad, (str(path), bad)


def test_built_bundle_is_present_for_node_free_launches():
    assert (UI / 'build/app.js').stat().st_size > 100_000 and (UI / 'build/app.css').stat().st_size > 10_000


def packaged(monkeypatch, appearance='system', windows_dark=False):
    class Webview:
        settings = {}
        @staticmethod
        def create_window(title, **kwargs):
            return dict(kwargs, title=title)
    class Bridge:
        pass
    monkeypatch.setitem(sys.modules, 'webview', Webview)
    monkeypatch.setattr('local_asset_library.settings.interface_settings',
                        lambda config: {'status': 'ready', 'appearance': appearance, 'inspector_width': 512})
    monkeypatch.setattr(desktop, 'windows_prefers_dark', lambda: windows_dark)
    return create_window(None, Bridge())


def test_packaged_shell_keeps_punctuation_icons_and_accessible_text(monkeypatch):
    window = packaged(monkeypatch)
    html = window['html']
    assert window['title'] == 'Assetarium' and not MOJIBAKE.search(html)
    for expected in (
        'charset="utf-8"', 'Kenney · ', 'Loading preview…', 'Loading asset evidence…',
        'You’re all caught up.', ' in the library · ', '% — ', 'Settings → General',
        'Filters & search options', '↻ Explore in 3D', 'Opening fullscreen…',
    ):
        assert expected in html, repr(expected)
    # The CSP still allows only inline code, data: images and now data: fonts (bundled Geist).
    assert "font-src data:" in html and "default-src 'none'" in html
    assert not re.search(r'(?:src|href)\s*=\s*["\']?https?:|url\(\s*["\']?https?:', html)


@pytest.mark.parametrize('appearance,windows_dark,theme,background', [
    ('system', False, 'light', '#f1f5f9'), ('system', True, 'dark', '#10151e'),
    ('dark', False, 'dark', '#10151e'), ('light', True, 'light', '#f1f5f9')])
def test_theme_is_resolved_before_first_paint(monkeypatch, appearance, windows_dark, theme, background):
    window = packaged(monkeypatch, appearance, windows_dark)
    assert f'<html lang="en" data-theme="{theme}" data-appearance="{appearance}">' in window['html']
    assert 'window.LAL_BOOT={"appearance": "%s", "inspector_width": 512};' % appearance in window['html']
    assert window['background_color'] == background
