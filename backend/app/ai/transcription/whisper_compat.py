from __future__ import annotations

from pathlib import Path

WHISPER_SUPPORTED_SUFFIXES = frozenset(
    {".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga", ".oga", ".ogg", ".wav", ".webm"}
)

# WhatsApp voice notes use Ogg Opus but often carry a .opus extension.
_SUFFIX_ALIASES_FOR_WHISPER = {
    ".opus": ".ogg",
}


def whisper_upload_filename(*, file_path: str, original_filename: str | None = None) -> str:
    """Return a filename Whisper accepts for the given stored audio file."""
    candidates = [original_filename or "", Path(file_path).name]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        suffix = path.suffix.lower()
        alias = _SUFFIX_ALIASES_FOR_WHISPER.get(suffix)
        if alias is not None:
            return f"{path.stem}{alias}"
        if suffix in WHISPER_SUPPORTED_SUFFIXES:
            return path.name
    return Path(file_path).name
