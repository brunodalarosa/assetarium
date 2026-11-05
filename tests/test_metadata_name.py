"""No tracked file names the old per-source generated folder outside the migration and history (decision 0023)."""
from pathlib import Path
import subprocess

from local_asset_library.library_migration import LEGACY_METADATA_DIR

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ('src/local_asset_library/library_migration.py', 'scripts/migrate-library.py', 'scripts/check-rekey.py',
           'docs/history/', 'scripts/historical/', 'CHANGELOG.md', '.gitignore',
           'Assetarium KnowledgeBase/Notebook/Roadmap/Features/ASSETRM-0002',
           'Assetarium KnowledgeBase/Decisions/')  # Decisions are dated owner records; 0023 replaces the folder.


def test_the_old_folder_name_appears_only_in_the_migration_and_history():
    files = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.decode().split('\0')
    found = []
    for name in filter(None, files):
        if name.startswith(ALLOWED) or not (ROOT / name).is_file():
            continue
        if LEGACY_METADATA_DIR.encode() in (ROOT / name).read_bytes():
            found.append(name)
    assert not found, 'Use library_migration.LEGACY_METADATA_DIR or the library store instead: ' + ', '.join(found)
