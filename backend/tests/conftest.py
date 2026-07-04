"""pytest 公共夹具：默认 DB_ENABLED=false（mock 模式），共享 TestClient 与登录令牌。"""
from __future__ import annotations

import os

os.environ.setdefault("DB_ENABLED", "false")

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
    from app.core.config import settings
    from app.db.session import reset_state
    url = f"sqlite+pysqlite:///{(tmp_path / 'test_dev.db').as_posix()}"
    old_enabled, old_url = settings.DB_ENABLED, settings.DATABASE_URL
    settings.DB_ENABLED, settings.DATABASE_URL = True, url
    reset_state()
    from app.db.base import metadata
    from app.db.session import get_engine, get_sessionmaker
    metadata.create_all(bind=get_engine())
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

