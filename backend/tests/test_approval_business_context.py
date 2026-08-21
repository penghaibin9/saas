"""审批业务 Context adapter（V3 施工手册 TP-A06）。

`approval_business_context_service.resolve_context()` 把 `WorkflowInstance`
解析成审批端可读的业务事实，替换 `get_task()` 里原来恒定的空 `attachments`/
`diff`。覆盖：

- 四个真实 adapter（LEAVE / AA_STATUS_CHANGE / AID / DISCIPLINE）在业务记录
  齐全时返回 FULL，附件来自 `AffairsAttachment`；
- 业务记录被软删/不存在时返回 MISSING，不冒充"没有内容"；
- 未接入的 `source_biz_type` 返回 UNSUPPORTED 并给出可读原因，不是静默空白；
- 单域读取异常返回 ERROR，不拖垮 `get_task()` 整个响应；
- AID 的 `statement`（强敏感）字段一律脱敏占位，绝不带原文出 adapter；
- `get_task()` 真实接口把 `businessContext` 挂到响应体，`attachments` 与之
  同源。

全部用真实 MySQL 跑（db_mode），不是字符串契约测试。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001


def _hdr(client, login_name="counselor01"):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _mk_instance(db, *, biz_type: str, biz_id: int, applicant_id: int = 1):
    from app.models import WorkflowInstance
    inst = WorkflowInstance(
        tenant_id=TID, workflow_code="TEST_WF", source_module="student-affairs",
        source_biz_type=biz_type, source_biz_id=biz_id, applicant_id=applicant_id,
        title="测试审批", status="RUNNING", current_node="NODE_1",
    )
    db.add(inst)
    db.flush()
    return inst


def _set_tenant():
    from app.core.context import set_tenant
    set_tenant({"tenantId": str(TID)})


def test_leave_adapter_returns_full_with_real_fields(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CsLeave
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        leave = CsLeave(
            tenant_id=TID, leave_type="PERSONAL", reason="家中有事",
            start_time=datetime(2026, 8, 1), end_time=datetime(2026, 8, 3),
            days=2, status="PENDING_REVIEW", affairs_status="IN_REVIEW",
        )
        db.add(leave)
        db.flush()
        inst = _mk_instance(db, biz_type="LEAVE", biz_id=leave.id)
        db.flush()

        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.FULL
        assert ctx["sourceBizType"] == "LEAVE"
        assert ctx["sourceBizId"] == str(leave.id)
        assert ctx["sourceVersion"] == int(leave.version or 0)
        labels = {f["label"]: f["value"] for f in ctx["sections"][0]["fields"]}
        assert labels["请假类型"] == "PERSONAL"
        assert labels["事由"] == "家中有事"
        assert ctx["note"] == ""
    finally:
        db.rollback()
        db.close()


def test_status_change_adapter_full(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaStatusChange
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        chg = AaStatusChange(
            tenant_id=TID, student_id=1, change_type="TRANSFER_MAJOR",
            from_status="NORMAL", to_status="NORMAL", status="SUBMITTED",
        )
        db.add(chg)
        db.flush()
        inst = _mk_instance(db, biz_type="AA_STATUS_CHANGE", biz_id=chg.id)
        db.flush()

        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.FULL
        labels = {f["label"]: f["value"] for f in ctx["sections"][0]["fields"]}
        assert labels["异动类型"] == "TRANSFER_MAJOR"
        assert labels["目标学籍状态"] == "NORMAL"
    finally:
        db.rollback()
        db.close()


def test_discipline_adapter_full_and_attachments(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAttachment, DisciplineCase
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        case = DisciplineCase(
            tenant_id=TID, student_id=1, disc_type="WARNING",
            reason="考试违纪", doc_no="XJ-2026-001", status="REGISTERED",
        )
        db.add(case)
        db.flush()
        db.add(AffairsAttachment(
            tenant_id=TID, biz_type="DISCIPLINE", biz_id=case.id, file_id=9001,
            file_name="处分决定书.pdf", sensitivity_level="SENSITIVE",
            source_channel="LEGACY_ADAPTER",
        ))
        inst = _mk_instance(db, biz_type="DISCIPLINE", biz_id=case.id)
        db.flush()

        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.FULL
        labels = {f["label"]: f["value"] for f in ctx["sections"][0]["fields"]}
        assert labels["处分类型"] == "WARNING"
        assert labels["违纪事实"] == "考试违纪"
        assert len(ctx["attachments"]) == 1
        assert ctx["attachments"][0]["fileName"] == "处分决定书.pdf"
    finally:
        db.rollback()
        db.close()


def test_aid_adapter_masks_sensitive_statement(db_mode):
    """AID 的 statement 是强敏感字段，adapter 绝不能把原文带出来。"""
    from app.db.session import get_sessionmaker
    from app.models import AidApply
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        apply_row = AidApply(
            tenant_id=TID, batch_id=1, student_id=1, apply_level="DIFFICULT",
            statement="这是一段包含家庭隐私信息的困难情况说明原文",
            status="SUBMITTED",
        )
        db.add(apply_row)
        db.flush()
        inst = _mk_instance(db, biz_type="AID", biz_id=apply_row.id)
        db.flush()

        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.FULL
        fields = ctx["sections"][0]["fields"]
        statement_field = next(f for f in fields if f["label"] == "困难情况说明")
        assert statement_field["masked"] is True
        assert statement_field["value"] == svc._MASKED_PLACEHOLDER
        assert "家庭隐私" not in str(ctx)
    finally:
        db.rollback()
        db.close()


def test_aid_adapter_partial_when_apply_level_missing(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        apply_row = AidApply(tenant_id=TID, batch_id=1, student_id=1, status="DRAFT")
        db.add(apply_row)
        db.flush()
        inst = _mk_instance(db, biz_type="AID", biz_id=apply_row.id)
        db.flush()

        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.PARTIAL
    finally:
        db.rollback()
        db.close()


def test_missing_when_business_row_soft_deleted(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CsLeave
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        leave = CsLeave(tenant_id=TID, leave_type="PERSONAL", status="PENDING_REVIEW",
                        is_deleted=True)
        db.add(leave)
        db.flush()
        inst = _mk_instance(db, biz_type="LEAVE", biz_id=leave.id)
        db.flush()

        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.MISSING
        assert ctx["sections"] == []
        assert "不存在或已删除" in ctx["summary"]
    finally:
        db.rollback()
        db.close()


def test_missing_when_business_row_does_not_exist(db_mode):
    from app.db.session import get_sessionmaker
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        inst = _mk_instance(db, biz_type="LEAVE", biz_id=999999999)
        db.flush()

        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.MISSING
    finally:
        db.rollback()
        db.close()


def test_unsupported_biz_type_is_explicit_not_silent(db_mode):
    """手册点名的 COMPANY_CHANGE / EMPLOYMENT_DESTINATION 全仓没有真实
    WorkflowInstance 使用这两个值，本轮未登记 adapter；必须显式 UNSUPPORTED +
    可读原因，不能返回一个看起来"这条申请没内容"的空 Context。"""
    from app.db.session import get_sessionmaker
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        inst = _mk_instance(db, biz_type="COMPANY_CHANGE", biz_id=1)
        db.flush()

        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.UNSUPPORTED
        assert "COMPANY_CHANGE" in ctx["note"]
        assert "尚未接入" in ctx["note"]
        assert ctx["sections"] == []
        assert ctx["attachments"] == []
    finally:
        db.rollback()
        db.close()


def test_error_isolated_from_unsupported_and_missing(db_mode, monkeypatch):
    """单域读取真的抛异常时标 ERROR，与 MISSING/UNSUPPORTED 严格分开，且不
    向上抛出——resolve_context() 必须吞下业务域异常，不能拖垮 get_task()。"""
    from app.db.session import get_sessionmaker
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        inst = _mk_instance(db, biz_type="LEAVE", biz_id=1)
        db.flush()

        def _boom(_db, _instance):
            raise RuntimeError("模拟业务域读取故障")

        monkeypatch.setitem(svc._ADAPTERS, "LEAVE", _boom)
        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.ERROR
        assert "RuntimeError" in ctx["note"]
    finally:
        db.rollback()
        db.close()


def test_supported_biz_types_only_lists_real_adapters():
    from app.services import approval_business_context_service as svc
    assert svc.supported_biz_types() == [
        "AA_STATUS_CHANGE", "AID", "DISCIPLINE", "EMPLOYMENT_DESTINATION", "LEAVE"]


def test_get_task_wires_business_context_into_response(db_mode, client):
    """端到端：审批任务详情接口真实返回 businessContext，attachments 与
    businessContext.attachments 同源（TP-A06 在 get_task() 里的实际接线）。"""
    from app.db.session import get_sessionmaker
    from app.models import AffairsAttachment, CsLeave, User, WorkflowInstance, WorkflowTask

    db = get_sessionmaker()()
    try:
        # "counselor01" 是 mock-login 内置演示账号（mock_auth_service.DEMO_USERS）；
        # 真实 assignee 校验走 resolve_message_user_id() 的登录名回查（token 的
        # userId 是字符串 "u_counselor01"，回查本租户同名 User 行取真实数字 id），
        # 所以这里必须真建一行同名 User，而不是任意起名——任意起名会命中
        # mock-login 的 userType 兜底分支，登进另一个演示身份，assignee 对不上。
        user = db.query(User).filter_by(tenant_id=TID, login_name="counselor01").first()
        if user is None:
            user = User(tenant_id=TID, login_name="counselor01", real_name="审批员",
                       password_hash="test-hash", user_type="TEACHER", status="ACTIVE")
            db.add(user)
            db.flush()
        else:
            user.status = "ACTIVE"
            user.is_deleted = False
        db.flush()

        leave = CsLeave(tenant_id=TID, leave_type="SICK", reason="生病请假",
                        start_time=datetime(2026, 8, 5), end_time=datetime(2026, 8, 6),
                        days=1, status="PENDING_REVIEW", affairs_status="IN_REVIEW")
        db.add(leave)
        db.flush()
        db.add(AffairsAttachment(tenant_id=TID, biz_type="LEAVE", biz_id=leave.id,
                                 file_id=9002, file_name="病历.jpg"))
        inst = WorkflowInstance(tenant_id=TID, workflow_code="LEAVE_WF",
                                source_module="student-affairs", source_biz_type="LEAVE",
                                source_biz_id=leave.id, applicant_id=1, status="RUNNING",
                                current_node="NODE_1")
        db.add(inst)
        db.flush()
        task = WorkflowTask(tenant_id=TID, instance_id=inst.id, node_code="NODE_1",
                            assignee_id=user.id, status="PENDING")
        db.add(task)
        db.flush()
        task_id = task.id
        db.commit()
    finally:
        db.close()

    headers = _hdr(client, "counselor01")
    resp = client.get(f"/api/v1/approvals/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["businessContext"]["completeness"] == "FULL"
    assert body["businessContext"]["sourceBizType"] == "LEAVE"
    assert body["attachments"] == body["businessContext"]["attachments"]
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["fileName"] == "病历.jpg"
