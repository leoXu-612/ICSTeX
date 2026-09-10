"""Unified image asset import for Block projects (copy into the project,
never move or reference outside the project)."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import stat
import uuid

from app.core.project_dependencies import safe_project_input
from app.core.project_lock import project_write_lock


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".bmp", ".tif", ".tiff"}


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


@contextmanager
def _asset_directory(project):
    """Anchor this one import directory; no metadata writer or format change."""
    folder = project / "assets" / "images"
    root_info = project.stat()
    parent = None

    def check():
        current = project.lstat()
        if (not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (root_info.st_dev, root_info.st_ino)
                or safe_project_input(project, folder / "image.png", allow_internal=True) is None):
            raise OSError("Image destination changed or contains a link; import refused")
        if parent is not None:
            opened, current = os.fstat(parent), folder.stat()
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise OSError("Image destination directory changed; import refused")

    check()
    try:
        if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            parent = os.open(project, flags)
            opened = os.fstat(parent)
            if (opened.st_dev, opened.st_ino) != (root_info.st_dev, root_info.st_ino):
                raise OSError("Image project directory changed; import refused")
            for name in ("assets", "images"):
                try:
                    os.mkdir(name, 0o700, dir_fd=parent)
                except FileExistsError:
                    pass
                child = os.open(name, flags, dir_fd=parent)
                os.close(parent)
                parent = child
        else:
            # Known links/junctions are rejected on every observation. Native
            # Windows reparse-point races require separate platform acceptance.
            folder.mkdir(parents=True, exist_ok=True)
        check()
        yield folder, parent, check
    finally:
        if parent is not None:
            os.close(parent)


def _source_identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def import_image(project_dir: Path, source_path: Path) -> str:
    """Copy ``source_path`` into ``<project>/assets/images`` and return the
    project-relative path (posix).  The source file is never moved."""
    project = Path(project_dir).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"图片文件不存在：{source}")
    if not is_image_path(source):
        raise ValueError(f"不支持的图片类型：{source.suffix}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(source, flags), "rb") as incoming:
        original = os.fstat(incoming.fileno())
        if not stat.S_ISREG(original.st_mode):
            raise ValueError("Image source is not a regular file")
        with project_write_lock(project, blocking=False):
            project.mkdir(parents=True, exist_ok=True)
            with _asset_directory(project) as (folder, parent, check):
                name = f".icstex-image-{uuid.uuid4().hex}.tmp"
                temporary = name if parent is not None else folder / name
                kwargs = {"dir_fd": parent} if parent is not None else {}
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(temporary, flags, 0o600, **kwargs)
                owned = os.fstat(descriptor)
                try:
                    with os.fdopen(descriptor, "wb") as staged:
                        shutil.copyfileobj(incoming, staged, 512 * 1024)
                        staged.flush()
                        os.fsync(staged.fileno())
                    if (_source_identity(os.fstat(incoming.fileno())) != _source_identity(original)
                            or _source_identity(source.stat()) != _source_identity(original)):
                        raise OSError("Image source changed during copying; import refused")
                    index = 0
                    while True:
                        check()
                        filename = source.name if index == 0 else f"{source.stem} ({index}){source.suffix}"
                        target = filename if parent is not None else folder / filename
                        current = os.stat(temporary, follow_symlinks=False, **kwargs)
                        if (current.st_dev, current.st_ino) != (owned.st_dev, owned.st_ino):
                            raise OSError("Staged image changed; import refused")
                        try:
                            if os.name == "nt":
                                # Windows rename refuses an existing destination.
                                os.rename(temporary, target)
                            else:
                                # link is an atomic, no-replace publication on
                                # supported local filesystems. Never fall back to
                                # replacement if that filesystem cannot do it.
                                link_args = {"src_dir_fd": parent, "dst_dir_fd": parent} if parent is not None else {}
                                os.link(temporary, target, follow_symlinks=False, **link_args)
                        except FileExistsError:
                            index += 1
                            continue
                        check()
                        published = os.stat(target, follow_symlinks=False, **kwargs)
                        if (published.st_dev, published.st_ino) != (owned.st_dev, owned.st_ino):
                            raise OSError("Imported image changed; model was not updated")
                        return (Path("assets/images") / filename).as_posix()
                finally:
                    try:
                        current = os.stat(temporary, follow_symlinks=False, **kwargs)
                        if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
                            os.unlink(temporary, **kwargs)
                    except FileNotFoundError:
                        pass
