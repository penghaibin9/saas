"""文件存储后端单测：本地后端行为回归 + COS 后端逻辑（假客户端，无需真桶）。

端到端的真实上传/下载由 test_graduation_mobile_final.py（本地 MySQL 真库）守，
本文件聚焦存储抽象层：切换、持久化、拉取缓存、错误配置。
"""
from __future__ import annotations

import sys
import types

import pytest

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import storage


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "FILE_STORAGE_BACKEND", "local", raising=False)
    storage.reset_backend()
    yield
    storage.reset_backend()


# ── 本地后端：行为与历史一致 ──

def test_local_backend_is_default():
    assert storage.get_backend().kind == "local"


def test_local_persist_is_inplace_and_fetch_returns_same_path():
    b = storage.get_backend()
    key = "20260713/local-abc.pdf"
    staged = b.staging_path(key)
    staged.write_bytes(b"hello-pdf")
    b.persist(key, staged)  # 本地：no-op，文件已在位
    fetched = b.fetch_local(key)
    assert fetched is not None and fetched.read_bytes() == b"hello-pdf"
    assert fetched == staged  # 落点即读点，零搬运
    assert b.exists(key) is True


def test_local_fetch_missing_returns_none():
    assert storage.get_backend().fetch_local("nope/missing.pdf") is None


def test_local_delete_is_idempotent():
    b = storage.get_backend()
    key = "20260713/del.pdf"
    b.staging_path(key).write_bytes(b"x")
    assert b.exists(key)
    b.delete(key)
    assert not b.exists(key)
    b.delete(key)  # 再删不报错


# ── COS 后端：假客户端，验证上传/拉取/缓存/删除，无需真桶 ──

class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def get_stream_to_file(self, dest: str):
        from pathlib import Path
        Path(dest).write_bytes(self._data)


class _FakeCosClient:
    store: dict[str, bytes] = {}

    def __init__(self, *_a, **_k):
        pass

    def put_object(self, Bucket, Body, Key):  # noqa: N803 (SDK 命名)
        _FakeCosClient.store[Key] = Body.read()

    def get_object(self, Bucket, Key):  # noqa: N803
        return {"Body": _FakeBody(_FakeCosClient.store[Key])}

    def object_exists(self, Bucket, Key):  # noqa: N803
        return Key in _FakeCosClient.store

    def delete_object(self, Bucket, Key):  # noqa: N803
        _FakeCosClient.store.pop(Key, None)


@pytest.fixture()
def _fake_cos(monkeypatch):
    _FakeCosClient.store = {}
    fake_mod = types.ModuleType("qcloud_cos")
    fake_mod.CosConfig = lambda *a, **k: object()
    fake_mod.CosS3Client = _FakeCosClient
    monkeypatch.setitem(sys.modules, "qcloud_cos", fake_mod)
    for k, v in {"FILE_STORAGE_BACKEND": "cos", "COS_REGION": "ap-guangzhou",
                 "COS_BUCKET": "test-bucket-1250000000",
                 "COS_SECRET_ID": "fake-id", "COS_SECRET_KEY": "fake-key"}.items():
        monkeypatch.setattr(settings, k, v, raising=False)
    storage.reset_backend()
    yield


def test_cos_backend_selected_when_configured(_fake_cos):
    assert storage.get_backend().kind == "cos"


def test_cos_persist_uploads_and_clears_staging(_fake_cos):
    b = storage.get_backend()
    key = "20260713/cos-x.pdf"
    staged = b.staging_path(key)
    staged.write_bytes(b"paper-bytes")
    b.persist(key, staged)
    assert _FakeCosClient.store[key] == b"paper-bytes"  # 已上传到 COS
    assert not staged.exists()                            # 本地临时已清
    assert b.exists(key) is True


def test_cos_fetch_uses_cache_then_pulls(_fake_cos):
    b = storage.get_backend()
    key = "20260713/cos-y.pdf"
    # 直接把字节放进 COS（模拟别处上传），本地无缓存
    _FakeCosClient.store[key] = b"remote-only"
    fetched = b.fetch_local(key)
    assert fetched is not None and fetched.read_bytes() == b"remote-only"
    # 二次取命中缓存（删掉远端仍能取到已缓存）
    _FakeCosClient.store.pop(key)
    again = b.fetch_local(key)
    assert again is not None and again.read_bytes() == b"remote-only"


def test_cos_fetch_missing_returns_none(_fake_cos):
    assert storage.get_backend().fetch_local("20260713/ghost.pdf") is None


def test_cos_delete_removes_remote_and_cache(_fake_cos):
    b = storage.get_backend()
    key = "20260713/cos-del.pdf"
    staged = b.staging_path(key)
    staged.write_bytes(b"z")
    b.persist(key, staged)
    assert b.exists(key)
    b.delete(key)
    assert not b.exists(key)
    assert b.fetch_local(key) is None


def test_cos_missing_config_raises(monkeypatch):
    fake_mod = types.ModuleType("qcloud_cos")
    fake_mod.CosConfig = lambda *a, **k: object()
    fake_mod.CosS3Client = _FakeCosClient
    monkeypatch.setitem(sys.modules, "qcloud_cos", fake_mod)
    monkeypatch.setattr(settings, "FILE_STORAGE_BACKEND", "cos", raising=False)
    for k in ("COS_REGION", "COS_BUCKET", "COS_SECRET_ID", "COS_SECRET_KEY"):
        monkeypatch.setattr(settings, k, "", raising=False)
    storage.reset_backend()
    with pytest.raises(AppException) as exc:
        storage.get_backend()
    assert exc.value.code == "FILE_STORAGE_MISCONFIGURED"
