"""生产文件扫描启动前检查。

只验证配置和 ClamAV clamd 可用性，不扫描业务文件、不打印地址/密钥/业务数据。
用于 systemd file-scan worker 的 ExecStartPre 和发布验收。
"""
from __future__ import annotations

import sys

from app.core.config import settings
from app.services.clamav_client import ClamAVClient
from app.services.file_scan_config import get_file_scan_config


def main() -> int:
    config = get_file_scan_config()

    # production 下 file_scan_config.required 恒为 True；显式再判断一次，避免未来配置回归。
    if settings.is_prod and not config.required:
        print("file_scan_check_failed: production scan gate is not required", file=sys.stderr)
        return 1
    if config.required and not config.enabled:
        print("file_scan_check_failed: ClamAV scanning is required but disabled", file=sys.stderr)
        return 1
    if not config.enabled:
        print("file_scan_check_skipped: scanner disabled in non-production")
        return 0

    try:
        client = ClamAVClient(config)
        if not client.ping():
            print("file_scan_check_failed: ClamAV PING did not return PONG", file=sys.stderr)
            return 1
        # VERSION 同时验证完整命令/读取链，不输出原始版本串，避免把环境细节带进日志。
        client.version()
    except Exception as exc:  # noqa: BLE001 - CLI 必须把依赖不可用转换为非零退出码
        print(f"file_scan_check_failed: {type(exc).__name__}", file=sys.stderr)
        return 1

    print("file_scan_ready: clamav reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
