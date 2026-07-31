"""腾讯云 COS 正式存储后端。

业务下载优先返回短时预签名 URL，不再把普通对象永久拉回应用服务器；fetch_local 仅供杀毒、
强敏感代理和迁移核验使用，其缓存属于可清理衍生物，不是权威字节。
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from app.core.config import settings
from app.core.exceptions import AppException


def _require(value: str, name: str) -> str:
    v = (value or "").strip()
    if not v:
        raise AppException(
            "FILE_STORAGE_MISCONFIGURED",
            f"对象存储后端已启用，但缺少配置 {name}。请在平台配置或服务器环境变量中填写 COS 参数。",
        )
    return v


class CosStorageBackend:
    kind = "cos"

    def __init__(self, *, region: str = "", bucket: str = "",
                 secret_id: str = "", secret_key: str = "") -> None:
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:  # noqa: BLE001
            raise AppException(
                "FILE_STORAGE_MISCONFIGURED",
                "FILE_STORAGE_BACKEND=cos 需要安装 cos-python-sdk-v5。",
            ) from exc
        self.bucket_name = _require(bucket or getattr(settings, "COS_BUCKET", ""), "COS_BUCKET")
        self.region = _require(region or getattr(settings, "COS_REGION", ""), "COS_REGION")
        self._secret_id = _require(secret_id or getattr(settings, "COS_SECRET_ID", ""), "COS_SECRET_ID")
        self._secret_key = _require(secret_key or getattr(settings, "COS_SECRET_KEY", ""), "COS_SECRET_KEY")
        config = CosConfig(
            Region=self.region,
            SecretId=self._secret_id,
            SecretKey=self._secret_key,
            Token=None,
            Scheme="https",
        )
        self._client = CosS3Client(config)

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

    def persist(self, key: str, staged: Path) -> dict:
        with staged.open("rb") as body:
            response = self._client.put_object(
                Bucket=self.bucket_name,
                Body=body,
                Key=key,
                ServerSideEncryption="AES256",
            ) or {}
        staged.unlink(missing_ok=True)
        return {
            "bucketName": self.bucket_name,
            "objectKey": key,
            "etag": str(response.get("ETag") or "").strip('"'),
        }

    def fetch_local(self, key: str) -> Path | None:
        cache = self._cache_root() / key
        if cache.exists():
            return cache
        if not self.exists(key):
            return None
        cache.parent.mkdir(parents=True, exist_ok=True)
        partial = cache.with_suffix(cache.suffix + ".part")
        partial.unlink(missing_ok=True)
        response = self._client.get_object(Bucket=self.bucket_name, Key=key)
        response["Body"].get_stream_to_file(str(partial))
        partial.replace(cache)
        return cache if cache.exists() else None

    def head_object(self, key: str) -> dict | None:
        try:
            # The official SDK returns metadata. Small test/adaptor clients may
            # signal a successful HEAD call with no response body.
            response = self._client.head_object(Bucket=self.bucket_name, Key=key) or {}
        except Exception:  # noqa: BLE001 - 对外统一为不存在/不可核验
            return None
        return {
            "bucketName": self.bucket_name,
            "objectKey": key,
            "etag": str(response.get("ETag") or "").strip('"'),
            "sizeBytes": int(response.get("Content-Length") or response.get("ContentLength") or 0),
            "lastModified": response.get("Last-Modified") or response.get("LastModified"),
            "serverSideEncryption": response.get("x-cos-server-side-encryption") or response.get("ServerSideEncryption"),
        }

    def presigned_download_url(self, key: str, *, filename: str, expires_seconds: int = 180) -> str:
        expires = min(300, max(60, int(expires_seconds or 180)))
        disposition = f"attachment; filename*=UTF-8''{quote(filename or 'download')}"
        return self._client.get_presigned_url(
            Bucket=self.bucket_name,
            Key=key,
            Method="GET",
            Expired=expires,
            Params={"response-content-disposition": disposition},
            SignHost=True,
        )

    def copy_object(self, source_key: str, target_key: str) -> dict:
        response = self._client.copy_object(
            Bucket=self.bucket_name,
            Key=target_key,
            CopySource={"Bucket": self.bucket_name, "Region": self.region, "Key": source_key},
            ServerSideEncryption="AES256",
        )
        head = self.head_object(target_key) or {}
        return {
            "bucketName": self.bucket_name,
            "objectKey": target_key,
            "etag": head.get("etag") or str(response.get("ETag") or "").strip('"'),
        }

    def exists(self, key: str) -> bool:
        return self.head_object(key) is not None

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket_name, Key=key)
        (self._cache_root() / key).unlink(missing_ok=True)
