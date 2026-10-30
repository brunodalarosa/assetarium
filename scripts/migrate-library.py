"""One-time move of old per-source generated folders into the central library store (decision 0023).

    migrate-library.py [--library-folder PATH ...] [--search PATH ...]      dry run: writes the plan only
    migrate-library.py [--library-folder PATH ...] [--search PATH ...] --apply
    migrate-library.py --remove-old

Run with the base runtime (`.\\scripts\\uv.ps1 run --locked python scripts/migrate-library.py ...`, same arguments
with `./scripts/uv.sh`). Close the app and MCP servers first. Nothing is moved: results are copied (immutable
result files hard-linked on the same drive) and re-keyed by their inputs, so nothing renders or is described
again. Each old folder is imported once; a fault stops only its own folder. --apply and --remove-old ask in the
terminal and have no bypass. --remove-old deletes only folders whose import a receipt verified.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from local_asset_library.config import ConfigError, load_project_config  # noqa: E402
from local_asset_library import library_migration  # noqa: E402


def ask(text):
    if not sys.stdin.isatty():
        raise ConfigError('This step asks in a terminal; run it yourself (there is no bypass)')
    return input(text + ' Type yes to continue: ').strip().lower() == 'yes'


def summary(plan):
    for folder in plan['folders']:
        line = f"- {folder['path']}: {folder['status']}"
        if folder['status'] == 'ready':
            enroll, ledger = folder['enroll'], folder['ledger']
            finished = sum(v for k, v in ledger.items() if k.endswith(":complete") and isinstance(v, int))
            line += (f"; {folder['assets']} assets, {finished} finished results to re-key"
                     + (f"; joins library folder {folder['library_folder']}" if folder['library_folder'] != folder['path'] else '')
                     + (f"; relinked from {folder['relinked_from']}" if folder.get('relinked_from') else '')
                     + (f"; {enroll['images_previously_off']} images newly included" if enroll['images_previously_off'] else '')
                     + (f"; {enroll['other_format_models']} models of other formats, proposed exclusions: "
                        + (', '.join(enroll['proposed_exclusions']) or 'none') if enroll['import_formats'] is not None else ''))
        elif folder.get('fault'):
            line += f" ({folder['fault']})"
        print(line)
    for item in plan['unmatched_registry']:
        print(f"- registered {item['key']} at {item['path']}: {item['reason']}")
    if plan['app_processes']:
        print('Close these first: ' + '; '.join(plan['app_processes']))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--library-folder', action='append', default=[], help='a folder that becomes one library folder')
    parser.add_argument('--search', action='append', default=[], help='also look here (for example, a moved drive)')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--remove-old', action='store_true')
    args = parser.parse_args()
    config = load_project_config(ROOT)
    try:
        if args.remove_old:
            removed = library_migration.remove_old(config, ask)
            print(json.dumps(removed, indent=2))
            return 0
        plan, path = library_migration.plan(config, args.library_folder, args.search)
        print(f'Plan: {path.relative_to(ROOT)}')
        summary(plan)
        if not args.apply:
            print('Dry run; nothing was changed. Review the plan, then run again with --apply.')
            return 0
        receipt, path = library_migration.apply(config, plan, ask)
        for folder in receipt['folders']:
            print(f"- {folder['path']}: {folder['status']}" + (f" ({folder['fault']})" if folder.get('fault') else '')
                  + (f" {folder['check']}" if folder.get('check') and folder['status'] != 'verified' else ''))
        print(f'Receipt: {path.relative_to(ROOT)}')
        return 0 if all(f['status'] == 'verified' for f in receipt['folders']) else 1
    except ConfigError as exc:
        print(f'Not done: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
