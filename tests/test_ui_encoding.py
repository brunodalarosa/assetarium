"""All app-owned UI sources and the packaged desktop shell preserve Unicode."""
from pathlib import Path
import sys

import pytest

from local_asset_library.desktop import create_window
from ui_text import MOJIBAKE


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'src/local_asset_library/ui'
SOURCES = sorted(p for p in UI.rglob('*') if p.is_file() and 'vendor' not in p.parts
                 and p.suffix in {'.js', '.html', '.css'})
SOURCES += [ROOT / 'src/local_asset_library' / name for name in
            ('desktop.py', 'desktop_service.py', 'interactive_preview.py')]


@pytest.mark.parametrize('path', SOURCES, ids=lambda p: p.name)
def test_app_owned_ui_text_is_utf8_without_mojibake(path):
    text = path.read_bytes().decode('utf-8', errors='strict')
    bad = [(number, match.group()) for number, line in enumerate(text.splitlines(), 1)
           for match in MOJIBAKE.finditer(line)]
    assert not bad, (str(path), bad)


def test_packaged_shell_keeps_punctuation_icons_and_accessible_text(monkeypatch):
    class Webview:
        settings = {}
        @staticmethod
        def create_window(title, **kwargs):
            return kwargs
    class Bridge:
        pass
    monkeypatch.setitem(sys.modules, 'webview', Webview)
    packaged = create_window(None, Bridge())['html']
    assert not MOJIBAKE.search(packaged)
    for expected in (
        'charset="utf-8"', 'Kenney \u00b7 ', 'Loading existing preview\u2026',
        '${state.offset+1}\u2013${state.offset+result.items.length}',
        '\u25c7</span>', "node('button','\u00d7','close-detail')",
        ' in the library \u00b7 ', '% \u2014 ', ' recorded failures \u00b7 ',
        '\u21bb Explore in 3D', 'Opening fullscreen\u2026',
    ):
        assert expected in packaged, repr(expected)
