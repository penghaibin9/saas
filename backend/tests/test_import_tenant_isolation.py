"""P10 安全回归：导入批次绑定租户，禁止跨租户凭 batchNo 确认写入他人数据。
覆盖 identity_import_file_service（学生/教师主档导入的现行正式入口）与
domain_import_service（6 域通用导入）。直接调用 service 层并切换租户上下文
（不经 HTTP 中间件），精确验证租户守卫。

注：旧 `import_export_service.dry_run/confirm`（/import/students/*）已于
`0ed5c03e` 随「学生导入入口收敛」整体删除，该提交声明的 5 个测试文件迁移漏了本
文件，导致本用例长期指向已不存在的函数。现按同一安全意图重指向现行入口。
"""
from __future__ import annotations

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException

TA = 1000000000000000001   # db_mode 种子所属主租户
TB = 1000000000000000009   # 另一个租户（无权确认 TA 的批次）


def _use_tenant(tid) -> None:
    set_tenant({"tenantId": str(tid)})


def test_student_import_cross_tenant_confirm_denied(db_mode):
    """学生/教师主档导入批次：同一个 batchNo，换租户拿不到、也确认不了。"""
    from app.services import identity_import_file_service as ii

    user = {"userId": "tiso-operator"}
    parsed = {"fileName": "隔离测试.xlsx", "fileSha256": "a" * 64, "totalRows": 1,
              "students": [{"studentNo": "TISO0001", "realName": "隔离生甲"}],
              "teachers": [], "rawRows": [], "errors": [], "relationships": [],
              "relationErrors": []}
    report = {"tenantId": TA, "errors": [], "entities": {}}
    try:
        _use_tenant(TA)
        created = ii.create_batch(user, parsed, report)
        batch_no = created["batchNo"]

        # 同一个操作人、同一个 batchNo，只是换租户上下文 → 按「不存在」拒绝，
        # 不泄露存在性，更不允许 claim 到确认租约。
        _use_tenant(TB)
        with pytest.raises(AppException) as ei:
            ii.get_batch(user, TB, batch_no)
        assert ei.value.code == "DATA_NOT_FOUND"
        with pytest.raises(AppException) as ei2:
            ii.claim_batch(user, TB, batch_no)
        assert ei2.value.code == "DATA_NOT_FOUND"

        # 切回租户 A → 本租户自己的批次仍可正常读取
        _use_tenant(TA)
        assert ii.get_batch(user, TA, batch_no)["batchNo"] == batch_no
    finally:
        set_tenant(None)


def test_domain_import_cross_tenant_confirm_denied(db_mode):
    from app.services import domain_import_service as di
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile

    # 阶段 D 起 academic 域导入只能给已有学籍的学生建台账，故先在租户 A 备好主档，
    # 否则 Dry-Run 直接判错行，测不到本用例真正要测的跨租户确认守卫。
    db = get_sessionmaker()()
    try:
        db.add(StudentProfile(tenant_id=TA, student_no="TISO0002", real_name="隔离生乙",
                              current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"))
        db.commit()
    finally:
        db.close()

    try:
        _use_tenant(TA)
        dr = di.dry_run("academic", [{"name": "隔离生乙", "studentNo": "TISO0002"}])
        assert dr["status"] == "DRY_RUN_PASSED"
        batch_no = dr["batchNo"]

        _use_tenant(TB)
        with pytest.raises(AppException) as ei:
            di.confirm(batch_no)
        assert ei.value.code == "DATA_NOT_FOUND"

        _use_tenant(TA)
        ok = di.confirm(batch_no)
        assert ok["status"] == "SUCCESS" and ok["insertedRows"] == 1
    finally:
        set_tenant(None)
