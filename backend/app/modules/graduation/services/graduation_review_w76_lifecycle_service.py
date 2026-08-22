"""W7.6 Todo / message / statistics lifecycle adapter for graduation review.

The formal-review status authority remains ``GraduationReview`` and the W7.1/W7.2
closure service. This adapter only synchronizes the derivative UnifiedTodo lifecycle
and reuses the W7.3 Review Center metrics projection. Repeating an operation repairs
an omitted todo because ``todo_upsert`` is idempotent on the shared unique key.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.models import GraduationMentor, GraduationReview, GraduationStudent, User
from app.modules.graduation.services import graduation_review_center_contract_service as review_center
from app.modules.graduation.services import graduation_review_closure_service as core
from app.modules.graduation.services import graduation_todo_helper as todo
from app.services.db_service import _tid, session

TODO_FORMAL_REVIEW = "GD_FORMAL_REVIEW"


def _review_and_student(db, review_id: int):
    review = db.scalars(select(GraduationReview).where(
        GraduationReview.tenant_id == _tid(),
        GraduationReview.id == int(review_id),
        GraduationReview.is_deleted.is_(False),
    ).with_for_update()).first()
    if not review:
        raise not_found("评阅任务不存在")
    student = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.id == int(review.gd_student_id),
        GraduationStudent.is_deleted.is_(False),
    )).first()
    if not student:
        raise not_found("毕设学生不存在")
    return review, student


def _reviewer_user_id(db, review: GraduationReview) -> int:
    mentor_id = getattr(review, "reviewer_mentor_id", None)
    if not mentor_id:
        return 0
    mentor = db.scalars(select(GraduationMentor).where(
        GraduationMentor.tenant_id == _tid(),
        GraduationMentor.id == int(mentor_id),
        GraduationMentor.is_deleted.is_(False),
    )).first()
    if not mentor:
        return 0
    teacher_no = str(mentor.teacher_no or "").strip()
    if not teacher_no:
        return 0
    user = db.scalars(select(User).where(
        User.tenant_id == _tid(),
        User.login_name == teacher_no,
        User.is_deleted.is_(False),
        User.status == "ACTIVE",
    )).first()
    return int(user.id) if user else 0


def _sync_formal_todo(review_id: int) -> bool:
    with session() as db:
        review, student = _review_and_student(db, int(review_id))
        assignee_id = _reviewer_user_id(db, review)
        prefix = "正式评阅退回重评" if str(review.status or "").upper() == "RETURNED" else "正式评阅待处理"
        written = todo.todo_upsert(
            db,
            biz_type="GD_FORMAL_REVIEW",
            biz_id=review.id,
            todo_type=TODO_FORMAL_REVIEW,
            assignee_id=assignee_id,
            student_id=getattr(student, "student_id", None),
            title=f"{prefix}：{student.name or '学生'}",
        )
        db.commit()
        return written


def _complete_formal_todo(review_id: int) -> int:
    with session() as db:
        count = todo.todo_done(db, biz_id=int(review_id), todo_type=TODO_FORMAL_REVIEW)
        db.commit()
        return count


def assign_review(gd_student_id, reviewer_name: str | None = None, gd_final_id=None,
                  reviewer_mentor_id=None) -> dict:
    result = core.assign_review(
        gd_student_id, reviewer_name, gd_final_id, reviewer_mentor_id=reviewer_mentor_id,
    )
    _sync_formal_todo(int(result["id"]))
    return result


def submit_review(rid, score: int, opinion: str, *, expected_version: int | None,
                  file_version_id: int | None, categories=None, issues=None,
                  idempotency_key: str | None = None) -> dict:
    result = core.submit_review(
        rid, score, opinion, expected_version=expected_version,
        file_version_id=file_version_id, categories=categories, issues=issues,
        idempotency_key=idempotency_key,
    )
    _complete_formal_todo(int(result["id"]))
    return result


def return_review(rid, reason: str) -> dict:
    result = core.return_review(rid, reason)
    _sync_formal_todo(int(result["id"]))
    return result


def review_stats(batch_id=None) -> dict:
    base = core.review_stats(batch_id=batch_id)
    if batch_id is None:
        return base
    metrics = review_center.summary(int(batch_id))
    return {
        **base,
        "overdue": int(metrics.get("overdue") or 0),
        "avgHours": metrics.get("avgHours"),
    }


__all__ = [
    "TODO_FORMAL_REVIEW", "assign_review", "submit_review", "return_review", "review_stats",
]
