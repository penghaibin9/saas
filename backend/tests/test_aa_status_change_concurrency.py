"""包 5：学籍异动并发、故障回滚与冲突无副作用（真实 MySQL）。

覆盖三条不变量：
1. 两个受理人同时终审同一异动，只有一个成功；失败方不得让主档 version 前进两次；
2. 终审事务中任一步失败（这里注入 outbox 写入异常），主档、异动单、工作流任务、
   待办、审计和消息全部回滚，不留半截事实；
3. 冲突请求不产生事件与消息：被拒绝的那一次审批不得留下 StudentStageEvent /
   UnifiedMessage / MessageEventOutbox 记录。

并发用例通过服务层真实入口（安装了包 5 安全层的 change_service.review）发起，
不是直接 INSERT 撞唯一键——要证明的是"审批命令"的互斥，不只是数据库兜底。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import academic_affairs_change_service as change_service
from tests.support_status_change_identity import (
    COUNSELOR_PERM,
    OFFICE_PERM,
    TID,
    seed_status_change_identity,
)

_COLLEGE_NAME = "并发学院"


def _ctx(login_name, role_code):
    return {
        "userId": f"u_{login_name}", "loginName": login_name, "realName": login_name,
        "currentRoleCode": role_code, "userType": "ADMIN", "tenantId": str(TID),
    }


def _activate(user):
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    set_current_user(user)


def _seed_change_at_final(*, change_type="SUSPEND"):
    """种一条已推进到教务处终审节点的异动单，返回 (changeId, studentId, 学生初始 version)。"""
    from app.models import (
        AaStatusChange, College, SchoolClass, StudentProfile, WorkflowInstance, WorkflowTask,
    )

    db = get_sessionmaker()()
    try:
        college = College(tenant_id=TID, college_name=_COLLEGE_NAME, status="ACTIVE")
        db.add(college)
        db.flush()
        klass = SchoolClass(tenant_id=TID, major_id=1, class_name="并发2101", grade="2021",
                            status="ACTIVE")
        db.add(klass)
        db.flush()
        student = StudentProfile(tenant_id=TID, student_no="AAC01", real_name="并发甲",
                                 class_id=klass.id, college_id=college.id, major_id=1,
                                 current_stage="ON_CAMPUS", student_status="REGISTERED",
                                 status="ACTIVE")
        db.add(student)
        db.flush()
        users = seed_status_change_identity(db, class_ids=(klass.id,), college_ids=(college.id,))

        change = AaStatusChange(
            tenant_id=TID, student_id=student.id, change_type=change_type,
            from_status="REGISTERED", to_status="SUSPENDED", reason="并发终审用例",
            from_college_id=college.id, from_major_id=1, from_class_id=klass.id,
            status="IN_REVIEW", current_node="AA_OFFICE_FINAL", term_code="2026-2027-1",
            expected_student_version=int(student.version or 0),
            idempotency_key="concurrency-final-1",
        )
        db.add(change)
        db.flush()
        instance = WorkflowInstance(
            tenant_id=TID, workflow_code="ACAD_STATUS_SUSPEND", source_module="academic-affairs",
            source_biz_type="AA_STATUS_CHANGE", source_biz_id=change.id, applicant_id=0,
            title="并发终审", status="RUNNING", current_node="AA_OFFICE_FINAL",
        )
        db.add(instance)
        db.flush()
        task = WorkflowTask(tenant_id=TID, instance_id=instance.id, node_code="AA_OFFICE_FINAL",
                            assignee_id=users["school_admin01"], status="PENDING")
        db.add(task)
        db.flush()
        change.workflow_instance_id = instance.id
        change.current_task_id = task.id
        db.commit()
        return int(change.id), int(student.id), int(student.version or 0)
    finally:
        db.close()


def _side_effect_counts(change_id, student_id):
    from app.models import MessageEventOutbox, StudentStageEvent, UnifiedMessage
    from app.models import AffairsAuditTrail

    db = get_sessionmaker()()
    try:
        return {
            "stageEvents": db.query(StudentStageEvent).filter(
                StudentStageEvent.tenant_id == TID,
                StudentStageEvent.student_id == student_id).count(),
            "messages": db.query(UnifiedMessage).filter(
                UnifiedMessage.tenant_id == TID).count(),
            "outbox": db.query(MessageEventOutbox).filter(
                MessageEventOutbox.tenant_id == TID,
                MessageEventOutbox.source_biz_id == change_id).count(),
            "audits": db.query(AffairsAuditTrail).filter(
                AffairsAuditTrail.tenant_id == TID,
                AffairsAuditTrail.biz_type == "AA_STATUS_CHANGE",
                AffairsAuditTrail.biz_id == change_id).count(),
        }
    finally:
        db.close()


def _student_state(student_id):
    from app.models import StudentProfile

    db = get_sessionmaker()()
    try:
        row = db.get(StudentProfile, student_id)
        return row.student_status, int(row.version or 0)
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_two_concurrent_final_reviews_only_one_wins():
    change_id, student_id, base_version = _seed_change_at_final()
    barrier = Barrier(2)

    def approve(_index):
        _activate(_ctx("school_admin01", "SCHOOL_ADMIN"))
        barrier.wait()
        try:
            change_service.review(change_id, _ctx("school_admin01", "SCHOOL_ADMIN"), "APPROVE")
            return "ok"
        except AppException as exc:
            return f"rejected:{exc.code}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, range(2)))

    assert results.count("ok") == 1, results
    # 落败方必须是"冲突"，而不是碰巧被状态机的非法转移挡下：证明互斥来自认领与行锁本身。
    assert results.count("rejected:APPROVAL_VERSION_CONFLICT") == 1, results

    status, version = _student_state(student_id)
    assert status == "SUSPENDED"
    # 关键：主档只被推进一次，落败方没有第二次 +1。
    assert version == base_version + 1

    counts = _side_effect_counts(change_id, student_id)
    assert counts["stageEvents"] == 1, counts
    assert counts["outbox"] == 1, counts


@pytest.mark.usefixtures("db_mode")
def test_failed_final_review_rolls_back_every_formal_fact(monkeypatch):
    change_id, student_id, base_version = _seed_change_at_final()
    before = _side_effect_counts(change_id, student_id)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("injected outbox failure")

    # 注入点在正式事实之后、commit 之前：只要事务边界正确，主档改动必须一起回滚。
    monkeypatch.setattr(change_service, "_msg", _boom)

    _activate(_ctx("school_admin01", "SCHOOL_ADMIN"))
    with pytest.raises(RuntimeError):
        change_service.review(change_id, _ctx("school_admin01", "SCHOOL_ADMIN"), "APPROVE")

    status, version = _student_state(student_id)
    assert status == "REGISTERED"
    assert version == base_version
    assert _side_effect_counts(change_id, student_id) == before

    from app.models import AaStatusChange, WorkflowTask

    db = get_sessionmaker()()
    try:
        change = db.get(AaStatusChange, change_id)
        assert change.status == "IN_REVIEW"
        assert int(change.decision_version or 0) == 0
        task = db.query(WorkflowTask).filter(
            WorkflowTask.tenant_id == TID,
            WorkflowTask.instance_id == change.workflow_instance_id,
        ).first()
        # 任务必须仍然待办：失败的审批不得把它吞掉。
        assert task.status == "PENDING"
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_stale_decision_version_is_rejected_without_side_effects():
    change_id, student_id, _base_version = _seed_change_at_final()
    _activate(_ctx("school_admin01", "SCHOOL_ADMIN"))
    before = _side_effect_counts(change_id, student_id)

    with pytest.raises(AppException) as exc:
        change_service.review(change_id, _ctx("school_admin01", "SCHOOL_ADMIN"), "APPROVE",
                              expected_decision_version=7)
    assert exc.value.code == "APPROVAL_VERSION_CONFLICT"

    assert _side_effect_counts(change_id, student_id) == before
    assert _student_state(student_id)[0] == "REGISTERED"


@pytest.mark.usefixtures("db_mode")
def test_stale_expected_student_version_blocks_final_approval():
    """申请在途期间主档被其他入口改写 → 终审 409，不允许拿过期事实覆盖当前学籍。"""
    from app.models import AaStatusChange, StudentProfile

    change_id, student_id, _base_version = _seed_change_at_final()
    db = get_sessionmaker()()
    try:
        change = db.get(AaStatusChange, change_id)
        change.expected_student_version = int(change.expected_student_version or 0) - 1
        db.commit()
    finally:
        db.close()

    _activate(_ctx("school_admin01", "SCHOOL_ADMIN"))
    with pytest.raises(AppException) as exc:
        change_service.review(change_id, _ctx("school_admin01", "SCHOOL_ADMIN"), "APPROVE")
    assert exc.value.code == "APPROVAL_VERSION_CONFLICT"

    db = get_sessionmaker()()
    try:
        assert db.get(StudentProfile, student_id).student_status == "REGISTERED"
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_permission_codes_are_declared_for_status_change_nodes():
    """受理人解析依赖的权限编码必须与审批节点合同一致，避免改名后静默解析不到人。"""
    assert change_service._NODE_PERM["COUNSELOR_REVIEW"] == COUNSELOR_PERM
    assert change_service._NODE_PERM["AA_OFFICE_FINAL"] == OFFICE_PERM
