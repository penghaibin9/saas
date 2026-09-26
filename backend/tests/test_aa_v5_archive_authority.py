"""归档正式写入口必须由当前学校责任人办理，审计别名不能充当授权。"""
from contextlib import nullcontext
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AppException, no_permission
from app.modules.academic_affairs.services import academic_affairs_archive_core_service as core
from app.modules.academic_affairs.services import academic_affairs_archive_manifest_service as manifest
from app.modules.academic_affairs.services import academic_affairs_archive_correction_review_service as review


@pytest.mark.parametrize("condition", ["valid", "college", "revoked", "expired", "other_actor", "disabled"])
def test_archive_operator_requires_live_school_scope_permission_and_identity(monkeypatch, condition):
    from app.modules.academic_affairs.services import academic_affairs_grade_correction_command as identity
    from app.modules.academic_affairs.services import academic_affairs_responsibility_service as responsibility

    monkeypatch.setattr(core, "_ctx", lambda *_: SimpleNamespace(
        scope_type="COLLEGE" if condition == "college" else "TENANT_ALL",
        permission_codes=set() if condition == "revoked" else {"academicAffairs.archive.manage"}))
    monkeypatch.setattr(responsibility, "resolve_school", lambda *_args, **_kwargs: {
        "resolved": condition != "expired", "assigneeUserIds": ["32" if condition == "other_actor" else "31"]})
    actor = MagicMock(return_value=31)
    if condition == "disabled":
        actor.side_effect = no_permission("账号已停用")
    monkeypatch.setattr(identity, "_current_user_id", actor)
    if condition == "valid":
        assert core._require_archive_operator(object(), {"userId": "db-31"}) == 31
    else:
        with pytest.raises(AppException) as denied:
            core._require_archive_operator(object(), {"userId": "db-31"})
        assert denied.value.http_status == 403


def _commands(user, batch_id=1, case_id=2):
    return [
        lambda: manifest.confirm_archive(user, batch_id),
        lambda: core.confirm_archive(user, batch_id),
        lambda: manifest.create_correction_case(user, batch_id, business_type="GRADE", target_ref="1",
            reason="原始试卷复核更正", correction={"score": 65}, evidence_manifest={"hash": "a" * 64}),
        lambda: manifest.approve_correction_case(user, case_id),
        lambda: review.reject_correction_case(user, case_id, reason="原始试卷材料仍不完整"),
        lambda: manifest.append_integrity_checkpoint(user, batch_id, note="核对历史清单完整性"),
    ]


def test_all_archive_write_consumers_fail_before_facts_or_audit(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(core, "session", lambda: nullcontext(db))
    guard = MagicMock(side_effect=no_permission("当前归档任职已到期"))
    monkeypatch.setattr(core, "_require_archive_operator", guard)
    audit = MagicMock()
    monkeypatch.setattr(core, "_audit", audit)
    for command in _commands({"userId": "db-31"}):
        with pytest.raises(AppException) as denied:
            command()
        assert denied.value.http_status == 403
    assert guard.call_count == 6
    db.query.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
    audit.assert_not_called()


def test_mysql_archive_expiry_and_permission_revocation_preserve_all_facts(db_mode):
    from sqlalchemy import func, select
    from app.core.context import get_current_user_ctx, get_tenant, set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaArchiveBatch, AffairsAuditTrail, ArchiveManifest, AcademicGrade, Permission, RolePermission, StaffAssignment, PostArchiveCorrectionCase
    from app.modules.academic_affairs.services import academic_affairs_archive_service as public
    from tests.support_archive_review_identity import seed_archive_operator
    from tests.test_stage_c3_correction_end_to_end import TID, _seed_grade_archive

    previous_tenant, previous_user = get_tenant(), get_current_user_ctx()
    set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            creator = seed_archive_operator(db, TID, "v5_archive_creator")
            operator = seed_archive_operator(db, TID, "v5_archive_reviewer")
            ready = AaArchiveBatch(tenant_id=TID, batch_name="未完成真实门禁的待确认批次",
                term_code="2041-2042-1", status="READY")
            db.add(ready); db.flush()
            ready_id = ready.id
            db.commit()
        set_current_user(creator)
        batch_id, grade_id, _manifest_id = _seed_grade_archive()
        case = public.create_correction_case(creator, batch_id, business_type="GRADE", target_ref=str(grade_id),
            reason="原始试卷复核更正", correction={"score": 65}, evidence_manifest={"hash": "a" * 64})
        set_current_user(operator)

        def snapshot():
            with get_sessionmaker()() as db:
                counts = tuple(db.scalar(select(func.count()).select_from(model).where(model.tenant_id == TID))
                    for model in (ArchiveManifest, AcademicGrade, AffairsAuditTrail))
                return counts, db.get(AaArchiveBatch, ready_id).status, public.get_correction_case(operator, case["caseId"])["status"]

        before = snapshot()
        assert public.get_batch(operator, ready_id)["confirmAction"]["allowed"] is True
        for invalidation in ("expired", "revoked"):
            with get_sessionmaker()() as db:
                appointment = db.scalar(select(StaffAssignment).where(StaffAssignment.tenant_id == TID,
                    StaffAssignment.user_id == int(operator["userId"])))
                grant = db.scalar(select(RolePermission).join(Permission, Permission.id == RolePermission.permission_id).where(
                    RolePermission.tenant_id == TID, Permission.permission_code == "academicAffairs.archive.manage"))
                appointment.expires_at = datetime.utcnow() - timedelta(days=1) if invalidation == "expired" else None
                grant.status = "DISABLED" if invalidation == "revoked" else "ACTIVE"
                db.commit()
            assert public.get_batch(operator, ready_id)["confirmAction"]["allowed"] is False
            for command in _commands(operator, ready_id, int(case["caseId"])):
                with pytest.raises(AppException) as denied:
                    command()
                assert denied.value.http_status == 403
            assert snapshot() == before
        with get_sessionmaker()() as db:
            grant = db.scalar(select(RolePermission).join(Permission, Permission.id == RolePermission.permission_id).where(
                RolePermission.tenant_id == TID, Permission.permission_code == "academicAffairs.archive.manage"))
            grant.status = "ACTIVE"
            db.commit()
        assert public.get_batch(operator, ready_id)["confirmAction"]["allowed"] is True
        # 合法责任人仍须经过真实语义门禁，历史 READY 不能直接封存。
        with pytest.raises(AppException) as blocked:
            public.confirm_archive(operator, ready_id)
        assert blocked.value.http_status == 409
        assert snapshot() == before
        # 仅在独立测试库模拟旧兼容签署；不得把“两个编号不同”当成双人证明。
        legacy_actor = 2 ** 60
        with get_sessionmaker()() as db:
            db.get(PostArchiveCorrectionCase, int(case["caseId"])).created_by = legacy_actor
            db.commit()
        for command in (
            lambda: public.approve_correction_case(operator, case["caseId"]),
            lambda: review.reject_correction_case(operator, case["caseId"], reason="历史签署身份待核验"),
            lambda: manifest.append_integrity_checkpoint(operator, batch_id, note="旧签署账号核验"),
        ):
            with pytest.raises(AppException) as historical:
                command()
            assert historical.value.http_status == 409 and "历史签署账号" in historical.value.message
        assert snapshot() == before
        with get_sessionmaker()() as db:
            row = db.get(PostArchiveCorrectionCase, int(case["caseId"]))
            assert row.created_by == legacy_actor
            row.created_by = int(creator["userId"])
            db.commit()
        applied = public.approve_correction_case(operator, case["caseId"])
        assert applied["status"] == "APPLIED" and applied["manifestVersion"] == 2
    finally:
        set_current_user(previous_user)
        set_tenant(previous_tenant)
