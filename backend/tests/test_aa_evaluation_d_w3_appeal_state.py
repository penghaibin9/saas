"""D-W3 MySQL contracts for the two-stage evaluation appeal state machine."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest
from sqlalchemy import func, select

from app.core.exceptions import AppException

TID = 1000000000000000001


def _teacher(login: str = "appeal_teacher") -> dict:
    return {
        "userId": f"u-{login}",
        "loginName": login,
        "realName": "申诉验收教师",
        "userType": "TEACHER",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "tenantId": str(TID),
    }


def _college_admin(login: str) -> dict:
    return {
        "userId": f"u-{login}",
        "loginName": login,
        "realName": "学院初审管理员",
        "userType": "ADMIN",
        "currentRoleCode": "COLLEGE_ADMIN",
        "tenantId": str(TID),
    }


def _academic_admin() -> dict:
    return {
        "userId": "u-appeal-academic-admin",
        "loginName": "appeal_academic_admin",
        "realName": "教务终审管理员",
        "userType": "ADMIN",
        "currentRoleCode": "ACADEMIC_ADMIN",
        "tenantId": str(TID),
    }


def _bind(user: dict) -> None:
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID), "tenantCode": "dw3-appeal-contract"})
    set_current_user(user)


def _unbind() -> None:
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def _seed_result(label: str, *, published: bool = True) -> dict:
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse,
        AaEvaluationBatch,
        AaEvaluationResult,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        College,
        TeacherStudentScope,
    )

    college_a_login = f"appeal_college_a_{label.lower()}"
    college_b_login = f"appeal_college_b_{label.lower()}"
    _bind(_academic_admin())
    db = get_sessionmaker()()
    try:
        college_a = College(
            tenant_id=TID,
            college_name=f"D-W3申诉学院A-{label}",
            code=f"DWA{label}",
            status="ACTIVE",
        )
        college_b = College(
            tenant_id=TID,
            college_name=f"D-W3申诉学院B-{label}",
            code=f"DWB{label}",
            status="ACTIVE",
        )
        db.add_all([college_a, college_b])
        db.flush()
        db.add_all([
            TeacherStudentScope(
                tenant_id=TID,
                teacher_key=college_a_login,
                role_code="COLLEGE_ADMIN",
                scope_type="COLLEGE",
                ref_value=college_a.college_name,
                status="ACTIVE",
            ),
            TeacherStudentScope(
                tenant_id=TID,
                teacher_key=college_b_login,
                role_code="COLLEGE_ADMIN",
                scope_type="COLLEGE",
                ref_value=college_b.college_name,
                status="ACTIVE",
            ),
        ])

        term = AaTerm(
            tenant_id=TID,
            year_code=f"2042-{label}",
            term_no=1,
            term_name=f"D-W3申诉验收学期-{label}",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        course = AaCourse(
            tenant_id=TID,
            course_code=f"DW3-APL-{label}",
            course_name=f"D-W3申诉验收课程-{label}",
            credit=2,
            status="ENABLED",
        )
        db.add(course)
        db.flush()
        teaching_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            college_id=college_a.id,
            batch_name=f"D-W3申诉教学任务批次-{label}",
            status="APPROVED",
        )
        db.add(teaching_batch)
        db.flush()
        teaching_task = AaTeachingTask(
            tenant_id=TID,
            batch_id=teaching_batch.id,
            course_id=course.id,
            course_code=course.course_code,
            course_name=course.course_name,
            teacher_key="appeal_teacher",
            teacher_name="申诉验收教师",
            status="READY",
        )
        db.add(teaching_task)
        db.flush()
        evaluation_batch = AaEvaluationBatch(
            tenant_id=TID,
            batch_name=f"D-W3申诉评教批次-{label}",
            term_id=term.id,
            anonymous=True,
            result_published_at=datetime.utcnow() if published else None,
            status="RESULT_READY",
        )
        db.add(evaluation_batch)
        db.flush()
        result = AaEvaluationResult(
            tenant_id=TID,
            batch_id=evaluation_batch.id,
            teaching_task_id=teaching_task.id,
            teacher_key="appeal_teacher",
            teacher_name="申诉验收教师",
            course_name=course.course_name,
            student_avg=88,
            student_count=20,
            composite_score=88,
            level="GOOD",
            published=published,
        )
        db.add(result)
        db.commit()
        return {
            "batchId": int(evaluation_batch.id),
            "resultId": int(result.id),
            "collegeA": college_a_login,
            "collegeB": college_b_login,
        }
    finally:
        db.close()
        _unbind()


def _call(user: dict, fn, *args, **kwargs):
    _bind(user)
    try:
        return fn(user, *args, **kwargs)
    finally:
        _unbind()


@pytest.mark.usefixtures("db_mode")
def test_appeal_requires_published_result_and_teacher_owner():
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as service

    unpublished = _seed_result("U1", published=False)
    with pytest.raises(AppException) as exc_info:
        _call(_teacher(), service.submit_appeal, unpublished["resultId"], "结果尚未发布不应允许发起申诉")
    assert exc_info.value.code == "DATA_CONFLICT"
    assert "尚未正式发布" in exc_info.value.message

    published = _seed_result("U2", published=True)
    with pytest.raises(AppException) as exc_info:
        _call(_teacher("other_teacher"), service.submit_appeal, published["resultId"], "非本人评价结果不得越权发起申诉")
    assert exc_info.value.code == "NO_PERMISSION"


@pytest.mark.usefixtures("db_mode")
def test_appeal_two_stage_scope_archive_guard_and_no_reappeal():
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as service

    ids = _seed_result("F1", published=True)
    appeal = _call(_teacher(), service.submit_appeal, ids["resultId"], "评价结果存在明显异常申请人工复核")
    assert appeal["status"] == "SUBMITTED"
    assert appeal["currentNode"] == "COLLEGE"
    appeal_id = int(appeal["appealId"])

    with pytest.raises(AppException) as exc_info:
        _call(
            _college_admin(ids["collegeB"]),
            service.review_appeal,
            appeal_id,
            "RESOLVE",
            "非本学院尝试初审必须拒绝",
        )
    assert exc_info.value.code == "NO_DATA_SCOPE"

    with pytest.raises(AppException) as exc_info:
        _call(
            _academic_admin(),
            service.review_appeal,
            appeal_id,
            "RESOLVE",
            "学校级管理员不得跳过学院初审",
        )
    assert exc_info.value.code == "NO_DATA_SCOPE"

    college_review = _call(
        _college_admin(ids["collegeA"]),
        service.review_appeal,
        appeal_id,
        "RESOLVE",
        "学院初审通过转交教务处终审",
    )
    assert college_review["status"] == "COLLEGE_REVIEW"
    assert college_review["currentNode"] == "ACADEMIC"

    with pytest.raises(AppException) as exc_info:
        _call(_academic_admin(), service.archive_batch, ids["batchId"])
    assert exc_info.value.code == "DATA_CONFLICT"
    assert "未完成评价申诉" in exc_info.value.message

    with pytest.raises(AppException) as exc_info:
        _call(
            _college_admin(ids["collegeA"]),
            service.review_appeal,
            appeal_id,
            "RESOLVE",
            "学院管理员不得越权完成教务终审",
        )
    assert exc_info.value.code == "NO_DATA_SCOPE"

    final = _call(
        _academic_admin(),
        service.review_appeal,
        appeal_id,
        "RESOLVE",
        "教务终审通过保留原分并记录人工复核",
    )
    assert final["status"] == "RESOLVED"
    assert final["currentNode"] is None

    with pytest.raises(AppException) as exc_info:
        _call(_teacher(), service.submit_appeal, ids["resultId"], "同一结果终审后默认不得再次发起申诉")
    assert exc_info.value.code == "DATA_CONFLICT"
    assert "不允许重复申诉" in exc_info.value.message

    archived = _call(_academic_admin(), service.archive_batch, ids["batchId"])
    assert archived["status"] == "ARCHIVED"


@pytest.mark.usefixtures("db_mode")
def test_same_result_concurrent_appeal_has_exactly_one_winner():
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationAppeal
    from app.modules.academic_affairs.services import academic_affairs_evaluation_service as service

    ids = _seed_result("R1", published=True)
    barrier = Barrier(2)

    def worker(index: int):
        _bind(_teacher())
        try:
            barrier.wait(timeout=10)
            try:
                value = service.submit_appeal(
                    _teacher(),
                    ids["resultId"],
                    f"并发申诉验收理由第{index}路必须只有一条成功",
                )
                return ("ok", value["appealId"])
            except AppException as exc:
                return ("error", exc.code)
        finally:
            _unbind()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(worker, (1, 2)))
    assert sorted(kind for kind, _value in outcomes) == ["error", "ok"]
    assert [value for kind, value in outcomes if kind == "error"] == ["DATA_CONFLICT"]

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        count = int(db.scalar(select(func.count()).select_from(AaEvaluationAppeal).where(
            AaEvaluationAppeal.tenant_id == TID,
            AaEvaluationAppeal.result_id == ids["resultId"],
            AaEvaluationAppeal.is_deleted.is_(False),
        )) or 0)
        assert count == 1
    finally:
        db.close()
        set_tenant(None)
