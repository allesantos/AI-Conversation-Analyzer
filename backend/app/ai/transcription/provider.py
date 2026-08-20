from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class TranscriptionUsage:
    provider: str
    model: str
    duration_seconds: float | None = None


@dataclass(slots=True, frozen=True)
class TranscriptionResult:
    text: str
    usage: TranscriptionUsage


class TranscriptionProvider(Protocol):
    async def transcribe_file(self, file_path: str, *, filename: str) -> TranscriptionResult: ...
