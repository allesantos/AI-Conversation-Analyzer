"""Extensões de mídia compartilhadas entre parser e upload de áudio."""

AUDIO_EXTENSIONS = frozenset({".opus", ".ogg", ".mp3", ".m4a", ".wav", ".aac", ".amr"})
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"})


def is_audio_filename(filename: str) -> bool:
    lowered = filename.lower().strip()
    return any(lowered.endswith(ext) for ext in AUDIO_EXTENSIONS)
