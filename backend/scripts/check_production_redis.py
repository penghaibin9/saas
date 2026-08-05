"""生产/预发 Redis 启动前闸门。

用途：在启动多 worker 后端前，验证 REDIS_URL、连通性、写入与单次原子消费。
不会打印密码、完整连接串或临时值。
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_backend_env() -> None:
    env_file = BACKEND_DIR / ".env"
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_file, override=False)
        return
    except Exception:
        pass
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _fail(message: str) -> int:
    print(f"❌ Redis 生产闸门失败：{message}", file=sys.stderr)
    return 1


def main() -> int:
    _load_backend_env()
    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    deployment = os.environ.get("DEPLOYMENT_MODE", "local").strip().lower()
    strict = app_env in {"production", "staging"} or deployment in {"production", "staging"}
    redis_url = os.environ.get("REDIS_URL", "").strip()

    if not redis_url:
        if strict:
            return _fail("APP_ENV/DEPLOYMENT_MODE 为生产或预发时必须设置 REDIS_URL")
        print("ℹ️ 非生产环境未设置 REDIS_URL，跳过 Redis 生产闸门")
        return 0

    parsed = urlparse(redis_url)
    if parsed.scheme not in {"redis", "rediss"}:
        return _fail("REDIS_URL 仅允许 redis:// 或 rediss://")
    if not parsed.hostname:
        return _fail("REDIS_URL 缺少主机名")
    if deployment == "production" and parsed.hostname.lower() in {"127.0.0.1", "localhost", "::1"}:
        if not _truthy("ALLOW_LOCAL_REDIS_IN_PRODUCTION"):
            return _fail("生产部署禁止连接本机 Redis；确为单机私有化部署时显式设置 ALLOW_LOCAL_REDIS_IN_PRODUCTION=true")

    try:
        import redis
    except ModuleNotFoundError:
        return _fail("缺少 redis Python 包，请先安装 backend/requirements.txt")

    connect_timeout = float(os.environ.get("REDIS_CONNECT_TIMEOUT", "2") or 2)
    socket_timeout = float(os.environ.get("REDIS_SOCKET_TIMEOUT", "2") or 2)
    prefix = os.environ.get("REDIS_KEY_PREFIX", "school-lifecycle").strip().strip(":") or "school-lifecycle"
    client = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=connect_timeout,
        socket_timeout=socket_timeout,
        health_check_interval=30,
    )
    key = f"{prefix}:preflight:{secrets.token_hex(12)}"
    value = secrets.token_urlsafe(24)
    try:
        if client.ping() is not True:
            return _fail("PING 未返回成功")
        if client.set(key, value, ex=30, nx=True) is not True:
            return _fail("临时键写入失败")
        if client.get(key) != value:
            return _fail("临时键读取结果不一致")
        try:
            consumed = client.execute_command("GETDEL", key)
        except Exception:
            consumed = client.eval(
                "local v=redis.call('GET',KEYS[1]); if v then redis.call('DEL',KEYS[1]) end; return v",
                1,
                key,
            )
        if consumed != value or client.exists(key):
            return _fail("验证码所需的单次原子消费能力验收失败")
    except Exception as exc:  # noqa: BLE001
        return _fail(f"连接或读写失败（{type(exc).__name__}）")
    finally:
        try:
            client.delete(key)
            client.close()
        except Exception:
            pass

    tls = "TLS" if parsed.scheme == "rediss" else "非 TLS（应仅用于可信内网）"
    db = (parsed.path or "/0").lstrip("/") or "0"
    port = parsed.port or (6380 if parsed.scheme == "rediss" else 6379)
    print(f"✅ Redis 生产闸门通过：host={parsed.hostname} port={port} db={db} mode={tls} prefix={prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
