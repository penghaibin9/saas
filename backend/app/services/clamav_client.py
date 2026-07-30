"""ClamAV clamd INSTREAM 客户端；按块发送文件，禁止整文件读入内存。"""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from pathlib import Path

from app.services.file_scan_config import FileScanConfig, get_file_scan_config


class ClamAVError(RuntimeError):
    """ClamAV 通用错误。"""


class ClamAVUnavailable(ClamAVError):
    """扫描服务不可连接。"""


class ClamAVProtocolError(ClamAVError):
    """扫描服务返回无法识别的协议响应。"""


@dataclass(frozen=True)
class ClamAVScanResult:
    status: str
    signature: str | None
    raw: str

    @property
    def clean(self) -> bool:
        return self.status == "CLEAN"

    @property
    def infected(self) -> bool:
        return self.status == "INFECTED"


class ClamAVClient:
    def __init__(self, config: FileScanConfig | None = None):
        self.config = config or get_file_scan_config()

    def _connect(self) -> socket.socket:
        try:
            if self.config.unix_socket:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self.config.connect_timeout)
                sock.connect(self.config.unix_socket)
            else:
                sock = socket.create_connection(
                    (self.config.host, self.config.port),
                    timeout=self.config.connect_timeout,
                )
            sock.settimeout(self.config.read_timeout)
            return sock
        except OSError as exc:
            raise ClamAVUnavailable(f"ClamAV unavailable: {exc}") from exc

    @staticmethod
    def _read_response(sock: socket.socket, limit: int = 64 * 1024) -> str:
        chunks: list[bytes] = []
        size = 0
        while size < limit:
            try:
                part = sock.recv(min(4096, limit - size))
            except OSError as exc:
                raise ClamAVUnavailable(f"ClamAV read failed: {exc}") from exc
            if not part:
                break
            chunks.append(part)
            size += len(part)
            if b"\0" in part or b"\n" in part:
                break
        return b"".join(chunks).rstrip(b"\0\r\n").decode("utf-8", errors="replace")

    def command(self, command: str) -> str:
        with self._connect() as sock:
            try:
                sock.sendall(f"z{command}\0".encode("ascii"))
            except OSError as exc:
                raise ClamAVUnavailable(f"ClamAV send failed: {exc}") from exc
            return self._read_response(sock)

    def ping(self) -> bool:
        return self.command("PING").strip().upper() == "PONG"

    def version(self) -> str:
        response = self.command("VERSION").strip()
        if not response:
            raise ClamAVProtocolError("empty VERSION response")
        return response

    def scan_path(self, path: str | Path) -> ClamAVScanResult:
        file_path = Path(path)
        if not file_path.is_file():
            raise ClamAVError(f"scan target missing: {file_path}")
        with self._connect() as sock:
            try:
                sock.sendall(b"zINSTREAM\0")
                with file_path.open("rb") as stream:
                    while True:
                        chunk = stream.read(self.config.chunk_size)
                        if not chunk:
                            break
                        sock.sendall(struct.pack("!I", len(chunk)))
                        sock.sendall(chunk)
                sock.sendall(struct.pack("!I", 0))
            except OSError as exc:
                raise ClamAVUnavailable(f"ClamAV stream failed: {exc}") from exc
            raw = self._read_response(sock)
        upper = raw.upper()
        if upper.endswith(" OK") or upper == "OK":
            return ClamAVScanResult("CLEAN", None, raw)
        if upper.endswith(" FOUND"):
            body = raw.rsplit(" FOUND", 1)[0]
            signature = body.split(":", 1)[-1].strip() or "UNKNOWN"
            return ClamAVScanResult("INFECTED", signature, raw)
        if "ERROR" in upper:
            raise ClamAVProtocolError(raw)
        raise ClamAVProtocolError(f"unknown ClamAV response: {raw!r}")
