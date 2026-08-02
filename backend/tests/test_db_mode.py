"""DB 真实模式端到端：临时 SQLite 建表+种子 → 学生/审批/待办/消息/审计 全走数据库。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.db.session import reset_state


def test_students_from_db(client, auth_headers, db_mode):
    body = client.get("/api/v1/students", headers=auth_headers).json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert body["data"]["total"] == 1 and items[0]["studentNo"] == "2023115001"
    assert items[0]["phoneMasked"] == "138****0001"
    detail = client.get(f"/api/v1/students/{db_mode['student']}", headers=auth_headers).json()["data"]
    assert detail["contacts"] and detail["timeline"] is not None


def test_students_filter_and_paginate_in_database(client, auth_headers, db_mode):
    """组织筛选、分页和联系方式批量加载必须保持租户隔离与准确总数。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentContact, StudentProfile

    tenant_id = 1000000000000000001
    other_tenant = 1000000000000000002
    db = get_sessionmaker()()
    college = College(tenant_id=tenant_id, college_name="信息工程学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=tenant_id, college_id=college.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    school_class = SchoolClass(tenant_id=tenant_id, major_id=major.id,
                               class_name="软件一班", status="ACTIVE")
    db.add(school_class); db.flush()
    for index in (1, 2):
        student = StudentProfile(
            tenant_id=tenant_id, student_no=f"2026DB{index:03d}", real_name=f"分页学生{index}",
            college_id=college.id, major_id=major.id, class_id=school_class.id,
            current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
        db.add(student); db.flush()
        db.add(StudentContact(tenant_id=tenant_id, student_id=student.id, contact_type="PHONE",
                              contact_value_encrypted=f"1390000000{index}", is_primary=True,
                              verified_status="VERIFIED"))
    db.add(StudentProfile(tenant_id=other_tenant, student_no="2026OTHER", real_name="外校学生",
                          current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"))
    db.commit(); db.close()

    first = client.get("/api/v1/students?college=信息工程&page=1&pageSize=1",
                       headers=auth_headers).json()["data"]
    second = client.get("/api/v1/students?college=信息工程&page=2&pageSize=1",
                        headers=auth_headers).json()["data"]
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert first["items"][0]["collegeName"] == "信息工程学院"
    assert first["items"][0]["majorName"] == "软件技术"
    assert first["items"][0]["className"] == "软件一班"
    assert first["items"][0]["phoneMasked"].startswith("139****")
    by_class = client.get("/api/v1/students?className=软件一班&pageSize=20",
                          headers=auth_headers).json()["data"]
    assert by_class["total"] == 2
    assert all(item["studentNo"] != "2026OTHER" for item in by_class["items"])


def test_student_create_void_db(client, auth_headers, db_mode):
    created = client.post("/api/v1/students", headers=auth_headers,
                          json={"studentNo": "2099115999", "realName": "库中新生",
                                "phone": "13800001111"}).json()["data"]
    assert created["phoneMasked"] == "138****1111"
    void = client.post(f"/api/v1/students/{created['id']}/void", headers=auth_headers,
                       json={"reason": "重复建档需要作废"}).json()["data"]
    assert void["physicalDelete"] is False
    items = client.get("/api/v1/students", headers=auth_headers).json()["data"]["items"]
    assert all(r["id"] != created["id"] for r in items)  # 逻辑删除后列表不可见


def test_approval_flow_db(client, auth_headers, db_mode):
    tasks = client.get("/api/v1/approvals/tasks", headers=auth_headers).json()["data"]["items"]
    assert len(tasks) == 1 and tasks[0]["status"] == "PENDING"
    tid = tasks[0]["taskId"]
    no_reason = client.post(f"/api/v1/approvals/tasks/{tid}/reject", headers=auth_headers, json={})
    assert no_reason.json()["code"] in (400001, 422001)
    ok = client.post(f"/api/v1/approvals/tasks/{tid}/approve", headers=auth_headers,
                     json={"comment": "同意"}).json()["data"]
    assert ok["status"] == "APPROVED"
    processed = client.get("/api/v1/approvals/processed", headers=auth_headers).json()["data"]["items"]
    assert any(p["taskId"] == tid for p in processed)


def test_todos_messages_db(client, auth_headers, db_mode):
    todos = client.get("/api/v1/todos", headers=auth_headers).json()["data"]
    assert todos["total"] == 1
    todo_id = todos["items"][0]["todoId"]
    assert client.post(f"/api/v1/todos/{todo_id}/done", headers=auth_headers).json()["data"]["status"] == "DONE"
    msgs = client.get("/api/v1/messages", headers=auth_headers).json()["data"]
    assert msgs["total"] == 1
    mid = msgs["items"][0]["messageId"]
    assert client.post(f"/api/v1/messages/{mid}/read", headers=auth_headers).json()["data"]["status"] == "READ"


def test_audit_persisted_db(client, auth_headers, db_mode):
    client.post("/api/v1/audit/mock-record", headers=auth_headers)
    body = client.get("/api/v1/audit/logs", headers=auth_headers).json()["data"]
    assert body["total"] >= 1  # 从 t_security_audit_log 读出
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog
    from sqlalchemy import select
    db = get_sessionmaker()()
    rows = db.scalars(select(SecurityAuditLog)).all()
    db.close()
    assert len(rows) >= 1


def test_p4_upload_real(client, auth_headers, db_mode, tmp_path):
    import io as _io
    resp = client.post("/api/v1/files", headers=auth_headers,
                       files={"file": ("测试.txt", _io.BytesIO("你好".encode()), "text/plain")}).json()
    assert resp["code"] == 0
    meta = resp["data"]
    assert meta["fileId"].isdigit() and meta["sha256"] and meta["sizeBytes"] > 0
    got = client.get(f"/api/v1/files/meta/{meta['fileId']}", headers=auth_headers).json()["data"]
    assert got["fileName"] == "测试.txt"
    bad = client.post("/api/v1/files", headers=auth_headers,
                      files={"file": ("evil.exe", _io.BytesIO(b"x"), "application/octet-stream")}).json()
    assert bad["code"] != 0  # 黑名单扩展被拒


# 原 test_p4_import_dry_run_and_confirm 已随 /import/students/* 删除：
# 学生批量导入现由「系统管理 › 学生导入与账号开通」承担，覆盖见
# tests/test_student_import_entries.py；本文件继续覆盖导出与其它 DB 模式行为。


def test_p4_export_and_download(client, auth_headers, db_mode):
    t = client.post("/api/v1/export/students", headers=auth_headers,
                    json={"purpose": "学院例会名单核对"}).json()["data"]
    assert t["status"] == "SUCCESS" and t["taskId"].isdigit()
    resp = client.get(f"/api/v1/export/tasks/{t['taskId']}/download", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # xlsx = zip 容器
    short = client.post("/api/v1/export/students", headers=auth_headers, json={"purpose": "短"}).json()
    assert short["code"] in (400001, 422001)  # 用途 <5 字被拦


def test_p4_export_uses_all_database_pages(client, auth_headers, db_mode, monkeypatch):
    """小分页模拟大导出：不得只写第一页，也不得为后续页重复执行总数统计。"""
    from io import BytesIO

    from openpyxl import load_workbook

    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from app.services import import_export_service as ie

    db = get_sessionmaker()()
    for index in (2, 3):
        db.add(StudentProfile(tenant_id=1000000000000000001,
                              student_no=f"2026EXPORT{index}", real_name=f"导出分页{index}",
                              current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"))
    db.commit(); db.close()
    monkeypatch.setattr(ie, "EXPORT_PAGE_SIZE", 1)

    task = client.post("/api/v1/export/students", headers=auth_headers,
                       json={"purpose": "验证分页导出完整性"}).json()["data"]
    assert task["rowCount"] == 3
    response = client.get(f"/api/v1/export/tasks/{task['taskId']}/download", headers=auth_headers)
    workbook = load_workbook(BytesIO(response.content), read_only=True)
    rows = list(workbook.active.iter_rows(values_only=True))
    assert len(rows) == 5  # 水印 + 表头 + 3 名学生
    assert {row[0] for row in rows[2:]} == {"2023115001", "2026EXPORT2", "2026EXPORT3"}


def test_p4_audit_filters(client, auth_headers, db_mode):
    client.post("/api/v1/audit/mock-record", headers=auth_headers)
    body = client.get("/api/v1/audit/logs?action=MOCK", headers=auth_headers).json()["data"]
    assert body["total"] >= 1
    assert all(i["action"] == "MOCK" for i in body["items"])
    empty = client.get("/api/v1/audit/logs?operator=不存在的人", headers=auth_headers).json()["data"]
    assert empty["total"] == 0
