"""R10 动态成绩项。

兼容原则：
- 未配置时自动映射现有平时/期中/期末比例；
- 任意1-12个成绩项权重合计100，首次录分后方案锁定；
- 可选项未提交按0分写入证据，禁止缩小总权重后虚高总评；
- 动态分项真实落库，最终总评仍写 AaGradeRecord，继续复用原审核、发布、预警与成绩单链路。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

from . import academic_affairs_grade_service as grade_service
from .academic_affairs_roster_consumer_service import resolve_versioned_roster

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,39}$")
_ALLOWED_FLAGS = {"NORMAL", "ABSENT", "DEFERRED", "EXEMPT", "CHEAT"}
_EDITABLE = {"NOT_STARTED", "INPUTTING", "RETURNED"}


def _operator() -> str:
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or ctx.get("realName") or "")


def _default_components(task) -> list[dict]:
    rows = []
    for code, name, weight in (
        ("USUAL", "平时成绩", task.usual_ratio),
        ("MIDTERM", "期中成绩", getattr(task, "midterm_ratio", 0)),
        ("FINAL", "期末成绩", task.final_ratio),
    ):
        if float(weight or 0) > 0:
            rows.append({
                "code": code,
                "name": name,
                "weight": float(weight),
                "required": True,
                "order": len(rows) + 1,
            })
    if not rows:
        raise AppException("DATA_CONFLICT", "成绩任务没有可用成绩比例，请先配置动态成绩项", http_status=409)
    return rows


def normalize_components(components) -> list[dict]:
    source = list(components or [])
    if len(source) < 1 or len(source) > 12:
        raise AppException("VALIDATION_ERROR", "动态成绩项须为1-12项")
    result = []
    codes = set()
    for index, raw in enumerate(source, start=1):
        code = str((raw or {}).get("code") or "").strip().upper()
        name = str((raw or {}).get("name") or "").strip()
        if not _CODE_RE.match(code):
            raise AppException("VALIDATION_ERROR", f"第{index}项代码须为大写字母开头的字母数字下划线")
        if code in codes:
            raise AppException("VALIDATION_ERROR", f"成绩项代码重复：{code}")
        if not name or len(name) > 80:
            raise AppException("VALIDATION_ERROR", f"第{index}项名称必填且不超过80字")
        try:
            weight = float((raw or {}).get("weight"))
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", f"第{index}项权重须为数字") from exc
        if weight <= 0 or weight > 100:
            raise AppException("VALIDATION_ERROR", f"第{index}项权重须大于0且不超过100")
        result.append({
            "code": code,
            "name": name,
            "weight": round(weight, 4),
            "required": bool((raw or {}).get("required", True)),
            "order": int((raw or {}).get("order") or index),
        })
        codes.add(code)
    result.sort(key=lambda item: (item["order"], item["code"]))
    total = round(sum(item["weight"] for item in result), 4)
    if abs(total - 100.0) > 0.0001:
        raise AppException("VALIDATION_ERROR", f"动态成绩项权重合计必须为100，当前为{total}")
    return result


def _task(db, task_id, user, *, lock=False):
    from app.models import AaGradeTask

    query = db.query(AaGradeTask).filter(
        AaGradeTask.id == int(task_id),
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    task = query.first()
    if not task:
        raise not_found("成绩录入任务不存在")
    grade_service._check_course_scope(task, user)
    return task


def _scheme_row(db, task, *, lock=False):
    from app.models.academic_affairs_r10 import AaGradeSchemeSnapshot

    query = db.query(AaGradeSchemeSnapshot).filter(
        AaGradeSchemeSnapshot.tenant_id == _tid(),
        AaGradeSchemeSnapshot.grade_task_id == task.id,
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def _scheme(db, task, *, create_default=False):
    row = _scheme_row(db, task, lock=create_default)
    if row and row.is_deleted:
        if not create_default:
            return None
        components = _default_components(task)
        row.is_deleted = False
        row.scheme_version = int(row.scheme_version or 0) + 1
        row.scheme_json = json.dumps(components, ensure_ascii=False, separators=(",", ":"))
        row.total_weight = 100
        row.status = "DRAFT"
        row.locked_at = None
        row.locked_by = None
        db.flush()
    elif not row and create_default:
        from app.models.academic_affairs_r10 import AaGradeSchemeSnapshot

        components = _default_components(task)
        row = AaGradeSchemeSnapshot(
            tenant_id=_tid(),
            grade_task_id=task.id,
            scheme_version=1,
            scheme_json=json.dumps(components, ensure_ascii=False, separators=(",", ":")),
            total_weight=100,
            status="DRAFT",
        )
        db.add(row)
        db.flush()
    return row


def _components(row, task) -> list[dict]:
    if not row:
        return _default_components(task)
    try:
        return normalize_components(json.loads(row.scheme_json or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppException("DATA_CONFLICT", "动态成绩方案快照损坏，请联系教务处修复", http_status=409) from exc


def get_scheme(task_id, user) -> dict:
    with session() as db:
        task = _task(db, task_id, user)
        row = _scheme(db, task)
        components = _components(row, task)
        return {
            "gradeTaskId": str(task.id),
            "schemeId": str(row.id) if row else "",
            "schemeVersion": int(row.scheme_version or 1) if row else 1,
            "status": row.status if row else "DEFAULT",
            "components": components,
            "totalWeight": sum(item["weight"] for item in components),
            "editable": task.status == "NOT_STARTED" and (not row or row.status == "DRAFT"),
        }


def configure_scheme(task_id, user, components) -> dict:
    from app.models import AaGradeRecord
    from app.models.academic_affairs_r10 import AaGradeSchemeSnapshot
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    normalized = normalize_components(components)
    with session() as db:
        task = _task(db, task_id, user, lock=True)
        guard_term_writable(db, task.term_id)
        if task.status != "NOT_STARTED":
            raise AppException("DATA_CONFLICT", "成绩任务开始录分后不可修改成绩项方案")
        record_count = db.query(AaGradeRecord).filter(
            AaGradeRecord.tenant_id == _tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.is_deleted.is_(False),
        ).count()
        if record_count:
            raise AppException("DATA_CONFLICT", "成绩任务已有录分记录，不可修改成绩项方案")
        row = _scheme_row(db, task, lock=True)
        if row and not row.is_deleted and row.status == "LOCKED":
            raise AppException("DATA_CONFLICT", "动态成绩方案已锁定")
        if not row:
            row = AaGradeSchemeSnapshot(
                tenant_id=_tid(),
                grade_task_id=task.id,
                scheme_version=1,
                scheme_json="[]",
                total_weight=100,
                status="DRAFT",
            )
            db.add(row)
        else:
            row.is_deleted = False
            row.scheme_version = int(row.scheme_version or 0) + 1
        row.scheme_json = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        row.total_weight = 100
        row.status = "DRAFT"
        row.locked_at = None
        row.locked_by = None
        grade_service._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "GRADE_SCHEME_CONFIG",
            f"version={row.scheme_version};components={len(normalized)}",
        )
        db.commit()
        db.refresh(row)
        return {
            "gradeTaskId": str(task.id),
            "schemeId": str(row.id),
            "schemeVersion": int(row.scheme_version),
            "status": row.status,
            "components": normalized,
            "totalWeight": 100,
        }


def _score(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{name}须为0-100数字") from exc
    if number < 0 or number > 100:
        raise AppException("VALIDATION_ERROR", f"{name}须为0-100数字")
    return round(number, 2)


def enter_component_scores(task_id, user, student_id, scores, exception_flag="NORMAL") -> dict:
    from app.models import AaGradeRecord
    from app.models.academic_affairs_r10 import AaGradeComponentScore
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    flag = str(exception_flag or "NORMAL").upper()
    if flag not in _ALLOWED_FLAGS:
        raise AppException("VALIDATION_ERROR", "异常标记非法")
    with session() as db:
        task = _task(db, task_id, user, lock=True)
        guard_term_writable(db, task.term_id)
        if task.status not in _EDITABLE:
            raise AppException("DATA_CONFLICT", "当前状态不可录入动态成绩")
        if not task.teaching_task_id:
            raise AppException("DATA_CONFLICT", "动态成绩只适用于绑定教学任务的正常成绩任务")
        roster = resolve_versioned_roster(db, int(task.teaching_task_id))
        if int(student_id) not in set(roster["studentIds"]):
            raise AppException("NO_DATA_SCOPE", "该学生不在成绩任务正式名单", http_status=403)
        scheme = _scheme(db, task, create_default=True)
        components = _components(scheme, task)
        submitted = {str(key).upper(): value for key, value in (scores or {}).items()}

        record = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(),
            AaGradeRecord.task_id == task.id,
            AaGradeRecord.student_id == int(student_id),
            AaGradeRecord.is_deleted.is_(False),
        )).first()
        if not record:
            record = AaGradeRecord(tenant_id=_tid(), task_id=task.id, student_id=int(student_id))
            db.add(record)
            db.flush()

        if flag != "NORMAL":
            record.usual_score = None
            record.midterm_score = None
            record.final_score = None
            record.total_score = None
            record.pass_status = None
            record.exception_flag = flag
            db.query(AaGradeComponentScore).filter(
                AaGradeComponentScore.tenant_id == _tid(),
                AaGradeComponentScore.grade_task_id == task.id,
                AaGradeComponentScore.student_id == int(student_id),
                AaGradeComponentScore.is_deleted.is_(False),
            ).update({AaGradeComponentScore.is_deleted: True}, synchronize_session=False)
            total = None
            component_rows = []
        else:
            missing = [
                item["code"] for item in components
                if item["required"] and item["code"] not in submitted
            ]
            if missing:
                raise AppException("VALIDATION_ERROR", "缺少必填成绩项：" + "、".join(missing))
            component_rows = []
            total = 0.0
            for component in components:
                supplied = component["code"] in submitted
                value = _score(submitted[component["code"]], component["name"]) if supplied else 0.0
                weighted = round(value * component["weight"] / 100.0, 4)
                total += weighted
                row = db.scalars(select(AaGradeComponentScore).where(
                    AaGradeComponentScore.tenant_id == _tid(),
                    AaGradeComponentScore.grade_task_id == task.id,
                    AaGradeComponentScore.student_id == int(student_id),
                    AaGradeComponentScore.component_code == component["code"],
                ).with_for_update()).first()
                if not row:
                    row = AaGradeComponentScore(
                        tenant_id=_tid(),
                        grade_task_id=task.id,
                        grade_record_id=record.id,
                        student_id=int(student_id),
                        component_code=component["code"],
                    )
                    db.add(row)
                else:
                    row.is_deleted = False
                    row.grade_record_id = record.id
                row.component_name = component["name"]
                row.weight = component["weight"]
                row.score = value
                row.weighted_score = weighted
                row.scheme_version = int(scheme.scheme_version or 1)
                component_rows.append({
                    **component,
                    "score": value,
                    "weightedScore": weighted,
                    "defaultedToZero": not supplied,
                })
                if component["code"] == "USUAL":
                    record.usual_score = round(value)
                elif component["code"] == "MIDTERM":
                    record.midterm_score = round(value)
                elif component["code"] == "FINAL":
                    record.final_score = round(value)
            total = round(total, 2)
            record.total_score = round(total)
            record.pass_status = "PASSED" if total >= float(task.pass_line or 60) else "FAILED"
            record.exception_flag = "NORMAL"

        if task.status == "NOT_STARTED":
            task.status = "INPUTTING"
        if scheme.status != "LOCKED":
            scheme.status = "LOCKED"
            scheme.locked_at = datetime.utcnow()
            scheme.locked_by = _operator()
        grade_service._audit(
            db,
            "AA_GRADE_TASK",
            task.id,
            "DYNAMIC_GRADE_ENTER",
            f"student={student_id};schemeVersion={scheme.scheme_version};components={len(component_rows)};flag={flag}",
        )
        db.commit()
        return {
            "gradeTaskId": str(task.id),
            "studentId": str(student_id),
            "recordId": str(record.id),
            "schemeVersion": int(scheme.scheme_version or 1),
            "components": component_rows,
            "totalScore": total,
            "passStatus": record.pass_status,
            "exceptionFlag": record.exception_flag,
        }


def student_component_scores(task_id, user, student_id) -> dict:
    from app.models.academic_affairs_r10 import AaGradeComponentScore

    with session() as db:
        task = _task(db, task_id, user)
        rows = db.scalars(select(AaGradeComponentScore).where(
            AaGradeComponentScore.tenant_id == _tid(),
            AaGradeComponentScore.grade_task_id == task.id,
            AaGradeComponentScore.student_id == int(student_id),
            AaGradeComponentScore.is_deleted.is_(False),
        ).order_by(AaGradeComponentScore.id)).all()
        return {
            "gradeTaskId": str(task.id),
            "studentId": str(student_id),
            "items": [{
                "componentCode": row.component_code,
                "componentName": row.component_name,
                "weight": row.weight,
                "score": row.score,
                "weightedScore": row.weighted_score,
                "schemeVersion": row.scheme_version,
            } for row in rows],
        }
