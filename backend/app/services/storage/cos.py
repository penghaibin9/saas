"""腾讯云对象存储 COS 后端。

写侧：字节先由 file_service 流式写到本地临时区（.staging/），persist 时上传到 COS
再删临时。读侧：fetch_local 先查本地缓存（.coscache/），未命中则从 COS 拉回缓存返回。
缓存命中避免重复下行，冷文件用完仍留缓存（可由后续清理任务回收，不影响正确性）。

依赖 cos-python-sdk-v5（qcloud_cos），延迟导入——未安装或未配置时构造即报错，
但只在 FILE_STORAGE_BACKEND=cos 时才会走到，本地模式完全不受影响。
密钥只从 settings 读取（环境变量 / .env），本模块不硬编码任何凭据。
"""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.exceptions import AppException


def _require(value: str, name: str) -> str:
    v = (value or "").strip()
    if not v:
        raise AppException(
            "FILE_STORAGE_MISCONFIGURED",
            f"对象存储后端已启用，但缺少配置 {name}。请在服务器环境变量/.env 中填写 COS 参数。",
        )
    return v


class CosStorageBackend:
    kind = "cos"

    def __init__(self) -> None:
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:  # noqa: BLE001
            raise AppException(
                "FILE_STORAGE_MISCONFIGURED",
                "FILE_STORAGE_BACKEND=cos 需要安装 cos-python-sdk-v5（pip install cos-python-sdk-v5）。",
            ) from exc
        self._bucket = _require(getattr(settings, "COS_BUCKET", ""), "COS_BUCKET")
        region = _require(getattr(settings, "COS_REGION", ""), "COS_REGION")
        secret_id = _require(getattr(settings, "COS_SECRET_ID", ""), "COS_SECRET_ID")
        secret_key = _require(getattr(settings, "COS_SECRET_KEY", ""), "COS_SECRET_KEY")
        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key,
                           Token=None, Scheme="https")
        self._client = CosS3Client(config)

    # ── 本地临时/缓存目录（复用 UPLOAD_DIR 下的隐藏子目录）──
    def _staging_root(self) -> Path:
        d = Path(settings.UPLOAD_DIR or "./uploads") / ".staging"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _cache_root(self) -> Path:
        d = Path(settings.UPLOAD_DIR or "./uploads") / ".coscache"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def staging_path(self, key: str) -> Path:
        target = self._staging_root() / key
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def persist(self, key: str, staged: Path) -> None:
        with staged.open("rb") as body:
            self._client.put_object(Bucket=self._bucket, Body=body, Key=key)
        # 上传成功后清理本地临时；同时预热读缓存，避免刚传就下要再拉一次。
        cache = self._cache_root() / key
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            staged.replace(cache)
        except OSError:
            staged.unlink(missing_ok=True)

    def fetch_local(self, key: str) -> Path | None:
        cache = self._cache_root() / key
        if cache.exists():
            return cache
        if not self.exists(key):
            return None
        cache.parent.mkdir(parents=True, exist_ok=True)
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        resp["Body"].get_stream_to_file(str(cache))
        return cache if cache.exists() else None

    def exists(self, key: str) -> bool:
        return bool(self._client.object_exists(Bucket=self._bucket, Key=key))

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception:  # noqa: BLE001 — 删除幂等，对象不存在不阻断
            pass
        (self._cache_root() / key).unlink(missing_ok=True)
