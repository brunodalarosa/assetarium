"""Keeps scratch/ safe to delete (AGENTS.md): links a run makes there are removed when it ends.

Removing a junction or symlink deletes only the link, never what it points to.
"""
import os
from pathlib import Path


def release(*links):
    for link in map(Path, links):
        if link.is_junction() or (link.is_symlink() and os.name == 'nt' and link.is_dir()):
            os.rmdir(link)
        elif link.is_symlink():
            link.unlink()
