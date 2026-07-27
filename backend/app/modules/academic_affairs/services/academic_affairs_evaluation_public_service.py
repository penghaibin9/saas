"""教学评价最终公开 Service。

学生评教入口同时满足三条红线：
1. 仅当前账号稳定绑定的学生本人可提交；
2. 学生必须属于该教学任务当前正式教学班名单；
3. 同一学生对同一任务只能提交一次，同时不在评价记录和审计中保存明文身份。

去重凭证使用静态数据密钥生成不可逆 HMAC，写入答卷保留字段；教师、学院和普通导出无法
据此反查学生。凭证不依赖 JWT 签名密钥，轮换登录令牌密钥不会使历史去重失效。
非学生评价继续使用既有 evaluator_key 本人校验与单任务幂等规则。
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import AppException, no_permission, not_found

from . import academic_affairs_evaluation_term_facade as _base

_legacy = _base._legacy
_RESERVED_TOKEN_KEY = "_systemAnonymousSubmissionToken"

# 保留显式注入点，便于定向测试；正式实现只读取本模块引用。
session = _legacy.session
_tid = _legacy._tid


def __getattr__(name):
    return getattr(_base, name)


def _is_student_user(user) -> bool:
    user = user or {}
    user_type = str(user.get("userType") or "").strip().upper()
    role = str(user.get("currentRoleCode") or "").strip().upper()
    return user_type == "STUDENT" or role == "STUDENT"


def _anonymous_token_key() -> bytes:
    """匿名去重凭证必须独立于短周期登录 JWT；静态字段密钥在数据存续期内保持稳定。"""
    key = str(settings.FIELD_ENCRYPTION_KEY or "").strip()
    if not key:
        raise AppException(
            "CONFIG_ERROR",
            "匿名评教凭证密钥未配置",
            http_status=500,
        )
    return key.encode("utf-8")


def _submission_token(task_id: int, student_id: int) -> str:
    material = f"{_tid()}:{int(task_id)}:{int(student_id)}".encode("utf-8")
    return hmac.new(
        _anonymous_token_key(),
        material,
        hashlib.sha256,
    ).hexdigest()


def _token_pattern(task_id: int, student_id: int) -> str:
    token = _submission_token(task_id, student_id)
    return f'%"{_RESERVED_TOKEN_KEY}":"{token}"%'


def _encode_student_answers(answers, token: str) -> str:
    payload = dict(answers or {})
    payload[_RESERVED_TOKEN_KEY] = token
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _require_anonymous_student_batch(batch, *, has_student_tasks: bool = True) -> None:
    """学生任务只能进入匿名批次；在生成、发布、开放和提交四个阶段重复校验。"""
    if has_student_tasks and not bool(getattr(batch, "anonymous", False)):
        raise AppException(
            "DATA_CONFLICT",
            "学生评教批次必须启用匿名模式，请修正批次配置后再继续",
            http_status=409,
        )


def _batch_has_student_tasks(db, batch_id: int) -> bool:
    from app.models import AaEvaluationTask

    return db.query(AaEvaluationTask.id).filter(
        AaEvaluationTask.tenant_id == _tid(),
        AaEvaluationTask.batch_id == int(batch_id),
        AaEvaluationTask.evaluator_type == "STUDENT",
        AaEvaluationTask.is_deleted.is_(False),
    ).first() is not None


def generate_tasks(user, bid, teaching_task_ids, evaluator_type="STUDENT"):
    evaluator_type = str(evaluator_type or "STUDENT").upper()
    if evaluator_type == "STUDENT":
        with session() as db:
            _legacy._require_school(_legacy._ctx(user, db))
            batch = _base._writable_batch(db, bid)
            _require_anonymous_student_batch(batch)
    return _base.generate_tasks(user, bid, teaching_task_ids, evaluator_type)


def publish_batch(user, bid):
    with session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _base._writable_batch(db, bid)
        _require_anonymous_student_batch(
            batch,
            has_student_tasks=_batch_has_student_tasks(db, batch.id),
        )
    return _base.publish_batch(user, bid)


def open_batch(user, bid):
    with session() as db:
        _legacy._require_school(_legacy._ctx(user, db))
        batch = _base._writable_batch(db, bid)
        _require_anonymous_student_batch(
            batch,
            has_student_tasks=_batch_has_student_tasks(db, batch.id),
        )
    return _base.open_batch(user, bid)


def _anonymous_audit(db, task_id: int) -> None:
    """只记录发生过匿名提交，不写当前学生账号、学号、姓名或可反查摘要。"""
    from app.models import AffairsAuditTrail

    db.add(AffairsAuditTrail(
        tenant_id=_tid(),
        biz_type="AA_EVALUATION",
        biz_id=int(task_id),
        action="EVAL_SUBMIT",
        operator="ANONYMOUS_STUDENT",
        role_name="STUDENT",
        detail="学生匿名评教提交",
        occurred_at=datetime.utcnow(),
    ))


def _resolve_student(db, user):
    if not _is_student_user(user):
        raise no_permission("学生评教任务仅允许学生本人访问")
    from app.services.mobile_student_identity_facade import resolve_student

    profile = resolve_student(db, user or {})
    if not profile:
        raise not_found("当前账号尚未绑定唯一学生档案")
    return profile


def _student_submission_context(db, user, task) -> tuple[object, dict, str]:
    if not getattr(task, "teaching_task_id", None):
        raise AppException(
            "DATA_CONFLICT",
            "学生评教任务未绑定正式教学任务",
            http_status=409,
        )

    from .academic_affairs_roster_consumer_service import resolve_versioned_roster

    profile = _resolve_student(db, user)
    roster = resolve_versioned_roster(db, int(task.teaching_task_id))
    student_ids = {
        int(value) for value in (roster.get("studentIds") or [])
        if str(value).isdigit()
    }
    if int(profile.id) not in student_ids:
        raise no_permission("当前学生不在该课程正式教学班名单中")
    token = _submission_token(int(task.id), int(profile.id))
    return profile, roster, token


def my_student_tasks(user, batch_id=None, include_closed=True) -> list[dict]:
    """返回当前学生正式教学班内已发布的匿名评教任务。"""
    from app.models import (
        AaEvaluationBatch,
        AaEvaluationRecord,
        AaEvaluationTask,
        AaTeachingClass,
        AaTeachingClassMember,
    )

    visible_statuses = [
        _legacy._B_PUBLISHED,
        _legacy._B_OPEN,
        _legacy._B_RESULT,
        _legacy._B_ARCHIVED,
    ]
    with session() as db:
        profile = _resolve_student(db, user)
        query = db.query(AaEvaluationTask, AaEvaluationBatch).join(
            AaEvaluationBatch,
            AaEvaluationBatch.id == AaEvaluationTask.batch_id,
        ).join(
            AaTeachingClass,
            AaTeachingClass.teaching_task_id == AaEvaluationTask.teaching_task_id,
        ).join(
            AaTeachingClassMember,
            (AaTeachingClassMember.teaching_class_id == AaTeachingClass.id)
            & (AaTeachingClassMember.roster_version_id == AaTeachingClass.current_roster_version_id),
        ).filter(
            AaEvaluationTask.tenant_id == _tid(),
            AaEvaluationTask.evaluator_type == "STUDENT",
            AaEvaluationTask.is_deleted.is_(False),
            AaEvaluationBatch.tenant_id == _tid(),
            AaEvaluationBatch.status.in_(visible_statuses),
            AaEvaluationBatch.anonymous.is_(True),
            AaEvaluationBatch.is_deleted.is_(False),
            AaTeachingClass.tenant_id == _tid(),
            AaTeachingClass.is_deleted.is_(False),
            AaTeachingClass.roster_status == "LOCKED",
            AaTeachingClassMember.tenant_id == _tid(),
            AaTeachingClassMember.student_id == int(profile.id),
            AaTeachingClassMember.status == "ACTIVE",
            AaTeachingClassMember.is_deleted.is_(False),
        )
        if batch_id:
            query = query.filter(AaEvaluationBatch.id == int(batch_id))
        if not include_closed:
            query = query.filter(AaEvaluationBatch.status == _legacy._B_OPEN)
        rows = query.distinct().order_by(
            AaEvaluationBatch.id.desc(),
            AaEvaluationTask.id.desc(),
        ).all()

        output = []
        for task, batch in rows:
            submitted = db.query(AaEvaluationRecord.id).filter(
                AaEvaluationRecord.tenant_id == _tid(),
                AaEvaluationRecord.task_id == task.id,
                AaEvaluationRecord.evaluator_type == "STUDENT",
                AaEvaluationRecord.answers_json.like(_token_pattern(task.id, profile.id)),
                AaEvaluationRecord.is_deleted.is_(False),
            ).first() is not None
            output.append({
                "taskId": str(task.id),
                "batchId": str(batch.id),
                "batchName": batch.batch_name,
                "teachingTaskId": str(task.teaching_task_id),
                "courseName": task.course_name,
                "teacherName": task.teacher_name,
                "windowStatus": batch.status,
                "anonymous": True,
                "submitted": submitted,
                "canSubmit": batch.status == _legacy._B_OPEN and not submitted,
            })
        return output


def submit_evaluation(user, task_id, answers, objective_score, comment=None):
    """提交学生匿名评教或教师角色评价，并在同一事务内完成身份、名单和幂等校验。"""
    from app.models import AaEvaluationRecord, AaEvaluationTask

    with session() as db:
        _legacy._ctx(user, db)
        query = db.query(AaEvaluationTask).filter(
            AaEvaluationTask.id == int(task_id),
            AaEvaluationTask.tenant_id == _tid(),
            AaEvaluationTask.is_deleted.is_(False),
        )
        if hasattr(query, "with_for_update"):
            query = query.with_for_update()
        task = query.first()
        if not task:
            raise not_found("应评任务不存在")

        batch = _base._writable_batch(db, task.batch_id)
        if batch.status != _legacy._B_OPEN:
            raise _legacy._invalid("评教窗口未开放")

        if task.evaluator_type == "STUDENT":
            _require_anonymous_student_batch(batch)
            profile, roster, token = _student_submission_context(db, user, task)
            duplicate = db.query(AaEvaluationRecord).filter(
                AaEvaluationRecord.tenant_id == _tid(),
                AaEvaluationRecord.task_id == task.id,
                AaEvaluationRecord.evaluator_type == "STUDENT",
                AaEvaluationRecord.answers_json.like(_token_pattern(task.id, profile.id)),
                AaEvaluationRecord.is_deleted.is_(False),
            ).first()
            if duplicate:
                raise _legacy._invalid("该课程评教已提交，不可重复提交")
            member_count = int(roster.get("memberCount") or len(roster.get("studentIds") or []))
            if member_count and int(task.submitted_count or 0) >= member_count:
                raise _legacy._invalid("该评教任务提交人数已达到正式教学班人数，请联系教务处核查")
            answers_json = _encode_student_answers(answers, token)
        else:
            keys = _legacy._derive_keys(user)
            if not task.evaluator_key or task.evaluator_key not in keys:
                raise no_permission("仅本任务指定的评价人本人可提交")
            if task.status == "SUBMITTED":
                raise _legacy._invalid("该任务已提交，不可重复提交")
            answers_json = json.dumps(answers, ensure_ascii=False) if answers else None

        record = AaEvaluationRecord(
            tenant_id=_tid(),
            batch_id=batch.id,
            task_id=task.id,
            teacher_key=task.teacher_key,
            evaluator_type=task.evaluator_type,
            answers_json=answers_json,
            objective_score=objective_score,
            comment=comment,
        )
        db.add(record)
        task.submitted_count = int(task.submitted_count or 0) + 1
        if task.evaluator_type != "STUDENT":
            task.status = "SUBMITTED"
        db.flush()
        if task.evaluator_type == "STUDENT":
            _anonymous_audit(db, task.id)
        else:
            _legacy._audit(db, task.id, "EVAL_SUBMIT", f"{task.evaluator_type} 提交")
        db.commit()
        return {"taskId": str(task.id), "submittedCount": task.submitted_count}
