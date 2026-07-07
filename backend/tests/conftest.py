"""pytest 公共夹具：强制隔离生产 MySQL，默认 mock 模式（不读写 saas_lifecycle）。"""
from __future__ import annotations

import os
from pathlib import Path

# 必须在 import app 之前覆盖（防止 shell `export $(grep .env)` 把 DB_ENABLED=true 带进 pytest）
os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "false"
os.environ["DATABASE_URL"] = ""
# MySQL-only 收口：优先使用显式 TEST_DATABASE_URL。
# 若进程环境未提供，则兜底读取 backend/.env 中的 TEST_DATABASE_URL，避免拼出 saas_user:@...。
if "TEST_DATABASE_URL" not in os.environ:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "TEST_DATABASE_URL" and v.strip():
                os.environ["TEST_DATABASE_URL"] = v.strip()
                break
if "TEST_DATABASE_URL" not in os.environ:
    raise RuntimeError("TEST_DATABASE_URL 未配置，拒绝回落 SQLite；请在 backend/.env 显式提供 MySQL 测试库连接串。")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def auth_headers(client: TestClient) -> dict:
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


@pytest.fixture(autouse=True)
def _reset_security_state():
    from app.core.token_store import reset_all_for_tests
    reset_all_for_tests()
    yield


@pytest.fixture()
def db_mode(tmp_path):
    """真库模式夹具。数据库来自 TEST_DATABASE_URL（MySQL-only 收口后默认 MySQL）。
    - MySQL：在专用 student_lifecycle_test 库上 drop+create 重建干净表结构（每测试隔离）。
    - sqlite（含 :memory:）：legacy 临时演示，改用每测试独立 tmp 文件；不得当 MySQL 验收。
    MySQL 不可达时本夹具会直接连接失败报错（不静默回落 sqlite 冒充通过）。"""
    from app.core.config import settings
    from app.db.session import reset_state
    test_url = os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL
    is_sqlite = test_url.startswith("sqlite")
    if is_sqlite:
        test_url = f"sqlite+pysqlite:///{(tmp_path / 'test_dev.db').as_posix()}"
    old_enabled, old_url = settings.DB_ENABLED, settings.DATABASE_URL
    settings.DB_ENABLED, settings.DATABASE_URL = True, test_url
    reset_state()
    from app.db.base import metadata
    from app.db.session import get_engine, get_sessionmaker
    engine = get_engine()
    if not is_sqlite:
        metadata.drop_all(bind=engine)   # MySQL 测试库：每测试重建干净结构
    metadata.create_all(bind=engine)
    # 最小种子
    from datetime import datetime, timedelta
    from app.models import (StudentContact, StudentProfile, UnifiedMessage, UnifiedTodo,
                            WorkflowInstance, WorkflowTask)
    TID = 1000000000000000001
    db = get_sessionmaker()()
    s = StudentProfile(tenant_id=TID, student_no="2023115001", real_name="赵一凡",
                       current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
    db.add(s); db.flush()
    db.add(StudentContact(tenant_id=TID, student_id=s.id, contact_type="PHONE",
                          contact_value_encrypted="13812340001", is_primary=True,
                          verified_status="VERIFIED"))
    inst = WorkflowInstance(tenant_id=TID, workflow_code="wf_student", source_module="student",
                            source_biz_type="PROFILE_CORRECTION", source_biz_id=s.id,
                            applicant_id=1, title="赵一凡 · 学籍信息变更", status="RUNNING",
                            remark="赵一凡")
    db.add(inst); db.flush()
    task = WorkflowTask(tenant_id=TID, instance_id=inst.id, node_code="COUNSELOR_REVIEW",
                        assignee_id=1, status="PENDING",
                        deadline_at=datetime.utcnow() + timedelta(days=2))
    db.add(task)
    db.add(UnifiedTodo(tenant_id=TID, source_module="student", source_biz_id=1, todo_type="APPROVAL",
                       assignee_id=1, title="处理学籍变更审批", status="PENDING"))
    db.add(UnifiedMessage(tenant_id=TID, receiver_id=1, title="测试消息", status="UNREAD"))
    db.commit()
    ids = {"student": s.id, "task": task.id}
    db.close()
    yield ids
    settings.DB_ENABLED, settings.DATABASE_URL = old_enabled, old_url
    reset_state()

