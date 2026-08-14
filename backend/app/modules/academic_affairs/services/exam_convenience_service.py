"""D7-U 考务便利性与高频读优化；最终写入仍走 canonical exam facade。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from contextlib import contextmanager
from types import SimpleNamespace

from sqlalchemy import and_, func, or_, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import AppException, not_found
from app.models import (
    AaExamBatch,
    AaExamCourse,
    AaExamInvigilator,
    AaExamRoom,
    AaTeachingTask,
    AaTeachingTaskBatch,
)
from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot
from app.modules.academic_affairs.services import academic_affairs_exam_conflict_service as conflict_svc
from app.modules.academic_affairs.services import academic_affairs_exam_facade as exam_svc
from app.modules.academic_affairs.services import academic_affairs_roster_consumer_service as roster_consumer
from app.services.db_service import _tid, session

_MAX_BULK = 100
_PREVIEW_TTL_SECONDS = 10 * 60
_TOKEN_CONTEXT = b"aa-exam-course-preview-v1"
_LOCK_TIMEOUT_SECONDS = 5


def _school_batch(db, batch_id: int, user):
    batch = db.query(AaExamBatch).filter(
        AaExamBatch.id == int(batch_id),
        AaExamBatch.tenant_id == _tid(),
        AaExamBatch.is_deleted.is_(False),
    ).first()
    if not batch:
        raise not_found("考试批次不存在")
    exam_svc._legacy._require_school(exam_svc._legacy._ctx(user, db))
    return batch


def _college_scope(batch) -> list[int] | None:
    raw = getattr(batch, "college_scope_json", None)
    if not raw:
        return None
    try:
        values = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise AppException("DATA_CONFLICT", "考试批次学院范围配置异常，请先修复批次", http_status=409)
    if not isinstance(values, list):
        raise AppException("DATA_CONFLICT", "考试批次学院范围配置异常，请先修复批次", http_status=409)
    out = []
    for value in values:
        try:
            item = int(value)
        except (TypeError, ValueError):
            raise AppException("DATA_CONFLICT", "考试批次学院范围配置异常，请先修复批次", http_status=409)
        if item > 0 and item not in out:
            out.append(item)
    return out


def _eligible_query(db, batch, *, only_uncircled: bool, task_ids=None, keyword=None):
    query = db.query(AaTeachingTask, AaTeachingTaskBatch).join(
        AaTeachingTaskBatch,
        and_(
            AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ),
    )
    if only_uncircled:
        query = query.outerjoin(
            AaExamCourse,
            and_(
                AaExamCourse.tenant_id == _tid(),
                AaExamCourse.batch_id == int(batch.id),
                AaExamCourse.teaching_task_id == AaTeachingTask.id,
                AaExamCourse.is_deleted.is_(False),
            ),
        )
    query = query.filter(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
        AaTeachingTaskBatch.term_id == int(batch.term_id),
        AaTeachingTaskBatch.status == "APPROVED",
        AaTeachingTask.status == "READY",
    )
    if only_uncircled:
        query = query.filter(AaExamCourse.id.is_(None))
    scope = _college_scope(batch)
    if scope is not None:
        query = query.filter(AaTeachingTaskBatch.college_id.in_(scope or [-1]))
    if task_ids is not None:
        query = query.filter(AaTeachingTask.id.in_([int(v) for v in task_ids] or [0]))
    word = str(keyword or "").strip()
    if word:
        like = f"%{word}%"
        query = query.filter(or_(
            AaTeachingTask.course_name.ilike(like),
            AaTeachingTask.teaching_class_name.ilike(like),
            AaTeachingTask.teacher_name.ilike(like),
            AaTeachingTask.teacher_key.ilike(like),
        ))
    return query


def _candidate_dto(task, task_batch) -> dict:
    return {
        "teachingTaskId": str(task.id),
        "taskBatchId": str(task_batch.id),
        "taskBatchName": task_batch.batch_name or "",
        "collegeId": str(task_batch.college_id) if task_batch.college_id else None,
        "courseId": str(task.course_id) if task.course_id else None,
        "courseName": task.course_name or "",
        "classId": str(task.class_id) if task.class_id else None,
        "teachingClassName": task.teaching_class_name or "",
        "teacherKey": task.teacher_key or "",
        "teacherName": task.teacher_name or "",
        "taskStatus": task.status or "",
    }


def list_course_candidates(batch_id, user, *, keyword=None, page=1, page_size=20):
    with session() as db:
        batch = _school_batch(db, batch_id, user)
        if not batch.term_id:
            raise AppException("DATA_CONFLICT", "考试批次未绑定正式学期", http_status=409)
        query = _eligible_query(db, batch, only_uncircled=True, keyword=keyword)
        total = query.order_by(None).count()
        rows = query.order_by(AaTeachingTask.course_name, AaTeachingTask.id).offset(
            (max(1, int(page)) - 1) * int(page_size)
        ).limit(int(page_size)).all()
        return [_candidate_dto(task, task_batch) for task, task_batch in rows], total


def _validate_ids(task_ids) -> list[int]:
    ids, seen = [], set()
    for raw in task_ids or []:
        try:
            task_id = int(raw)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "教学任务 ID 非法")
        if task_id <= 0:
            raise AppException("VALIDATION_ERROR", "教学任务 ID 非法")
        if task_id not in seen:
            seen.add(task_id)
            ids.append(task_id)
    if not ids:
        raise AppException("VALIDATION_ERROR", "请至少选择 1 门应考课程")
    if len(ids) > _MAX_BULK:
        raise AppException("VALIDATION_ERROR", f"单次最多处理 {_MAX_BULK} 门应考课程")
    return ids


def _preview_snapshot(preview: dict) -> str:
    stable = {
        "batchId": preview.get("batchId"),
        "batchStatus": preview.get("batchStatus"),
        "items": [
            {key: item.get(key) for key in (
                "teachingTaskId", "status", "code", "taskBatchId", "courseId",
                "courseName", "teachingClassName", "teacherKey", "taskStatus",
            )}
            for item in preview.get("items") or []
        ],
    }
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode((data + "=" * (-len(data) % 4)).encode("ascii"))


def _signing_key() -> bytes:
    return hmac.new(settings.jwt_secret.encode("utf-8"), _TOKEN_CONTEXT, hashlib.sha256).digest()


def _issue_token(batch_id: int, task_ids: list[int], snapshot: str) -> str:
    now = int(time.time())
    payload = {
        "v": 1,
        "tenantId": str(_tid()),
        "batchId": str(int(batch_id)),
        "taskIds": [str(v) for v in task_ids],
        "snapshot": snapshot,
        "iat": now,
        "exp": now + _PREVIEW_TTL_SECONDS,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_signing_key(), raw, hashlib.sha256).digest()
    return f"{_b64encode(raw)}.{_b64encode(sig)}"


def _decode_token(token: str, batch_id: int) -> dict:
    try:
        raw_part, sig_part = (token or "").split(".", 1)
        raw = _b64decode(raw_part)
        supplied = _b64decode(sig_part)
        expected = hmac.new(_signing_key(), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("bad signature")
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        raise AppException("VALIDATION_ERROR", "批量圈课预览凭证无效，请重新预览")
    if payload.get("v") != 1 or payload.get("tenantId") != str(_tid()):
        raise AppException("VALIDATION_ERROR", "批量圈课预览凭证无效，请重新预览")
    if payload.get("batchId") != str(int(batch_id)):
        raise AppException("VALIDATION_ERROR", "预览凭证与当前考试批次不匹配，请重新预览")
    if int(payload.get("exp") or 0) < int(time.time()):
        raise AppException("DATA_CONFLICT", "批量圈课预览已过期，请重新预览", http_status=409)
    payload["taskIds"] = _validate_ids(payload.get("taskIds") or [])
    return payload


def bulk_course_preview(batch_id, user, task_ids):
    ids = _validate_ids(task_ids)
    with session() as db:
        batch = _school_batch(db, batch_id, user)
        rows = _eligible_query(db, batch, only_uncircled=True, task_ids=ids).all()
        by_id = {int(task.id): (task, task_batch) for task, task_batch in rows}
        items, ready = [], 0
        for task_id in ids:
            pair = by_id.get(task_id)
            if pair is None:
                items.append({
                    "teachingTaskId": str(task_id), "status": "BLOCKED",
                    "code": "NOT_AVAILABLE", "message": "该教学任务不可圈定或已被圈定",
                })
                continue
            task, task_batch = pair
            row = _candidate_dto(task, task_batch)
            if str(batch.status or "").upper() != "DRAFT":
                status, code, message = "BLOCKED", "DATA_CONFLICT", "考试批次已离开草稿阶段"
            else:
                status, code, message = "READY", "", "可圈定；确认时仍会进入正式考务写入口再次校验"
                ready += 1
            items.append({**row, "status": status, "code": code, "message": message})
        preview = {
            "batchId": str(batch.id), "batchName": batch.batch_name, "batchStatus": batch.status,
            "selected": len(ids), "ready": ready, "blocked": len(ids) - ready, "items": items,
        }
    snapshot = _preview_snapshot(preview)
    preview["previewToken"] = _issue_token(batch_id, ids, snapshot) if ready else None
    preview["previewExpiresIn"] = _PREVIEW_TTL_SECONDS if ready else 0
    return preview


@contextmanager
def exam_course_mutex(batch_id: int, task_id: int):
    lock_db = session()
    acquired = False
    lock_name = ""
    try:
        if lock_db.get_bind().dialect.name == "mysql":
            raw = f"{_tid()}:{int(batch_id)}:{int(task_id)}".encode("utf-8")
            lock_name = "aa-exam-course:" + hashlib.sha256(raw).hexdigest()[:40]
            acquired = lock_db.execute(
                text("SELECT GET_LOCK(:lock_name, :timeout_seconds)"),
                {"lock_name": lock_name, "timeout_seconds": _LOCK_TIMEOUT_SECONDS},
            ).scalar() == 1
            if not acquired:
                raise AppException("DATA_CONFLICT", "同一课程正在圈定，请稍后重新预览", http_status=409)
        yield
    finally:
        if acquired:
            try:
                lock_db.execute(text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": lock_name})
            except Exception:
                pass
        lock_db.close()


def _still_candidate(batch_id: int, user, task_id: int) -> bool:
    with session() as db:
        batch = _school_batch(db, batch_id, user)
        if str(batch.status or "").upper() != "DRAFT":
            return False
        return _eligible_query(db, batch, only_uncircled=True, task_ids=[task_id]).first() is not None


def _apply_preview(batch_id, user, preview):
    items = []
    for item in preview.get("items") or []:
        task_id = int(item["teachingTaskId"])
        if item.get("status") != "READY":
            items.append({
                "teachingTaskId": str(task_id), "ok": False,
                "code": item.get("code") or "NOT_AVAILABLE", "message": item.get("message") or "不可圈定",
            })
            continue
        with exam_course_mutex(batch_id, task_id):
            if not _still_candidate(batch_id, user, task_id):
                items.append({
                    "teachingTaskId": str(task_id), "ok": False,
                    "code": "DATA_CONFLICT", "message": "课程状态已变化或已被圈定，请重新预览",
                })
                continue
            try:
                result = exam_svc.add_exam_course(user, int(batch_id), SimpleNamespace(teachingTaskId=task_id))
            except AppException as exc:
                items.append({"teachingTaskId": str(task_id), "ok": False, "code": exc.code, "message": exc.message})
            except IntegrityError:
                items.append({
                    "teachingTaskId": str(task_id), "ok": False,
                    "code": "DATA_CONFLICT", "message": "课程已被其它请求圈定，请刷新后继续",
                })
            else:
                items.append({
                    "teachingTaskId": str(task_id), "ok": True, "code": "", "message": "已圈定",
                    "examCourseId": result.get("examCourseId"),
                    "courseName": result.get("courseName") or item.get("courseName") or "",
                })
    succeeded = sum(1 for item in items if item.get("ok"))
    return {
        "batchId": str(batch_id), "selected": len(items), "succeeded": succeeded,
        "failed": len(items) - succeeded, "items": items,
    }


def bulk_course_confirm(batch_id, user, preview_token):
    token = _decode_token(preview_token, batch_id)
    current = bulk_course_preview(batch_id, user, token["taskIds"])
    if _preview_snapshot(current) != token.get("snapshot"):
        raise AppException("DATA_CONFLICT", "应考课程或教学任务状态已变化，请重新预览后再确认", http_status=409)
    return _apply_preview(batch_id, user, current)


def _snapshot_map(db, course_ids: list[int]) -> dict[int, dict]:
    ids = sorted({int(v) for v in course_ids if v})
    if not ids:
        return {}
    rows = db.query(AaRosterConsumerSnapshot).filter(
        AaRosterConsumerSnapshot.tenant_id == _tid(),
        AaRosterConsumerSnapshot.consumer_type == "EXAM_COURSE",
        AaRosterConsumerSnapshot.consumer_id.in_(ids),
        AaRosterConsumerSnapshot.status == "ACTIVE",
        AaRosterConsumerSnapshot.is_deleted.is_(False),
    ).order_by(AaRosterConsumerSnapshot.consumer_id, AaRosterConsumerSnapshot.snapshot_version.desc()).all()
    grouped: dict[int, list] = {}
    for row in rows:
        grouped.setdefault(int(row.consumer_id), []).append(row)
    result = {}
    for course_id, group in grouped.items():
        active = roster_consumer._active_row(group)
        if active:
            result[course_id] = roster_consumer._snapshot_dto(active)
    return result


def list_courses(user, batch_id, page=1, page_size=100):
    rows, total = exam_svc._legacy.list_courses(user, batch_id, page, page_size)
    course_ids = [int(row["examCourseId"]) for row in rows if str(row.get("examCourseId") or "").isdigit()]
    with session() as db:
        snapshots = _snapshot_map(db, course_ids)
    for row in rows:
        row["rosterIdentity"] = snapshots.get(int(row["examCourseId"]))
    return rows, total


def batch_readiness(batch_id, user) -> dict:
    with session() as db:
        batch = _school_batch(db, batch_id, user)
        if not batch.term_id:
            raise AppException("DATA_CONFLICT", "考试批次未绑定正式学期", http_status=409)
        eligible_count = _eligible_query(db, batch, only_uncircled=False).order_by(None).count()
        pending_candidate_count = _eligible_query(db, batch, only_uncircled=True).order_by(None).count()
        courses = db.query(AaExamCourse).filter(
            AaExamCourse.tenant_id == _tid(), AaExamCourse.batch_id == int(batch.id),
            AaExamCourse.status != "REMOVED", AaExamCourse.is_deleted.is_(False),
        ).all()
        confirmed = [row for row in courses if str(row.status or "").upper() == "CONFIRMED"]
        pending_confirm = [row for row in courses if str(row.status or "").upper() == "PENDING_CONFIRM"]
        course_ids = [int(row.id) for row in confirmed]
        rooms = db.query(AaExamRoom).filter(
            AaExamRoom.tenant_id == _tid(), AaExamRoom.exam_course_id.in_(course_ids or [0]),
            AaExamRoom.status == "ACTIVE", AaExamRoom.is_deleted.is_(False),
        ).all()
        rooms_by_course: dict[int, list] = {}
        for room in rooms:
            rooms_by_course.setdefault(int(room.exam_course_id), []).append(room)
        room_ids = [int(room.id) for room in rooms]
        inv_counts = dict(db.query(AaExamInvigilator.exam_room_id, func.count(AaExamInvigilator.id)).filter(
            AaExamInvigilator.tenant_id == _tid(),
            AaExamInvigilator.exam_room_id.in_(room_ids or [0]),
            AaExamInvigilator.is_deleted.is_(False),
        ).group_by(AaExamInvigilator.exam_room_id).all())
        arranged_count = 0
        room_shortage_count = 0
        for course in confirmed:
            course_rooms = rooms_by_course.get(int(course.id), [])
            if course.exam_date and course.start_time and course.end_time and course_rooms:
                arranged_count += 1
            capacity = sum(exam_svc._effective_room_capacity(room) for room in course_rooms)
            if not course_rooms or capacity < int(course.expected_students or 0):
                room_shortage_count += 1
        missed_count = max(0, len(confirmed) - arranged_count)
        invigilator_gap_count = sum(1 for room in rooms if int(inv_counts.get(int(room.id), 0) or 0) <= 0)
        blockers = []
        if pending_candidate_count:
            blockers.append(f"仍有 {pending_candidate_count} 门已终审应考课程尚未圈定")
        if pending_confirm:
            blockers.append(f"仍有 {len(pending_confirm)} 门考试课程待学院确认")
        if missed_count:
            blockers.append(f"仍有 {missed_count} 门已确认课程未完成排考")
        if room_shortage_count:
            blockers.append(f"仍有 {room_shortage_count} 门课程考场容量不足或无考场")
        if invigilator_gap_count:
            blockers.append(f"仍有 {invigilator_gap_count} 个考场缺少监考教师")
        if str(batch.status or "").upper() not in {"COURSE_CONFIRMED", "ARRANGED"}:
            blockers.append("考试批次尚未进入可发布阶段")
        if not confirmed:
            blockers.append("当前没有已确认考试课程")
        if not blockers:
            _courses, exact_problems = exam_svc._check_arrangement_complete(db, int(batch.id))
            blockers.extend(exact_problems)
            if not blockers:
                conflict_result = conflict_svc.validate_exam_batch_conflicts(db, batch)
                blockers.extend([str(item) for item in (conflict_result.get("problems") or [])])
        return {
            "batchId": str(batch.id), "batchName": batch.batch_name, "batchStatus": batch.status,
            "eligibleCourseCount": int(eligible_count), "circledCourseCount": len(courses),
            "pendingCandidateCount": int(pending_candidate_count), "confirmedCourseCount": len(confirmed),
            "pendingConfirmCount": len(pending_confirm), "arrangedCourseCount": int(arranged_count),
            "missedCourseCount": int(missed_count), "invigilatorGapCount": int(invigilator_gap_count),
            "roomShortageCount": int(room_shortage_count), "canPublish": not blockers,
            "blockingReasons": blockers[:10],
        }
