"""Real MySQL lifecycle evidence for VolunteerGroup <-> EnterpriseDecision lock effects."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.internship_enterprise_application_decision import InternshipEnterpriseApplicationDecision
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_volunteer_group_service as group_svc

TID = 1000000000000000001


def _unique_base() -> int:
    return 8_000_000_000 + (uuid4().int % 500_000_000)


def _session():
    return get_sessionmaker()()


def _seed_locked(*, expired: bool):
    base = _unique_base()
    db = _session()
    try:
        assert db.bind.dialect.name == "mysql"
        now = datetime.utcnow()
        group = InternshipVolunteerGroup(
            tenant_id=TID,
            record_id=base + 1,
            student_id=base + 2,
            batch_id=base + 3,
            campaign_id=base + 4,
            status="LOCKED",
            submission_version=1,
            locked_application_id=base + 5,
            locked_at=now - timedelta(hours=1),
            teacher_confirm_deadline=(now - timedelta(seconds=1) if expired else now + timedelta(hours=24)),
            version=0,
        )
        db.add(group)
        db.flush()
        decision = InternshipEnterpriseApplicationDecision(
            tenant_id=TID,
            application_id=base + 5,
            volunteer_group_id=group.id,
            campaign_id=base + 4,
            batch_id=base + 3,
            company_id=base + 6,
            position_id=base + 7,
            material_snapshot_id=base + 8,
            submission_version=1,
            decision_status="ACCEPT_INTENT",
            effect_status="ACTIVE",
            valid_until=now + timedelta(days=2),
            version=0,
        )
        db.add(decision)
        db.flush()
        group.locked_by_decision_id = decision.id
        ids = group.id, decision.id
        db.commit()
        return ids
    finally:
        db.close()


def test_mysql_timeout_release_expires_active_accept_intent_same_transaction(db_mode):
    set_tenant({"tenantId": str(TID)})
    group_id, decision_id = _seed_locked(expired=True)
    db = _session()
    try:
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.id == group_id,
            InternshipVolunteerGroup.tenant_id == TID,
        ).with_for_update())
        assert group_svc.lazy_release_expired_lock_in_tx(
            db, group=group, tenant_id=TID, now=datetime.utcnow(), user={"userId": "db-1"},
        ) is True
        decision = db.get(InternshipEnterpriseApplicationDecision, decision_id)
        assert group.status == "NEEDS_REVISION"
        assert group.release_reason == "TEACHER_CONFIRM_TIMEOUT"
        assert group.released_at is not None
        assert group.teacher_confirm_deadline is None
        assert group.locked_application_id is not None
        assert group.locked_by_decision_id == decision_id
        assert decision.effect_status == "EXPIRED"
        assert decision.superseded_reason == "TEACHER_CONFIRM_TIMEOUT"
        db.commit()
    finally:
        db.close()
        set_tenant(None)


def test_mysql_teacher_release_supersedes_active_accept_intent_same_transaction(db_mode):
    set_tenant({"tenantId": str(TID)})
    group_id, decision_id = _seed_locked(expired=False)
    db = _session()
    try:
        group = db.scalar(select(InternshipVolunteerGroup).where(
            InternshipVolunteerGroup.id == group_id,
            InternshipVolunteerGroup.tenant_id == TID,
        ).with_for_update())
        group_svc.teacher_request_revision_in_tx(
            db,
            group=group,
            reason="学生申请调整志愿，学校审核同意",
            user={"userId": "db-991", "realName": "审核老师", "currentRoleCode": "INTERNSHIP_MANAGER"},
            release_reason_code="TEACHER_UNLOCK_RELEASE",
        )
        decision = db.get(InternshipEnterpriseApplicationDecision, decision_id)
        assert group.status == "NEEDS_REVISION"
        assert group.release_reason == "TEACHER_UNLOCK_RELEASE"
        assert group.released_by_user_id == 991
        assert decision.effect_status == "SUPERSEDED"
        assert decision.superseded_reason == "TEACHER_UNLOCK_RELEASE"
        db.commit()
    finally:
        db.close()
        set_tenant(None)


def test_mysql_two_enterprises_competing_accept_intent_only_one_lock_wins(db_mode):
    base = _unique_base()
    db = _session()
    try:
        assert db.bind.dialect.name == "mysql"
        group = InternshipVolunteerGroup(
            tenant_id=TID,
            record_id=base + 1,
            student_id=base + 2,
            batch_id=base + 3,
            campaign_id=base + 4,
            status="SUBMITTED",
            submission_version=1,
            version=0,
        )
        db.add(group)
        db.flush()
        group_id = group.id
        db.commit()
    finally:
        db.close()

    barrier = threading.Barrier(2)
    output: list[tuple] = []
    output_lock = threading.Lock()

    def _worker(index: int):
        set_tenant({"tenantId": str(TID)})
        local = _session()
        try:
            barrier.wait(timeout=30)
            row = local.scalar(select(InternshipVolunteerGroup).where(
                InternshipVolunteerGroup.id == group_id,
                InternshipVolunteerGroup.tenant_id == TID,
            ).with_for_update())
            group_svc.lock_for_accept_intent_in_tx(
                local,
                group=row,
                application_id=base + 100 + index,
                decision_id=base + 200 + index,
                teacher_confirm_sla_hours=48,
                user={"userId": f"db-{800 + index}", "realName": f"企业{index}"},
            )
            local.commit()
            with output_lock:
                output.append(("ok", row.locked_application_id, row.locked_by_decision_id))
        except AppException as exc:
            local.rollback()
            with output_lock:
                output.append(("err", exc.code, exc.http_status))
        finally:
            local.close()
            set_tenant(None)

    threads = [threading.Thread(target=_worker, args=(1,)), threading.Thread(target=_worker, args=(2,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    oks = [item for item in output if item[0] == "ok"]
    errs = [item for item in output if item[0] == "err"]
    assert len(oks) == 1, output
    assert len(errs) == 1, output
    assert errs[0][1] == "VOLUNTEER_GROUP_LOCKED", output
    assert errs[0][2] == 409, output
