from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QImageWriter

from app.core.paths import latex_dependency_closure, strip_latex_comments


ALLOWED_SUFFIXES = (".png", ".jpg", ".jpeg")
WATCHABLE_SUFFIXES = (*ALLOWED_SUFFIXES, ".pdf", ".eps")
MAX_PROXY_EDGE = 1800
JPEG_QUALITY = 82
TEX_DEFAULT_IMAGE_DPI = 72
POLICY_VERSION = (
    "image-proxy-v3:max-edge=1800:jpeg-quality=82:raw-orientation:preserve-natural-size"
)
MANIFEST_SCHEMA = 1

_GRAPHICS_RE = re.compile(r"\\includegraphics\*?(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}")
_GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\s*\{[^{}]*\}\s*)+)\}")
_GRAPHICSPATH_ENTRY_RE = re.compile(r"\{([^{}]*)\}")
_DYNAMIC_PATH_CHARS = frozenset("\\#$%{}~")
_LOCKS_GUARD = threading.Lock()
_OVERLAY_LOCKS: dict[Path, threading.RLock] = {}


@dataclass(frozen=True)
class ImageProxyResult:
    overlay_dir: Path
    proxy_count: int
    fallback_count: int
    manifest_digest: str | None
    fidelity: str
    referenced_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class _ProxyMetadata:
    proxy_sha256: str
    width: int
    height: int


class ImageProxyCache:
    """Build a local image-only overlay for fast preview compilation."""

    def __init__(self, *, policy_version: str = POLICY_VERSION) -> None:
        if not policy_version:
            raise ValueError("policy_version must not be empty")
        self.policy_version = policy_version

    def referenced_paths(self, root_file: Path) -> tuple[Path, ...]:
        """Return statically identifiable local graphic dependencies."""
        root = Path(root_file).expanduser().resolve()
        _resolved, _unresolved, watched = _referenced_images(root, root.parent)
        return tuple(sorted(watched))

    def prepare(self, root_file: Path, overlay_dir: Path) -> ImageProxyResult:
        root = Path(root_file).expanduser().resolve()
        project_dir = root.parent
        overlay = Path(overlay_dir).expanduser().resolve()
        resolved, unresolved, watched = _referenced_images(root, project_dir)

        # Cleaning an overlay that is the project directory (or one of its
        # ancestors) could destroy user files. Reject that caller error and let
        # LaTeX fall back to the originals instead.
        if (
            not overlay.is_relative_to(project_dir)
            or overlay == project_dir
            or project_dir.is_relative_to(overlay)
            or root.is_relative_to(overlay)
            or any(source.is_relative_to(overlay) for source in resolved.values())
        ):
            return ImageProxyResult(
                overlay_dir=overlay,
                proxy_count=0,
                fallback_count=len(resolved) + len(unresolved),
                manifest_digest=None,
                fidelity=_fidelity(0, len(resolved) + len(unresolved)),
                referenced_paths=tuple(sorted(watched)),
            )

        lock = _overlay_lock(overlay)
        with lock:
            return self._prepare_locked(overlay, resolved, unresolved, watched)

    def _prepare_locked(
        self,
        overlay: Path,
        resolved: dict[str, Path],
        unresolved: set[str],
        watched: set[Path],
    ) -> ImageProxyResult:
        overlay.mkdir(parents=True, exist_ok=True)
        _clean_overlay(overlay)

        manifest_path = overlay.parent / "manifest.json"
        previous = _read_manifest(manifest_path, policy_version=self.policy_version)
        previous_entries = previous.get("entries", {}) if previous else {}
        if not isinstance(previous_entries, dict):
            previous_entries = {}

        published: set[str] = set()
        entries: dict[str, dict[str, object]] = {}
        references: dict[str, dict[str, str | None]] = {}
        fallback_count = len(unresolved)

        for relative_path, source in sorted(resolved.items()):
            destination = (overlay / Path(relative_path)).resolve()
            if not destination.is_relative_to(overlay):
                fallback_count += 1
                continue

            try:
                source_sha256 = _sha256_file(source)
            except OSError:
                references[relative_path] = {"source_sha256": None}
                fallback_count += 1
                _remove_proxy(destination, overlay)
                continue
            references[relative_path] = {"source_sha256": source_sha256}

            cache_key = _cache_key(source_sha256, self.policy_version)
            cached = previous_entries.get(relative_path)
            metadata = _cached_metadata(
                cached,
                destination=destination,
                source_sha256=source_sha256,
                cache_key=cache_key,
            )

            if metadata is None:
                try:
                    metadata = _write_proxy_atomic(
                        source,
                        destination,
                        overlay=overlay,
                        staging_dir=overlay.parent,
                        expected_source_sha256=source_sha256,
                    )
                except (OSError, RuntimeError, ValueError):
                    fallback_count += 1
                    _remove_proxy(destination, overlay)
                    continue

            published.add(relative_path)
            entries[relative_path] = {
                "cache_key": cache_key,
                "source_sha256": source_sha256,
                "proxy_sha256": metadata.proxy_sha256,
                "width": metadata.width,
                "height": metadata.height,
            }

        _remove_stale_proxies(overlay, published)
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "policy_version": self.policy_version,
            "proxy_count": len(entries),
            "fallback_count": fallback_count,
            "references": references,
            "entries": entries,
        }
        payload = _manifest_payload(manifest)
        _write_bytes_atomic(manifest_path, payload)
        digest = hashlib.sha256(payload).hexdigest()
        return ImageProxyResult(
            overlay_dir=overlay,
            proxy_count=len(entries),
            fallback_count=fallback_count,
            manifest_digest=digest,
            fidelity=_fidelity(len(entries), fallback_count),
            referenced_paths=tuple(sorted(watched)),
        )


_DEFAULT_CACHE = ImageProxyCache()


def prepare(root_file: Path, overlay_dir: Path) -> ImageProxyResult:
    return _DEFAULT_CACHE.prepare(root_file, overlay_dir)


def referenced_paths(root_file: Path) -> tuple[Path, ...]:
    return _DEFAULT_CACHE.referenced_paths(root_file)


@dataclass(frozen=True)
class _ResolvedReference:
    proxy_source: Path | None
    watched_paths: tuple[Path, ...]


def _referenced_images(
    root_file: Path,
    project_dir: Path,
) -> tuple[dict[str, Path], set[str], set[Path]]:
    resolved: dict[str, Path] = {}
    unresolved: set[str] = set()
    watched: set[Path] = set()
    source_texts: dict[Path, str] = {}
    source_files = sorted(
        latex_dependency_closure(root_file),
        key=lambda path: (path.expanduser().resolve() != root_file, str(path)),
    )
    for tex_file in source_files:
        source_file = tex_file.expanduser().resolve()
        if not source_file.is_relative_to(project_dir) or not source_file.is_file():
            continue
        try:
            text = source_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        source_texts[source_file] = strip_latex_comments(text)

    root_graphicspaths = _graphicspath_directories(
        source_texts.get(root_file, ""),
        tex_file=root_file,
        project_dir=project_dir,
    )
    for source_file, text in source_texts.items():
        local_graphicspaths = _graphicspath_directories(
            text,
            tex_file=source_file,
            project_dir=project_dir,
        )
        graphicspaths = local_graphicspaths or root_graphicspaths

        for match in _GRAPHICS_RE.finditer(text):
            raw = match.group(1).strip()
            reference = _resolve_reference(
                raw,
                tex_file=source_file,
                project_dir=project_dir,
                graphicspaths=graphicspaths,
            )
            watched.update(reference.watched_paths)
            if reference.proxy_source is None:
                unresolved.add(f"{source_file}:{raw}")
                continue
            relative_path = reference.proxy_source.relative_to(project_dir).as_posix()
            resolved[relative_path] = reference.proxy_source
    return resolved, unresolved, watched


def _graphicspath_directories(
    text: str,
    *,
    tex_file: Path,
    project_dir: Path,
) -> tuple[Path, ...]:
    directories: list[Path] = []
    for match in _GRAPHICSPATH_RE.finditer(text):
        for entry in _GRAPHICSPATH_ENTRY_RE.findall(match.group(1)):
            entry_raw = entry.strip()
            if (
                not entry_raw
                or "\x00" in entry_raw
                or any(character in entry_raw for character in _DYNAMIC_PATH_CHARS)
            ):
                continue
            raw = entry_raw.replace("\\", "/")
            path = Path(raw)
            bases = (path,) if path.is_absolute() else (project_dir / path, tex_file.parent / path)
            for base in bases:
                candidate = _safe_project_candidate(base, project_dir)
                if candidate is not None and candidate not in directories:
                    directories.append(candidate)
    return tuple(directories)


def _resolve_reference(
    raw: str,
    *,
    tex_file: Path,
    project_dir: Path,
    graphicspaths: tuple[Path, ...] = (),
) -> _ResolvedReference:
    if not raw or "\x00" in raw or any(character in raw for character in _DYNAMIC_PATH_CHARS):
        return _ResolvedReference(None, ())
    normalized_raw = raw.replace("\\", "/")
    reference = Path(normalized_raw)
    proxyable_request = (
        not reference.is_absolute()
        and not normalized_raw.startswith("./")
        and ".." not in reference.parts
        and (not reference.suffix or reference.suffix.lower() in ALLOWED_SUFFIXES)
    )

    if reference.is_absolute():
        bases = (reference,)
    else:
        # graphicx applies \graphicspath to bare names. Keep the declared
        # order, then retain ICSTeX's established root/child-relative lookup.
        declared = graphicspaths if reference.parent == Path(".") else ()
        bases = (*declared, project_dir, tex_file.parent)

    candidates: list[Path] = []
    for base in bases:
        base = base if reference.is_absolute() else base / reference
        if reference.suffix:
            candidates.append(base)
        else:
            candidates.extend(base.with_suffix(suffix) for suffix in WATCHABLE_SUFFIXES)
            # Preserve the actual spelling of a supported extension on
            # case-sensitive filesystems when LaTeX omitted the suffix.
            try:
                candidates.extend(
                    child
                    for child in sorted(base.parent.iterdir())
                    if child.stem == base.name and child.suffix.lower() in WATCHABLE_SUFFIXES
                )
            except OSError:
                pass

    seen: set[Path] = set()
    watch_candidates: list[Path] = []
    for candidate in candidates:
        resolved = _safe_project_candidate(candidate, project_dir, allow_alias=True)
        if resolved is None or resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.exists() and not resolved.parent.is_dir():
            # PollingObserver cannot watch a directory that does not yet
            # exist. It will be discovered on the next source edit/compile.
            continue
        watch_candidates.append(resolved)
        if resolved.is_file():
            is_alias = resolved != Path(os.path.abspath(candidate.expanduser()))
            proxy = (
                resolved
                if (
                    proxyable_request
                    and not is_alias
                    and resolved.suffix.lower() in ALLOWED_SUFFIXES
                )
                else None
            )
            return _ResolvedReference(proxy, (resolved,))
    return _ResolvedReference(None, tuple(watch_candidates))


def _safe_project_candidate(
    candidate: Path,
    project_dir: Path,
    *,
    allow_alias: bool = False,
) -> Path | None:
    try:
        resolved = candidate.expanduser().resolve()
    except OSError:
        return None
    if not allow_alias and resolved != Path(os.path.abspath(candidate.expanduser())):
        # A symlink alias cannot be mirrored truthfully under TEXINPUTS.
        return None
    if not resolved.is_relative_to(project_dir):
        return None
    return resolved


def _cached_metadata(
    entry: object,
    *,
    destination: Path,
    source_sha256: str,
    cache_key: str,
) -> _ProxyMetadata | None:
    if not isinstance(entry, dict):
        return None
    if entry.get("source_sha256") != source_sha256 or entry.get("cache_key") != cache_key:
        return None
    proxy_sha256 = entry.get("proxy_sha256")
    width = entry.get("width")
    height = entry.get("height")
    if (
        not isinstance(proxy_sha256, str)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
        or not destination.is_file()
    ):
        return None
    try:
        if _sha256_file(destination) != proxy_sha256:
            return None
    except OSError:
        return None
    return _ProxyMetadata(proxy_sha256=proxy_sha256, width=width, height=height)


def _write_proxy_atomic(
    source: Path,
    destination: Path,
    *,
    overlay: Path,
    staging_dir: Path,
    expected_source_sha256: str,
) -> _ProxyMetadata:
    suffix = source.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES or destination.suffix.lower() != suffix:
        raise ValueError("proxy extension must match the source image")

    image = _read_proxy_image(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.parent.resolve().is_relative_to(overlay):
        raise OSError("invalid proxy destination")

    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".icstex-image-proxy-",
        suffix=suffix,
        dir=staging_dir,
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        image_format = b"png" if suffix == ".png" else b"jpeg"
        writer = QImageWriter(str(temporary), image_format)
        if image_format == b"jpeg":
            writer.setQuality(JPEG_QUALITY)
        if not writer.write(image):
            message = writer.errorString() or "Qt failed to write image proxy"
            del writer
            raise RuntimeError(message)
        del writer
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise OSError("Qt produced an empty image proxy")
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        # Validate before os.replace so a changing source never publishes a
        # proxy that does not match its manifest cache key.
        if _sha256_file(source) != expected_source_sha256:
            raise OSError("source image changed while proxying")
        os.replace(temporary, destination)
        return _ProxyMetadata(
            proxy_sha256=_sha256_file(destination),
            width=image.width(),
            height=image.height(),
        )
    finally:
        temporary.unlink(missing_ok=True)


def _read_proxy_image(source: Path) -> QImage:
    reader = QImageReader(str(source))
    # graphicx/pdfTeX uses the encoded pixel geometry rather than applying
    # EXIF orientation. Keep the proxy's geometry identical to the proper PDF.
    reader.setAutoTransform(False)
    size = reader.size()
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        raise RuntimeError(reader.errorString() or "invalid image dimensions")
    if max(size.width(), size.height()) > MAX_PROXY_EDGE:
        reader.setScaledSize(
            size.scaled(
                QSize(MAX_PROXY_EDGE, MAX_PROXY_EDGE),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
        )
    image = reader.read()
    if image.isNull():
        raise RuntimeError(reader.errorString() or "Qt failed to decode image")
    if max(image.width(), image.height()) > MAX_PROXY_EDGE:
        image = image.scaled(
            QSize(MAX_PROXY_EDGE, MAX_PROXY_EDGE),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    # graphicx uses an image's pixel density to derive its natural size when
    # no width/height option is present. QImage scaling retains the original
    # density, which would make a downscaled proxy physically smaller. Scale
    # density with pixel geometry so preview and final keep the same box.
    # For files without physical-density metadata, pdfTeX's default is 72 dpi;
    # Qt otherwise invents 100 dpi and writes that into the proxy.
    has_density = _has_explicit_physical_density(source)
    source_dpm_x = image.dotsPerMeterX() if has_density else _dpi_to_dpm(TEX_DEFAULT_IMAGE_DPI)
    source_dpm_y = image.dotsPerMeterY() if has_density else _dpi_to_dpm(TEX_DEFAULT_IMAGE_DPI)
    image.setDotsPerMeterX(max(1, round(source_dpm_x * image.width() / size.width())))
    image.setDotsPerMeterY(max(1, round(source_dpm_y * image.height() / size.height())))
    return image


def _dpi_to_dpm(dpi: int) -> int:
    return round(dpi / 0.0254)


def _has_explicit_physical_density(source: Path) -> bool:
    suffix = source.suffix.lower()
    try:
        if suffix == ".png":
            return _png_has_physical_density(source)
        if suffix in (".jpg", ".jpeg"):
            return _jpeg_has_physical_density(source)
    except OSError:
        return False
    return False


def _png_has_physical_density(source: Path) -> bool:
    with source.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            return False
        while True:
            header = handle.read(8)
            if len(header) != 8:
                return False
            length = int.from_bytes(header[:4], "big")
            chunk_type = header[4:]
            if length > 64 * 1024 * 1024:
                return False
            payload = handle.read(length)
            if len(payload) != length or len(handle.read(4)) != 4:
                return False
            if chunk_type == b"pHYs":
                return (
                    length == 9
                    and payload[8] == 1
                    and int.from_bytes(payload[:4], "big") > 0
                    and int.from_bytes(payload[4:8], "big") > 0
                )
            if chunk_type in (b"IDAT", b"IEND"):
                return False


def _jpeg_has_physical_density(source: Path) -> bool:
    with source.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            return False
        while True:
            byte = handle.read(1)
            while byte and byte != b"\xff":
                byte = handle.read(1)
            if not byte:
                return False
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if not marker or marker in (b"\xd9", b"\xda"):
                return False
            marker_value = marker[0]
            if marker_value == 0x01 or 0xD0 <= marker_value <= 0xD7:
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) != 2:
                return False
            length = int.from_bytes(length_bytes, "big")
            if length < 2:
                return False
            payload = handle.read(length - 2)
            if len(payload) != length - 2:
                return False
            if marker_value == 0xE0 and payload.startswith(b"JFIF\x00") and len(payload) >= 12:
                units = payload[7]
                x_density = int.from_bytes(payload[8:10], "big")
                y_density = int.from_bytes(payload[10:12], "big")
                return units in (1, 2) and x_density > 0 and y_density > 0


def _read_manifest(path: Path, *, policy_version: str) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    if value.get("schema") != MANIFEST_SCHEMA or value.get("policy_version") != policy_version:
        return None
    return value


def _manifest_payload(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _clean_overlay(overlay: Path) -> None:
    for directory, directory_names, file_names in os.walk(overlay, topdown=True, followlinks=False):
        base = Path(directory)
        for name in list(directory_names):
            child = base / name
            if child.is_symlink():
                child.unlink(missing_ok=True)
                directory_names.remove(name)
        for name in file_names:
            child = base / name
            if child.is_symlink() or child.suffix.lower() not in ALLOWED_SUFFIXES:
                child.unlink(missing_ok=True)


def _remove_stale_proxies(overlay: Path, published: set[str]) -> None:
    for directory, _directory_names, file_names in os.walk(overlay, topdown=False, followlinks=False):
        base = Path(directory)
        for name in file_names:
            path = base / name
            try:
                relative = path.relative_to(overlay).as_posix()
            except ValueError:
                continue
            if path.is_symlink() or path.suffix.lower() not in ALLOWED_SUFFIXES or relative not in published:
                path.unlink(missing_ok=True)
        if base != overlay:
            try:
                base.rmdir()
            except OSError:
                pass


def _remove_proxy(destination: Path, overlay: Path) -> None:
    if destination.is_relative_to(overlay):
        destination.unlink(missing_ok=True)


def _cache_key(source_sha256: str, policy_version: str) -> str:
    return hashlib.sha256(f"{policy_version}\0{source_sha256}".encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fidelity(proxy_count: int, fallback_count: int) -> str:
    if proxy_count and fallback_count:
        return "mixed"
    if proxy_count:
        return "proxy"
    if fallback_count:
        return "original_fallback"
    return "original"


def _overlay_lock(overlay: Path) -> threading.RLock:
    with _LOCKS_GUARD:
        lock = _OVERLAY_LOCKS.get(overlay)
        if lock is None:
            lock = threading.RLock()
            _OVERLAY_LOCKS[overlay] = lock
        return lock
