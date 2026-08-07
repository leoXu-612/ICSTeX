"""Model manifest read/validation for the pix2tex sidecar."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelManifest:
    version: str
    checkpoint: Path
    image_resizer: Path
    tokenizer: Path
    config: Path

    def missing_files(self) -> list[Path]:
        return [path for path in (self.checkpoint, self.image_resizer, self.tokenizer, self.config) if not path.exists()]


def load_manifest(path: Path) -> ModelManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent
    return ModelManifest(
        version=str(payload.get("version", "")),
        checkpoint=root / payload["checkpoint"],
        image_resizer=root / payload["image_resizer"],
        tokenizer=root / payload["tokenizer"],
        config=root / payload["config"],
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
