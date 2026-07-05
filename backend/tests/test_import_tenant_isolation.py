"""P10 安全回归：内存导入批次绑定租户，禁止跨租户凭 batchNo 确认写入他人数据。
覆盖 import_export_service（学生主档导入）与 domain_import_service（6 域通用导入）。
直接调用 service 层并切换租户上下文（不经 HTTP 中间件），精确验证租户守卫。
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
    from app.services import import_export_service as ie
    try:
        _use_tenant(TA)
        dr = ie.dry_run([{"studentNo": "TISO0001", "realName": "隔离生甲"}])
        assert dr["status"] == "DRY_RUN_PASSED"
        batch_no = dr["batchNo"]

        # 切到租户 B 确认 → 按「不存在」拒绝（不泄露存在性），不得写入
        _use_tenant(TB)
        with pytest.raises(AppException) as ei:
            ie.confirm(batch_no)
        assert ei.value.code == "DATA_NOT_FOUND"

        # 切回租户 A 确认 → 正常成功
        _use_tenant(TA)
        ok = ie.confirm(batch_no)
        assert ok["status"] == "SUCCESS" and ok["insertedRows"] == 1
    finally:
        set_tenant(None)


def test_domain_import_cross_tenant_confirm_denied(db_mode):
    from app.services import domain_import_service as di
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
