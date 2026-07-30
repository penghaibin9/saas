from __future__ import annotations

import socketserver
import struct
import threading
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from app.services.clamav_client import ClamAVClient, ClamAVUnavailable
from app.services.file_content_security import validate_content_path
from app.services.file_scan_config import FileScanConfig

EICAR = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)


class _ClamdHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        command = bytearray()
        while not command.endswith(b"\0"):
            part = self.request.recv(1)
            if not part:
                return
            command.extend(part)
        cmd = bytes(command).rstrip(b"\0").lstrip(b"z").decode("ascii")
        if cmd == "PING":
            self.request.sendall(b"PONG\0")
            return
        if cmd == "VERSION":
            self.request.sendall(b"ClamAV 1.4.3/27600/Test\0")
            return
        if cmd != "INSTREAM":
            self.request.sendall(b"UNKNOWN COMMAND ERROR\0")
            return
        payload = bytearray()
        while True:
            raw_size = self._read_exact(4)
            if not raw_size:
                return
            size = struct.unpack("!I", raw_size)[0]
            if size == 0:
                break
            payload.extend(self._read_exact(size))
        if EICAR in payload:
            self.request.sendall(b"stream: Eicar-Test-Signature FOUND\0")
        else:
            self.request.sendall(b"stream: OK\0")

    def _read_exact(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            part = self.request.recv(size - len(chunks))
            if not part:
                return b""
            chunks.extend(part)
        return bytes(chunks)


class _ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@contextmanager
def fake_clamd():
    server = _ThreadingServer(("127.0.0.1", 0), _ClamdHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def config(port: int) -> FileScanConfig:
    return FileScanConfig(
        enabled=True,
        required=True,
        host="127.0.0.1",
        port=port,
        unix_socket="",
        connect_timeout=0.2,
        read_timeout=2.0,
        chunk_size=16,
        max_attempts=3,
        retry_base_seconds=1,
        stale_lock_seconds=60,
        batch_size=1,
        poll_seconds=0.2,
    )


def test_clamav_instream_rejects_eicar_and_allows_clean(tmp_path: Path) -> None:
    infected = tmp_path / "eicar.txt"
    infected.write_bytes(EICAR)
    clean = tmp_path / "clean.txt"
    clean.write_text("hello", encoding="utf-8")
    with fake_clamd() as port:
        client = ClamAVClient(config(port))
        assert client.ping() is True
        assert client.version().startswith("ClamAV ")
        bad = client.scan_path(infected)
        good = client.scan_path(clean)
    assert bad.infected is True
    assert bad.signature == "Eicar-Test-Signature"
    assert good.clean is True


def test_clamav_unavailable_is_not_treated_as_clean(tmp_path: Path) -> None:
    target = tmp_path / "clean.txt"
    target.write_text("hello", encoding="utf-8")
    client = ClamAVClient(config(9))
    with pytest.raises(ClamAVUnavailable):
        client.scan_path(target)


def test_ooxml_validation_never_uses_path_read_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "sample.docx"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")

    def forbidden(_self: Path) -> bytes:
        raise AssertionError("Path.read_bytes() must not be used for upload scanning")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setenv("CLAMAV_ENABLED", "true")
    monkeypatch.setenv("FILE_SCAN_REQUIRED", "true")
    mime, status = validate_content_path(
        filename=target.name,
        declared_content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        path=target,
        ext="docx",
        biz_type="GRADUATION_MATERIAL",
        source="USER",
    )
    assert mime == "application/zip"
    assert status == "QUARANTINED"
