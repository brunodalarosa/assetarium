"""Design principle P3: every command the app shows gets a block with Copy (frontend/src/ui/CommandBlock.tsx).

The UI finds commands inside backend text with COMMAND_PATTERN; these tests run that same pattern over the backend's
command-carrying messages, and keep literal commands out of the UI source.
"""
from pathlib import Path
import re

from local_asset_library import engines

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'frontend/src/ui/CommandBlock.tsx').read_text(encoding='utf-8')
PATTERN = re.compile(re.search(r'COMMAND_PATTERN = String\.raw`([^`]+)`', SOURCE).group(1))


def found(text):
    return [m.group(0).rstrip('.,;:') for m in PATTERN.finditer(text)]


def test_the_pattern_finds_each_backend_command_whole():
    for command in (engines.command(None, 'embedding', 'sync --locked --project runtime/embedding'),
                    engines.weights_command(None, 'embedding', {'state': 'absent'}, 'runtime/embedding'),
                    engines.weights_command(None, 'caption', {'state': 'present'}, 'runtime/caption'),
                    r'.\scripts\uv.ps1 sync --locked', './scripts/uv.sh sync --locked', 'local-assets setup status'):
        assert found(f'Install it: {command}') == [command]
        assert found(f'Run it in a terminal in the Assetarium folder: {command} Then process this source again.') == [command]
        assert found(f'Verify it: {command}. Nothing is downloaded.') == [command]


def test_ui_source_never_spells_out_a_command():
    for path in (ROOT / 'frontend/src').rglob('*.tsx'):
        text = path.read_text(encoding='utf-8')
        assert not re.search(r'\.\\scripts\\|\./scripts/\w', text), f'{path.name}: commands come from the backend, shown in a CommandBlock'
