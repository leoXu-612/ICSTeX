"""Recognition domain models and provider protocol (ICSTeX 2.1)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class RecognitionKind(str, Enum):
    FORMULA = "formula"
    TEXT = "text"


@dataclass(frozen=True)
class RecognitionRequest:
    request_id: str
    kind: RecognitionKind
    image_path: Path | None = None
    image_bytes: bytes | None = None
    crop: tuple[int, int, int, int] | None = None
    language_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecognitionRegion:
    text: str
    confidence: float | None = None
    box: tuple[
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
    ] | None = None


@dataclass(frozen=True)
class RecognitionResult:
    request_id: str
    kind: RecognitionKind
    provider_id: str
    latex: str | None = None
    text: str | None = None
    regions: tuple[RecognitionRegion, ...] = ()
    elapsed_ms: float | None = None
    provider_version: str | None = None
    model_version: str | None = None


class RecognitionProvider(Protocol):
    provider_id: str

    def capabilities(self) -> set[RecognitionKind]:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def health_check(self) -> bool:
        ...

    def recognize(self, request: RecognitionRequest) -> RecognitionResult:
        ...


class RecognitionRouter:
    """Route by kind: formula -> pix2tex, text -> rapidocr."""

    def __init__(self, providers: list[RecognitionProvider]) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}

    def provider_for(self, kind: RecognitionKind) -> RecognitionProvider | None:
        default = {
            RecognitionKind.FORMULA: "pix2tex",
            RecognitionKind.TEXT: "rapidocr",
        }
        provider = self._providers.get(default[kind])
        if provider is not None and kind in provider.capabilities():
            return provider
        return next(
            (candidate for candidate in self._providers.values() if kind in candidate.capabilities()),
            None,
        )

    def recognize(self, request: RecognitionRequest) -> RecognitionResult:
        provider = self.provider_for(request.kind)
        if provider is None:
            raise ValueError(f"no provider for {request.kind.value}")
        return provider.recognize(request)
