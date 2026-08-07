"""6 域通用导入：Dry-Run 校验（必填/批内重复/库内重复）+ 确认写入 + 未过校验禁确认。"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException

MAIN_TID = 1000000000000000001


def _seed_profiles(nos):
    """阶段 D 起旧域导入只能给已有学籍的学生建业务台账，测试需先备好主档。"""
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    try:
        for i, no in enumerate(nos):
            db.add(StudentProfile(tenant_id=1000000000000000001, student_no=no,
                                  real_name=f"导入主档{i}", current_stage="ENROLLED",
                                  student_status="NORMAL", status="ACTIVE"))
        db.commit()
    finally:
        db.close()


def test_academic_import_dry_run_and_confirm(client, auth_headers, db_mode):
    _seed_profiles(["IMP2026001", "IMP2026002", "IMP2026010", "IMP2026011"])
    rows = [{"name": "导入生A", "studentNo": "IMP2026001", "className": "软件2301班"},
            {"name": "导入生B", "studentNo": "IMP2026002"},
            {"name": "", "studentNo": "IMP2026003"},          # 姓名缺失
            {"name": "重复", "studentNo": "IMP2026001"}]        # 批内重复
    dr = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                     json={"rows": rows}).json()
    assert dr["code"] == 0 and dr["data"]["status"] == "DRY_RUN_FAILED"
    assert dr["data"]["okRows"] == 2 and dr["data"]["errorRows"] == 2

    # 全部合法 → 通过 → 确认
    good = [{"name": "导入生C", "studentNo": "IMP2026010"}, {"name": "导入生D", "studentNo": "IMP2026011"}]
    dr2 = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                      json={"rows": good}).json()
    assert dr2["data"]["status"] == "DRY_RUN_PASSED" and dr2["data"]["okRows"] == 2
    cf = client.post("/api/v1/import/domain/confirm", headers=auth_headers,
                     json={"batchNo": dr2["data"]["batchNo"]}).json()
    assert cf["code"] == 0 and cf["data"]["insertedRows"] == 2
    # 已导入的学号再导入 → 库内重复
    dr3 = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                      json={"rows": [{"name": "x", "studentNo": "IMP2026010"}]}).json()
    assert dr3["data"]["errorRows"] == 1


def test_import_failed_batch_cannot_confirm(client, auth_headers, db_mode):
    dr = client.post("/api/v1/import/domain/employment/validate", headers=auth_headers,
                     json={"rows": [{"name": "", "studentNo": ""}]}).json()
    assert dr["data"]["status"] == "DRY_RUN_FAILED"
    cf = client.post("/api/v1/import/domain/confirm", headers=auth_headers,
                     json={"batchNo": dr["data"]["batchNo"]}).json()
    assert cf["code"] == 422001


def test_import_unknown_domain(client, auth_headers, db_mode):
    bad = client.post("/api/v1/import/domain/nosuch/validate", headers=auth_headers,
                      json={"rows": []}).json()
    assert bad["code"] == 422001


def test_import_requires_login(client):
    assert client.post("/api/v1/import/domain/academic/validate", json={"rows": []}).json()["code"] == 401001


def test_import_rejects_unbounded_batches():
    """行数上限守卫。必须带租户上下文，否则先撞更外层的租户守卫，测不到本用例的目标
    （租户守卫排在行数检查之前是正确的安全顺序，不应为了这个测试调换）。"""
    from app.core.context import set_tenant
    from app.services import domain_import_service as service

    set_tenant({"tenantId": str(MAIN_TID)})
    try:
        with pytest.raises(AppException) as exc:
            service.dry_run("academic", [{}] * (service.MAX_IMPORT_ROWS + 1))
        assert exc.value.code == "VALIDATION_ERROR"
    finally:
        set_tenant(None)


def test_dry_run_batch_survives_process_local_state_wipe(client, auth_headers, db_mode):
    """包12/C29 止血：批次落 MySQL 共享表，不再是进程内 dict——即便清空任何进程级缓存，
    只要行还在数据库里，confirm 仍能查到（等价于 worker A dry-run、worker B 用同一份
    持久化数据 confirm；服务重启同理不丢）。"""
    _seed_profiles(["IMP2026030"])
    dr = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                     json={"rows": [{"name": "导入生X", "studentNo": "IMP2026030"}]}).json()
    batch_no = dr["data"]["batchNo"]

    from app.db.session import get_sessionmaker
    from app.models import SharedImportBatch
    db = get_sessionmaker()()
    try:
        row = db.query(SharedImportBatch).filter(
            SharedImportBatch.tenant_id == MAIN_TID,
            SharedImportBatch.namespace == "DOMAIN_IMPORT",
            SharedImportBatch.batch_no == batch_no).first()
        assert row is not None, "Dry-Run 批次必须落库，不能只留在进程内存"
        assert row.status == "DRY_RUN_PASSED"
        assert row.payload_json.get("domain") == "academic"
    finally:
        db.close()

    cf = client.post("/api/v1/import/domain/confirm", headers=auth_headers,
                     json={"batchNo": batch_no}).json()
    assert cf["code"] == 0 and cf["data"]["insertedRows"] == 1


def test_confirm_rolls_back_whole_batch_on_row_failure(client, auth_headers, db_mode):
    """第 N 行确认时失败（哪怕前面的行已经在同一事务里 flush 过），整批必须 rollback，
    不能留下半成品台账。"""
    _seed_profiles(["IMP2026040", "IMP2026041"])
    rows = [{"name": "导入生E", "studentNo": "IMP2026040"},
            {"name": "导入生F", "studentNo": "IMP2026041"}]
    dr = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                     json={"rows": rows}).json()
    assert dr["data"]["status"] == "DRY_RUN_PASSED"
    batch_no = dr["data"]["batchNo"]

    # 模拟 Dry-Run 快照之后、确认写入之前，另一条链路已经把第二行的台账建好了
    # （真实世界里的并发建档竞态）——确认时第二行必然撞 DATA_CONFLICT。
    from app.core.context import set_tenant
    from app.services import academic_service
    set_tenant({"tenantId": MAIN_TID})
    try:
        academic_service.create_student({"studentNo": "IMP2026041"})
    finally:
        set_tenant(None)

    cf = client.post("/api/v1/import/domain/confirm", headers=auth_headers,
                     json={"batchNo": batch_no})
    assert cf.status_code >= 400 or cf.json()["code"] != 0

    from app.db.session import get_sessionmaker
    from app.models import AcademicStudent, StudentProfile
    db = get_sessionmaker()()
    try:
        first = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN_TID, StudentProfile.student_no == "IMP2026040").first()
        leaked = db.query(AcademicStudent).filter(
            AcademicStudent.tenant_id == MAIN_TID, AcademicStudent.student_id == first.id).first()
        assert leaked is None, "第二行失败必须回滚第一行已 flush 但未提交的写入，不能留半成品台账"
    finally:
        db.close()


def test_confirm_is_idempotent_on_repeat_call(client, auth_headers, db_mode):
    """重复点确认（同一个已 SUCCESS 的批次）不得重复写入。"""
    _seed_profiles(["IMP2026050"])
    dr = client.post("/api/v1/import/domain/academic/validate", headers=auth_headers,
                     json={"rows": [{"name": "导入生G", "studentNo": "IMP2026050"}]}).json()
    batch_no = dr["data"]["batchNo"]
    cf1 = client.post("/api/v1/import/domain/confirm", headers=auth_headers,
                      json={"batchNo": batch_no}).json()
    assert cf1["code"] == 0 and cf1["data"]["insertedRows"] == 1
    cf2 = client.post("/api/v1/import/domain/confirm", headers=auth_headers,
                      json={"batchNo": batch_no}).json()
    assert cf2["code"] == 0
    assert cf2["data"] == cf1["data"], "重复确认必须原样返回首次结果，不能二次写入"

    from app.db.session import get_sessionmaker
    from app.models import AcademicStudent, StudentProfile
    db = get_sessionmaker()()
    try:
        prof = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == MAIN_TID, StudentProfile.student_no == "IMP2026050").first()
        cnt = db.query(AcademicStudent).filter(
            AcademicStudent.tenant_id == MAIN_TID, AcademicStudent.student_id == prof.id).count()
        assert cnt == 1, "重复确认不能在库里留下第二条台账"
    finally:
        db.close()
