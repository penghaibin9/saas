"""审批业务 Context adapter（TP-A06/A07，真实 MySQL）。

核心合同：真实生产 workflow 必须有 Context/sourceVersion；业务记录缺失、读取异常、敏感字段
脱敏和附件投影都不能退化成“空白但可审批”。生产类型覆盖率与审批业务字典直接比对，只有
明确的 sandbox-only 类型允许带理由豁免。
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
        db.add(leave); db.flush()
        inst = _mk_instance(db, biz_type="LEAVE", biz_id=leave.id)
        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.FULL
        assert ctx["sourceVersion"] == int(leave.version or 0)
        labels = {f["label"]: f["value"] for f in ctx["sections"][0]["fields"]}
        assert labels["请假类型"] == "PERSONAL"
        assert labels["事由"] == "家中有事"
    finally:
        db.rollback(); db.close()


def test_status_change_adapter_full(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaStatusChange
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        row = AaStatusChange(
            tenant_id=TID, student_id=1, change_type="TRANSFER_MAJOR",
            from_status="NORMAL", to_status="NORMAL", status="SUBMITTED",
        )
        db.add(row); db.flush()
        ctx = svc.resolve_context(db, _mk_instance(db, biz_type="AA_STATUS_CHANGE", biz_id=row.id))
        assert ctx["completeness"] == svc.FULL
        labels = {f["label"]: f["value"] for f in ctx["sections"][0]["fields"]}
        assert labels["异动类型"] == "TRANSFER_MAJOR"
        assert labels["目标学籍状态"] == "NORMAL"
    finally:
        db.rollback(); db.close()


def test_discipline_adapter_full_and_attachments(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAttachment, DisciplineCase
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        row = DisciplineCase(
            tenant_id=TID, student_id=1, disc_type="WARNING",
            reason="考试违纪", doc_no="XJ-2026-001", status="REGISTERED",
        )
        db.add(row); db.flush()
        db.add(AffairsAttachment(
            tenant_id=TID, biz_type="DISCIPLINE", biz_id=row.id, file_id=9001,
            file_name="处分决定书.pdf", sensitivity_level="SENSITIVE",
            source_channel="LEGACY_ADAPTER",
        ))
        ctx = svc.resolve_context(db, _mk_instance(db, biz_type="DISCIPLINE", biz_id=row.id))
        assert ctx["completeness"] == svc.FULL
        assert ctx["attachments"][0]["fileName"] == "处分决定书.pdf"
    finally:
        db.rollback(); db.close()


def test_aid_adapter_masks_sensitive_statement(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        row = AidApply(
            tenant_id=TID, batch_id=1, student_id=1, apply_level="DIFFICULT",
            statement="这是一段包含家庭隐私信息的困难情况说明原文", status="SUBMITTED",
        )
        db.add(row); db.flush()
        ctx = svc.resolve_context(db, _mk_instance(db, biz_type="AID", biz_id=row.id))
        assert ctx["completeness"] == svc.FULL
        field = next(f for f in ctx["sections"][0]["fields"] if f["label"] == "困难情况说明")
        assert field["masked"] is True
        assert field["value"] == svc._MASKED_PLACEHOLDER
        assert "家庭隐私" not in str(ctx)
    finally:
        db.rollback(); db.close()


def test_aid_adapter_partial_when_apply_level_missing(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        row = AidApply(tenant_id=TID, batch_id=1, student_id=1, status="DRAFT")
        db.add(row); db.flush()
        ctx = svc.resolve_context(db, _mk_instance(db, biz_type="AID", biz_id=row.id))
        assert ctx["completeness"] == svc.PARTIAL
    finally:
        db.rollback(); db.close()


def test_missing_when_business_row_soft_deleted(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CsLeave
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        row = CsLeave(tenant_id=TID, leave_type="PERSONAL", status="PENDING_REVIEW", is_deleted=True)
        db.add(row); db.flush()
        ctx = svc.resolve_context(db, _mk_instance(db, biz_type="LEAVE", biz_id=row.id))
        assert ctx["completeness"] == svc.MISSING
        assert ctx["sections"] == []
    finally:
        db.rollback(); db.close()


def test_missing_when_business_row_does_not_exist(db_mode):
    from app.db.session import get_sessionmaker
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        ctx = svc.resolve_context(db, _mk_instance(db, biz_type="LEAVE", biz_id=999999999))
        assert ctx["completeness"] == svc.MISSING
    finally:
        db.rollback(); db.close()


def test_unknown_biz_type_is_explicit_not_silent(db_mode):
    from app.db.session import get_sessionmaker
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        ctx = svc.resolve_context(db, _mk_instance(db, biz_type="COMPANY_CHANGE", biz_id=1))
        assert ctx["completeness"] == svc.UNSUPPORTED
        assert "COMPANY_CHANGE" in ctx["note"] and "尚未接入" in ctx["note"]
        assert ctx["sections"] == [] and ctx["attachments"] == []
    finally:
        db.rollback(); db.close()


def test_error_isolated_from_unsupported_and_missing(db_mode, monkeypatch):
    """adapter 的动作锁参数也是正式合同；故障注入 mock 必须接受该关键字。"""
    from app.db.session import get_sessionmaker
    from app.services import approval_business_context_service as svc

    db = get_sessionmaker()()
    try:
        _set_tenant()
        inst = _mk_instance(db, biz_type="LEAVE", biz_id=1)

        def _boom(_db, _instance, **_kwargs):
            raise RuntimeError("模拟业务域读取故障")

        monkeypatch.setitem(svc._ADAPTERS, "LEAVE", _boom)
        ctx = svc.resolve_context(db, inst)
        assert ctx["completeness"] == svc.ERROR
        assert "RuntimeError" in ctx["note"]
    finally:
        db.rollback(); db.close()


def test_production_approval_types_have_context_or_explicit_nonprod_exemption():
    """新增生产审批类型时忘接 Context，CI 必须直接失败，不能运行时默默 UNSUPPORTED。"""
    from app.services import approval_business_context_service as svc
    from app.services import approval_runtime_service as runtime

    runtime_types = set(runtime._BIZ_TYPE_LABELS)
    supported = set(svc.supported_biz_types())
    exemptions = svc.non_production_exemptions()
    assert runtime_types == supported | set(exemptions), {
        "missingContext": sorted(runtime_types - supported - set(exemptions)),
        "staleAdapters": sorted(supported - runtime_types),
        "staleExemptions": sorted(set(exemptions) - runtime_types),
    }
    assert exemptions == {
        "PROFILE_CORRECTION": "仅体验沙箱/演示学校种子创建，不存在生产业务 command"
    }
    assert "PROFILE_CORRECTION" not in supported


def test_supported_biz_types_lists_all_real_adapters():
    from app.services import approval_business_context_service as svc
    assert svc.supported_biz_types() == sorted([
        "AA_GRADE_CHANGE", "AA_GRADE_TASK", "AA_SCHEDULE_CHANGE", "AA_STATUS_CHANGE",
        "AID", "DISCIPLINE", "DISCIPLINE_REMOVE", "EMPLOYMENT_DESTINATION", "FUNDING",
        "LEAVE", "MESSAGE_CAMPAIGN",
    ])


def test_get_task_wires_business_context_into_response(db_mode, client):
    from app.db.session import get_sessionmaker
    from app.models import AffairsAttachment, CsLeave, User, WorkflowInstance, WorkflowTask

    db = get_sessionmaker()()
    try:
        user = db.query(User).filter_by(tenant_id=TID, login_name="counselor01").first()
        if user is None:
            user = User(tenant_id=TID, login_name="counselor01", real_name="审批员",
                        password_hash="test-hash", user_type="TEACHER", status="ACTIVE")
            db.add(user); db.flush()
        else:
            user.status = "ACTIVE"; user.is_deleted = False
        row = CsLeave(
            tenant_id=TID, leave_type="SICK", reason="生病请假",
            start_time=datetime(2026, 8, 5), end_time=datetime(2026, 8, 6),
            days=1, status="PENDING_REVIEW", affairs_status="IN_REVIEW",
        )
        db.add(row); db.flush()
        db.add(AffairsAttachment(tenant_id=TID, biz_type="LEAVE", biz_id=row.id,
                                 file_id=9002, file_name="病历.jpg"))
        inst = WorkflowInstance(
            tenant_id=TID, workflow_code="LEAVE_WF", source_module="student-affairs",
            source_biz_type="LEAVE", source_biz_id=row.id, applicant_id=1,
            status="RUNNING", current_node="NODE_1",
        )
        db.add(inst); db.flush()
        task = WorkflowTask(tenant_id=TID, instance_id=inst.id, node_code="NODE_1",
                            assignee_id=user.id, status="PENDING")
        db.add(task); db.flush(); task_id = task.id; db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/v1/approvals/tasks/{task_id}", headers=_hdr(client))
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["businessContext"]["completeness"] == "FULL"
    assert body["businessContext"]["sourceBizType"] == "LEAVE"
    assert body["attachments"] == body["businessContext"]["attachments"]
