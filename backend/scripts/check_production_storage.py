"""发布验收文件存储探针。

COS 模式执行一个固定 healthcheck 小对象的写入+删除，验证真实凭据/桶/地域链；
local 模式只确认当前后端类型，不打印路径或密钥。该脚本只用于发布验收，不挂在高频 /health。
"""
from __future__ import annotations

import sys
from pathlib import Path

# The systemd unit supplies PYTHONPATH, while release acceptance invokes this
# verifier directly from ``backend/``.  Resolve the same application package
# in both modes so the storage probe tests the configured backend rather than
# failing during import.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.storage.config import effective_config, test_connection


def main() -> int:
    try:
        config = effective_config()
        backend = str(config.get("backend") or "local").lower()
    except Exception as exc:  # noqa: BLE001
        print(f"storage_check_failed: config:{type(exc).__name__}", file=sys.stderr)
        return 1

    if backend == "local":
        print("storage_ready: local")
        return 0
    if backend != "cos":
        print("storage_check_failed: unsupported backend", file=sys.stderr)
        return 1

    try:
        result = test_connection()
    except Exception as exc:  # noqa: BLE001
        print(f"storage_check_failed: cos_probe:{type(exc).__name__}", file=sys.stderr)
        return 1
    if not bool(result.get("ok")):
        # test_connection 的 provider 原始错误不写日志，避免意外带出部署细节。
        print("storage_check_failed: cos probe failed", file=sys.stderr)
        return 1

    print("storage_ready: cos write-delete probe ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
