#!/usr/bin/env python3
"""Diagnose WhatsApp media file timestamps vs embedded filename dates.

Compares filesystem creation/modification dates with the YYYYMMDD segment in
WhatsApp export filenames (PTT-/AUD-/IMG-/VID-YYYYMMDD-WAxxxx).

Usage:
    python scripts/check_opus_timestamps.py "C:\\path\\to\\WhatsApp Media"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

WHATSAPP_NAME_RE = re.compile(
    r"^(?:PTT|AUD|IMG|VID)-(\d{8})-WA\d+\.",
    re.IGNORECASE,
)
MEDIA_EXTENSIONS = {".opus", ".jpg", ".mp4"}


@dataclass(frozen=True)
class FileReport:
    path: Path
    created_at: datetime
    modified_at: datetime
    name_date: str | None
    status: str


def stat_created_at(st: os.stat_result) -> float:
    """Return best-effort creation timestamp for the current platform."""
    birthtime = getattr(st, "st_birthtime", None)
    if birthtime is not None:
        return birthtime
    return st.st_ctime


def parse_name_date(file_name: str) -> str | None:
    match = WHATSAPP_NAME_RE.match(file_name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def date_key(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def format_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def classify(created_key: str, modified_key: str, name_date: str | None) -> str:
    if name_date is None:
        return "SEM_PADRAO"
    if created_key == name_date and modified_key == name_date:
        return "OK"
    return "DIVERGENTE"


def iter_media_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
            yield path


def analyze_folder(root: Path) -> list[FileReport]:
    reports: list[FileReport] = []

    for path in sorted(iter_media_files(root)):
        st = path.stat()
        created_ts = stat_created_at(st)
        modified_ts = st.st_mtime
        name_date = parse_name_date(path.name)
        status = classify(date_key(created_ts), date_key(modified_ts), name_date)
        reports.append(
            FileReport(
                path=path,
                created_at=datetime.fromtimestamp(created_ts),
                modified_at=datetime.fromtimestamp(modified_ts),
                name_date=name_date,
                status=status,
            )
        )

    return reports


def print_table(reports: list[FileReport]) -> None:
    headers = ("arquivo", "data_criacao", "data_modificacao", "data_no_nome", "status")
    rows: list[tuple[str, str, str, str, str]] = []

    for report in reports:
        rows.append(
            (
                report.path.name,
                format_ts(report.created_at.timestamp()),
                format_ts(report.modified_at.timestamp()),
                report.name_date or "-",
                report.status,
            )
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def fmt_row(cells: tuple[str, ...]) -> str:
        return " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(cells))

    print(fmt_row(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(fmt_row(row))


def print_summary(reports: list[FileReport]) -> None:
    ok = sum(1 for report in reports if report.status == "OK")
    divergent = sum(1 for report in reports if report.status == "DIVERGENTE")
    no_pattern = sum(1 for report in reports if report.status == "SEM_PADRAO")

    print()
    print("Resumo:")
    print(f"  Total de arquivos analisados: {len(reports)}")
    print(f"  OK: {ok}")
    print(f"  DIVERGENTE: {divergent}")
    print(f"  SEM_PADRAO (nome fora do padrão WhatsApp): {no_pattern}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compara datas de criação/modificação de mídias WhatsApp "
            "com a data embutida no nome do arquivo."
        )
    )
    parser.add_argument(
        "folder",
        help="Pasta raiz para varrer recursivamente (.opus, .jpg, .mp4)",
    )
    args = parser.parse_args(argv)

    root = Path(args.folder).expanduser()
    if not root.exists():
        print(f"Erro: caminho não encontrado: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"Erro: caminho não é uma pasta: {root}", file=sys.stderr)
        return 1

    reports = analyze_folder(root)
    if not reports:
        print(f"Nenhum arquivo .opus/.jpg/.mp4 encontrado em {root}")
        return 0

    print_table(reports)
    print_summary(reports)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
