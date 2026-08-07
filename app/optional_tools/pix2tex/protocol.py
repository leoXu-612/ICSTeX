"""JSON Lines protocol between the GUI and the pix2tex sidecar worker."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RecognitionRequest:
    request_id: str
    image_path: Path
    temperature: float = 0.01
    use_resizer: bool = True

    def to_message(self) -> dict:
        return {
            "id": self.request_id,
            "method": "recognize",
            "params": {
                "image_path": str(self.image_path),
                "temperature": self.temperature,
                "use_resizer": self.use_resizer,
            },
        }


@dataclass(frozen=True)
class RecognitionResult:
    request_id: str
    latex: str
    elapsed_ms: int
    model_version: str
    source_image_size: tuple[int, int] = (0, 0)


def encode_message(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=True) + "\n"


def decode_message(line: str) -> dict[str, Any]:
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise ValueError("protocol message must be an object")
    return payload
