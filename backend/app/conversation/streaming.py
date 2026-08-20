"""Leitura linha a linha com limite de bytes. Sem carregar o arquivo inteiro como str."""

from __future__ import annotations

from collections.abc import Iterator

from app.core.exceptions import PayloadTooLargeError

_CHUNK_SIZE = 65_536


def iter_limited_text_lines(binary: object, max_bytes: int) -> Iterator[str]:
    total = 0
    leftover = b""
    first_line = True
    while True:
        chunk = binary.read(_CHUNK_SIZE)  # type: ignore[attr-defined]
        if chunk:
            total += len(chunk)
            if total > max_bytes:
                raise PayloadTooLargeError("Arquivo excede o tamanho máximo permitido")
            leftover += chunk
        newline_at = leftover.find(b"\n")
        while newline_at >= 0:
            raw_line = leftover[:newline_at]
            leftover = leftover[newline_at + 1 :]
            yield _decode_line(raw_line, strip_bom=first_line)
            first_line = False
            newline_at = leftover.find(b"\n")
        if not chunk:
            if leftover:
                yield _decode_line(leftover, strip_bom=first_line)
            break


def _decode_line(raw_line: bytes, *, strip_bom: bool) -> str:
    if raw_line.endswith(b"\r"):
        raw_line = raw_line[:-1]
    line = raw_line.decode("utf-8", errors="replace")
    if strip_bom:
        line = line.lstrip("\ufeff")
    return line
