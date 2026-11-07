"""Decision records stay current truth (decision review, November 2026): one file per live decision, listed in the
index; replaced numbers only in the Replaced table; no amendment notes stacked on a record; a known area; at most
150 lines; and every code name a decision cites still exists. Contradictions are judged at the scope checkpoint
(AGENTS.md → Recorded decisions); this test keeps the mechanical rules."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / 'Assetarium KnowledgeBase' / 'Decisions'
PACKAGE = ROOT / 'src' / 'local_asset_library'
AREAS = {'Desktop App', 'MCP', 'Platform and Storage', 'Processing', 'Search', 'Setup and Engines',
         'Sources and Catalog', 'Project'}
MAX_LINES = 150
FILE_TYPES = ('.py', '.ts', '.tsx', '.json', '.jsonl', '.toml', '.md', '.txt', '.sqlite', '.png')
# Notes that patch a record instead of rewriting it: the habit that made 27 decisions unreadable.
AMENDMENT = re.compile(r'^\s*(>\s*)?\*{0,2}\(?(Since |Update|Updated |Scope note|See also|Corrected |Amended|Added )'
                       r'|[Pp]artly superseded|superseded_in_part_by|^status:\s*(retired|superseded)'
                       r'|\((?:[Uu]pdated|[Aa]dded|[Cc]orrected|[Aa]mended)\b[^)]*\d{4}', re.M)


def records():
    return sorted(DECISIONS.glob('[0-9][0-9][0-9][0-9]-*.md'))


def front(path):
    text = path.read_text(encoding='utf-8')
    match = re.match(r'---\n(.*?)\n---\n', text.replace('\r\n', '\n'), re.S)
    assert match, f'{path.name}: no frontmatter'
    return dict(line.split(':', 1) for line in match.group(1).splitlines() if ':' in line and not line.startswith(' ')), text


def index():
    text = (DECISIONS / 'Decisions.md').read_text(encoding='utf-8')
    current, _, replaced = text.partition('\n## Replaced')
    return (re.findall(r'^\| \[(\d{4})\]\(([^)]+)\)', current, re.M),
            set(re.findall(r'^\| (\d{4}) \|', replaced, re.M)))


def numbers(value):
    return re.findall(r'\b\d{4}\b', value or '')


def test_index_lists_every_current_decision_and_only_those():
    listed, replaced = index()
    files = {p.name[:4]: p.name for p in records()}
    assert len(files) == len(records()), 'Two decision files share a number'
    assert {n: f for n, f in listed} == files, 'Decisions.md must list exactly the decision files, with their file names'
    assert not replaced & set(files), f'Replaced numbers still have a file: {sorted(replaced & set(files))}'


def test_replaced_numbers_are_recorded_and_never_reused():
    _, replaced = index()
    for path in records():
        fields, _ = front(path)
        for number in numbers(fields.get('replaces')):
            assert number in replaced, f'{path.name} replaces {number}, which needs a row under Replaced in Decisions.md'


def test_each_decision_has_frontmatter_area_and_size():
    for path in records():
        fields, text = front(path)
        assert fields.get('tags', '').strip() == '[decision]', f'{path.name}: tags must be [decision]'
        assert re.fullmatch(r'\s*\d{4}-\d{2}-\d{2}', fields.get('decided', '')), f'{path.name}: decided must be a date'
        assert fields.get('area', '').strip() in AREAS, f'{path.name}: area must be one of {sorted(AREAS)}'
        lines = text.count('\n') + 1
        assert lines <= MAX_LINES, f'{path.name}: {lines} lines; split it (at most {MAX_LINES})'


def test_decisions_are_rewritten_not_patched():
    for path in records():
        found = AMENDMENT.search(front(path)[1])
        assert not found, (f'{path.name}: "{found.group(0).strip()}" patches the record. Rewrite the text and add a dated '
                           'line under "## Changes" instead (AGENTS.md → Recorded decisions)')


def _exists(name):
    """A cited `module.attr`, `file.py` or repo path still exists (attributes by definition or assignment)."""
    if '/' in name:
        return (ROOT / name).exists()
    if name.endswith(FILE_TYPES):
        return (PACKAGE / name).exists() or (ROOT / name).exists()
    module, _, attr = name.partition('.')
    source = PACKAGE / f'{module}.py'
    if not source.exists():
        return None  # Not a package module (prose like `config.local.toml`): nothing to check.
    last = attr.split('.')[-1]
    return not last or re.search(rf'^\s*(def|class|async def)\s+{re.escape(last)}\b|^\s*{re.escape(last)}\s*[:=]',
                                 source.read_text(encoding='utf-8'), re.M) is not None


def test_cited_code_still_exists():
    missing = []
    for path in records():
        fields, text = front(path)
        cited = [c.strip() for c in fields.get('code', '').strip(' []').split(',') if c.strip()]
        cited += [name for name in re.findall(r'`([a-z_]+\.[A-Za-z_][\w.]*)`', text)  # `module.function` in the text
                  if not name.endswith(FILE_TYPES)]  # File names in prose (`settings.json`) are data, not code.
        missing += [f'{path.name}: {name}' for name in dict.fromkeys(cited) if _exists(name) is False]
    assert not missing, 'Decisions cite code that no longer exists:\n' + '\n'.join(missing)
