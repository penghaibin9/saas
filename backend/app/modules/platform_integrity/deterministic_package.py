"""STANDARD_V1 deterministic ZIP writer for frozen evidence packages."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

STANDARD_PROFILE_V1 = "STANDARD_V1"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    path: str
    source_path: Path
    sha256: str
    size_bytes: int


class _Utf8ZipInfo(zipfile.ZipInfo):
    """Pin UTF-8 even when a particular archive happens to contain ASCII names only."""

    def _encodeFilenameFlags(self):  # noqa: N802, SLF001 - zipfile extension point
        return self.filename.encode("utf-8"), self.flag_bits | 0x800


def safe_segment(value: str, *, fallback: str = "file") -> str:
    normalized = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", str(value or "").strip())
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")
    return (normalized or fallback)[:160]


def _info(path: str) -> zipfile.ZipInfo:
    info = _Utf8ZipInfo(filename=path, date_time=_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    info.flag_bits |= 0x800
    return info


def _write_bytes(archive: zipfile.ZipFile, path: str, body: bytes) -> None:
    archive.writestr(_info(path), body, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _copy_stream(reader: BinaryIO, writer: BinaryIO) -> None:
    while True:
        chunk = reader.read(_CHUNK_SIZE)
        if not chunk:
            break
        writer.write(chunk)


def canonical_package_manifest(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"


def write_standard_v1(
    output_path: Path,
    *,
    manifest_payload: dict,
    entries: Iterable[ArchiveEntry],
) -> tuple[int, str]:
    ordered = sorted(entries, key=lambda item: item.path)
    manifest_bytes = canonical_package_manifest(manifest_payload)
    checksums = [(hashlib.sha256(manifest_bytes).hexdigest(), "manifest.json")]
    checksums.extend((entry.sha256.lower(), entry.path) for entry in ordered)
    checksum_bytes = "".join(f"{digest}  {path}\n" for digest, path in checksums).encode("utf-8")

    with zipfile.ZipFile(
        output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
        strict_timestamps=True,
    ) as archive:
        archive.comment = b""
        _write_bytes(archive, "manifest.json", manifest_bytes)
        for entry in ordered:
            with entry.source_path.open("rb") as reader, archive.open(_info(entry.path), "w", force_zip64=True) as writer:
                _copy_stream(reader, writer)
        _write_bytes(archive, "checksums.sha256", checksum_bytes)

    digest = hashlib.sha256()
    size = 0
    with output_path.open("rb") as reader:
        while True:
            chunk = reader.read(_CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


__all__ = ["ArchiveEntry", "STANDARD_PROFILE_V1", "safe_segment", "write_standard_v1"]
