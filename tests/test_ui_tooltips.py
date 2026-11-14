"""Every clickable in the app-owned UI goes through a primitive that requires a tooltip or an explicit opt-out.

`Button`, `Pressable` and `MotionPressable` (`frontend/src/ui/primitives.tsx`) take a required `tooltip`, so the
TypeScript build fails without one; this test closes the ways around them: a raw `<button>` / `<motion.button>`
and a native `title=` tooltip on an HTML element. beUI's vendored components keep their own internals. The plain-JS
3D viewer (`ui/interactive-preview.js`) can't use the primitives: its controls put their text in `data-tooltip-text`,
which `ui/ViewerTooltips.tsx` shows with the same tooltip, and never set a native `title`.
"""
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'frontend/src'
OWNED = sorted(p for p in SRC.rglob('*.tsx') if 'beui' not in p.relative_to(SRC).parts)
PRIMITIVES = SRC / 'ui/primitives.tsx'
RAW_BUTTON = re.compile(r'<(?:motion\.)?button\b')
HTML_TAG = re.compile(r'<([a-z][\w.]*)')
TITLE_ATTR = re.compile(r'(?<![\w-])title=')
VIEWER = ROOT / 'src/local_asset_library/ui/interactive-preview.js'
# `.title =` or setAttribute('title', …); the iframe's title is its accessible name, not a tooltip.
JS_TITLE = re.compile(r"(\w+)\.title\s*=(?!=)|setAttribute\(\s*['\"]title['\"]")
NAMED_FRAMES = {'frame'}


def line_of(text, index):
    return text.count('\n', 0, index) + 1


def html_tags(text):
    """(line, element, attributes) of each lowercase (HTML or motion.*) opening tag; braces and quotes may hold `>`."""
    for match in HTML_TAG.finditer(text):
        depth, quote, end = 0, '', match.end()
        while end < len(text):
            char = text[end]
            if quote:
                quote = '' if char == quote else quote
            elif char in '"\'`':
                quote = char
            elif char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
            elif char == '>' and depth == 0:
                break
            end += 1
        yield line_of(text, match.start()), match.group(1), text[match.end():end]


def test_the_owned_sources_are_found():
    assert PRIMITIVES in OWNED and len(OWNED) > 30


@pytest.mark.parametrize('path', OWNED, ids=lambda p: str(p.relative_to(SRC)))
def test_no_raw_buttons_outside_the_primitives(path):
    if path == PRIMITIVES:
        return
    text = path.read_text(encoding='utf-8')
    found = [line_of(text, m.start()) for m in RAW_BUTTON.finditer(text)]
    assert not found, f'{path.relative_to(ROOT)}:{found}: use Button, IconButton, Pressable or MotionPressable'


@pytest.mark.parametrize('path', OWNED, ids=lambda p: str(p.relative_to(SRC)))
def test_no_native_title_tooltips(path):
    found = [line for line, _, attributes in html_tags(path.read_text(encoding='utf-8')) if TITLE_ATTR.search(attributes)]
    assert not found, f'{path.relative_to(ROOT)}:{found}: use the beUI tooltip (Hint, Pressable) instead of title='


def native_titles(text):
    """Lines that give an element a native title tooltip, except the iframe's accessible name."""
    return [line_of(text, m.start()) for m in JS_TITLE.finditer(text) if m.group(1) not in NAMED_FRAMES]


def test_the_3d_viewer_sets_no_native_title():
    text = VIEWER.read_text(encoding='utf-8')
    found = native_titles(text)
    assert not found, f'{VIEWER.relative_to(ROOT)}:{found}: put the text in data-tooltip-text (ViewerTooltips.tsx shows it)'
    assert "frame.title = " in text and 'dataset.tooltipText' in text


def test_the_checks_catch_what_they_ban():
    assert native_titles("button.title = label;") == [1] and native_titles("x.setAttribute('title', t)") == [1]
    assert native_titles("frame.title = name;\nif (a.title === b) {}\nthis.more.title = t;") == [3]
    assert RAW_BUTTON.search('<button type="button">') and RAW_BUTTON.search('<motion.button\n')
    assert not RAW_BUTTON.search('<Button tooltip={false}>')
    tag = lambda text: [name for _, name, attributes in html_tags(text) if TITLE_ATTR.search(attributes)]
    assert tag('<span className="x"\n  title={a ? `b ${c}` : undefined}>') == ['span']
    assert tag('<motion.div onClick={() => { go({ page: "x" }); }} title="t">') == ['motion.div']
    assert tag('<p className="a > b">x</p><b title="t">') == ['b']
    assert tag('<Card title="Settings">') == [] and tag('<span data-title="x">') == []
