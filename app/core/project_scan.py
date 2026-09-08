"""Local project enumeration with pruning before directory descent."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator


def iter_project_files(root: Path, *, ignored_dirs: set[str]) -> Iterator[Path]:
    """Do not descend into generated directories or follow symbolic links."""
    for directory, subdirs, filenames in os.walk(root, topdown=True, followlinks=False):
        parent = Path(directory)
        subdirs[:] = [
            name for name in subdirs
            if name not in ignored_dirs and not (parent / name).is_symlink()
        ]
        for name in filenames:
            path = parent / name
            if not path.is_symlink() and path.is_file():
                yield path
