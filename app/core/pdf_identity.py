"""Content evidence for reusing a displayed PDF, separate from build freshness."""
from dataclasses import dataclass
from pathlib import Path

from app.core.file_observation import FileSignature, file_signature
from app.core.project_dependencies import InputObservation, observe_input


@dataclass(frozen=True)
class PdfContentIdentity:
    path: Path
    digest: str
    signature: FileSignature

    def still_matches(self, path: Path) -> bool:
        # Metadata is only an invalidation check for already-hashed content.
        return (path == self.path and self.signature is not None and not path.is_symlink()
                and file_signature(path) == self.signature)


def capture_pdf_identity(path: Path, scope: Path, *, observation: InputObservation | None = None,
                         observed_from: FileSignature = None) -> PdfContentIdentity | None:
    before = observed_from if observation is not None else file_signature(path)
    if before is None:
        return None
    observed = observation if observation is not None else observe_input(path, scope, allow_internal=True)
    after = file_signature(path)
    if before != after or not observed.stable or not observed.readable or not observed.digest:
        return None
    return PdfContentIdentity(path, observed.digest, after)
