"""One automatic-build admission policy shared by all GUI event sources."""
from __future__ import annotations

from app.core.compiler import BuildPurpose


def automatic_build_purpose(
    *, enabled: bool, authorized: bool, fast_preview: bool,
) -> BuildPurpose | None:
    """Events may invalidate state without being allowed to launch a compiler."""
    if not enabled or not authorized:
        return None
    return BuildPurpose.PREVIEW if fast_preview else BuildPurpose.FINAL
