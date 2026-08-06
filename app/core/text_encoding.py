from __future__ import annotations

from dataclasses import dataclass
import codecs
import os
from pathlib import Path
import re
import stat
import tempfile


_MAGIC_ENCODING_RE = re.compile(
    r"^\s*%\s*!\s*T[eE]X\s+encoding\s*=\s*(?P<encoding>[^%]+?)\s*$",
    re.IGNORECASE,
)
_INPUTENC_RE = re.compile(
    r"\\usepackage\s*\[(?P<options>[^\]]+)\]\s*\{inputenc\}",
    re.IGNORECASE,
)
_ENCODING_ALIASES = {
    "utf8": "utf-8",
    "utf8x": "utf-8",
    "utf8unicode": "utf-8",
    "latin1": "iso-8859-1",
    "isolatin1": "iso-8859-1",
    "iso88591": "iso-8859-1",
    "ansinew": "cp1252",
    "windowslatin1": "cp1252",
    "windows1252": "cp1252",
    "cp1252": "cp1252",
    "applemac": "mac_roman",
    "macosroman": "mac_roman",
}


@dataclass(frozen=True)
class DecodedLatexText:
    text: str
    encoding: str


class LatexTextDecodeError(UnicodeError):
    def __init__(self, encoding: str, reason: str) -> None:
        self.encoding = encoding
        self.reason = reason
        super().__init__(f"Could not decode LaTeX source as {encoding}: {reason}")


def decode_latex_bytes(data: bytes, *, encoding: str | None = None) -> DecodedLatexText:
    if encoding is None and data.startswith(codecs.BOM_UTF8):
        return _decode(data, "utf-8-sig")

    requested = encoding or declared_latex_encoding(data) or "utf-8"
    return _decode(data, requested)


def write_latex_text_atomic(path: str | Path, text: str, *, encoding: str) -> None:
    """Encode before touching disk, then replace the file from its directory."""
    destination = Path(path)
    target = destination.resolve() if destination.is_symlink() else destination
    payload = text.encode(encoding)
    target.parent.mkdir(parents=True, exist_ok=True)
    original_mode = target.stat().st_mode if target.exists() else None
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if original_mode is not None:
            os.chmod(temporary, stat.S_IMODE(original_mode))
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def declared_latex_encoding(data: bytes) -> str | None:
    header = data[:16384].decode("latin-1")
    for line in header.splitlines()[:80]:
        match = _MAGIC_ENCODING_RE.match(line)
        if match:
            return match.group("encoding").strip()

    inputenc = _INPUTENC_RE.search(header)
    if inputenc:
        for option in inputenc.group("options").split(","):
            candidate = option.strip()
            if _canonical_encoding(candidate) is not None:
                return candidate
    return None


def _decode(data: bytes, requested: str) -> DecodedLatexText:
    canonical = _canonical_encoding(requested)
    if canonical is None:
        raise LatexTextDecodeError(requested, "unknown encoding name")
    try:
        return DecodedLatexText(data.decode(canonical), canonical)
    except UnicodeDecodeError as exc:
        raise LatexTextDecodeError(canonical, str(exc)) from exc


def _canonical_encoding(value: str) -> str | None:
    clean = value.strip().strip("'\"")
    key = re.sub(r"[\s_-]+", "", clean).casefold()
    alias = _ENCODING_ALIASES.get(key)
    if alias is not None:
        return codecs.lookup(alias).name
    try:
        return codecs.lookup(clean).name
    except LookupError:
        return None
