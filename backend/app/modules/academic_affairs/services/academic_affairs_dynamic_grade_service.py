"""R10 动态成绩项。

兼容原则：
- 未配置时自动映射现有平时/期中/期末比例；
- 任意1-12个成绩项权重合计100，首次录分后方案锁定；
- 可选项未提交按0分写入证据，禁止缩小总权重后虚高总评；
- 动态分项真实落库，最终总评仍写 AaGradeRecord，继续复用原审核、发布、预警与成绩单链路。
"""
from __future__ import annotations

import json
import math
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
        if isinstance((raw or {}).get("weight"), bool) or not math.isfinite(weight) or weight <= 0 or weight > 100:
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
    if isinstance(value, bool) or not math.isfinite(number) or number < 0 or number > 100:
        raise AppException("VALIDATION_ERROR", f"{name}须为0-100数字")
    return round(number, 2)


def _conflict(message):
    return AppException("DATA_CONFLICT", message, http_status=409)


def uses_components(db, task) -> bool:
    from app.models.academic_affairs_r10 import AaGradeComponentScore
    scheme = _scheme_row(db, task)
    return bool((scheme and not scheme.is_deleted) or db.scalar(select(AaGradeComponentScore.id).where(
        AaGradeComponentScore.tenant_id == _tid(), AaGradeComponentScore.grade_task_id == task.id,
        AaGradeComponentScore.is_deleted.is_(False)).limit(1)))


def require_fixed_score_entry(db, task):
    from app.models import AaGradeTask
    # Legacy core entry did not lock the task: close its race with first dynamic entry.
    current = db.query(AaGradeTask).filter(AaGradeTask.id == task.id, AaGradeTask.tenant_id == _tid(),
        AaGradeTask.is_deleted.is_(False)).populate_existing().with_for_update().first()
    if not current or current.status not in _EDITABLE or current.publish_at:
        raise _conflict("当前状态不可录入固定成绩")
    if uses_components(db, task):
        raise _conflict("任务已有动态成绩方案或分项证据，请通过动态分项入口录入，不能覆盖为固定三段")


def formal_roster(db, task, *, lock=False):
    """Read an existing LOCKED roster; never create a teaching-class projection."""
    from app.models import AaTeachingClass, AaTeachingClassRosterVersion
    from . import academic_affairs_roster_consumer_service as consumer
    if not task.teaching_task_id:
        raise _conflict("动态成绩须绑定正式教学任务；管理员补录使用专用流程")
    query = db.query(AaTeachingClass).filter(
        AaTeachingClass.tenant_id == _tid(), AaTeachingClass.teaching_task_id == task.teaching_task_id,
        AaTeachingClass.is_deleted.is_(False), AaTeachingClass.status == "ACTIVE")
    if lock:
        query = query.with_for_update().populate_existing()
    teaching_class = query.first()
    if not teaching_class or not teaching_class.current_roster_version_id:
        raise _conflict("缺少已投影的正式教学班名单，请先完成名单投影")
    query = db.query(AaTeachingClassRosterVersion).filter(
        AaTeachingClassRosterVersion.id == teaching_class.current_roster_version_id,
        AaTeachingClassRosterVersion.tenant_id == _tid(), AaTeachingClassRosterVersion.is_deleted.is_(False),
        AaTeachingClassRosterVersion.status == "LOCKED")
    if lock:
        query = query.with_for_update().populate_existing()
    version = query.first()
    resolved = consumer.teaching_class_service.resolve_teaching_task_roster(db, int(task.teaching_task_id))
    ids = sorted({int(v) for v in resolved.get("studentIds") or []})
    if (not version or not resolved.get("ready") or not ids
            or str(resolved.get("rosterVersionId") or "") != str(version.id)
            or str(resolved.get("teachingClassId") or "") != str(teaching_class.id)
            or version.roster_hash != consumer.roster_hash(ids)
            or int(version.member_count or 0) != len(ids)):
        raise _conflict("正式名单版本、成员或来源不一致，请刷新并核对名单投影")
    return {**resolved, "studentIds": ids, "rosterVersionId": str(version.id),
            "rosterVersionNo": int(version.version_no), "rosterHash": version.roster_hash,
            "teachingClassId": str(teaching_class.id), "memberCount": len(ids)}


def roster_identity(roster):
    return {"source": str(roster.get("source") or ""),
            "teachingClassId": str(roster.get("teachingClassId") or ""),
            "rosterVersionId": str(roster.get("rosterVersionId") or ""),
            "rosterVersionNo": int(roster.get("rosterVersionNo") or 0),
            "rosterHash": str(roster.get("rosterHash") or ""),
            "memberCount": int(roster.get("memberCount") or len(roster.get("studentIds") or []))}


def require_expected_identity(task, scheme, roster, expected):
    if expected is None:
        return  # compatibility single-row/submit only; the new batch router requires all fields.
    current = {"expectedTaskVersion": int(task.version or 0),
               "expectedSchemeId": str(scheme.id) if scheme and not scheme.is_deleted else "",
               "expectedSchemeVersion": int(scheme.scheme_version or 1) if scheme and not scheme.is_deleted else 1,
               "rosterIdentity": roster_identity(roster)}
    if any(expected.get(key) != value for key, value in current.items()):
        raise _conflict("成绩任务、方案或正式名单版本已变化，请重新读取后确认")


def prepare_component_row(components, scores, exception_flag="NORMAL"):
    """Pure validation and canonical rounding, shared by one-row and batch entry."""
    flag = str(exception_flag or "NORMAL").upper()
    if flag not in _ALLOWED_FLAGS:
        raise AppException("VALIDATION_ERROR", "异常标记非法")
    if not isinstance(scores, dict):
        raise AppException("VALIDATION_ERROR", "分项成绩须为代码到数值的映射")
    submitted = {str(key).upper(): value for key, value in scores.items()}
    if len(submitted) != len(scores):
        raise AppException("VALIDATION_ERROR", "成绩项代码大小写重复")
    known = {item["code"] for item in components}
    if set(submitted) - known:
        raise AppException("VALIDATION_ERROR", "提交了正式方案之外的成绩项")
    if flag != "NORMAL":
        return {"exceptionFlag": flag, "components": [], "totalScore": None}
    missing = [item["code"] for item in components if item["required"] and item["code"] not in submitted]
    if missing:
        raise AppException("VALIDATION_ERROR", "缺少必填成绩项：" + "、".join(missing))
    entries = []
    for item in components:
        supplied = item["code"] in submitted
        value = _score(submitted[item["code"]], item["name"]) if supplied else 0.0
        entries.append({**item, "score": value, "weightedScore": round(value * item["weight"] / 100.0, 4),
                        "defaultedToZero": not supplied})
    return {"exceptionFlag": flag, "components": entries,
            "totalScore": round(sum(item["weightedScore"] for item in entries), 2)}


def write_component_row(db, task, scheme, student_id, record, prepared):
    """Caller owns locks, transaction and commit. Never writes a published record."""
    from app.models import AaGradeRecord
    from app.models.academic_affairs_r10 import AaGradeComponentScore
    if record and record.acad_grade_id:
        raise _conflict("该成绩已形成正式发布记录，请走成绩更正")
    if not record:
        record = AaGradeRecord(tenant_id=_tid(), task_id=task.id, student_id=student_id)
        db.add(record)
        db.flush()
    existing = db.scalars(select(AaGradeComponentScore).where(
        AaGradeComponentScore.tenant_id == _tid(), AaGradeComponentScore.grade_task_id == task.id,
        AaGradeComponentScore.student_id == student_id).order_by(AaGradeComponentScore.id)
        .with_for_update().execution_options(populate_existing=True)).all()
    by_code = {row.component_code: row for row in existing}
    if len(by_code) != len(existing):
        raise _conflict("同一学生存在重复动态分项证据，请先核对")
    record.usual_score = record.midterm_score = record.final_score = None
    retained = set()
    for item in prepared["components"]:
        code = item["code"]
        retained.add(code)
        row = by_code.get(code)
        if not row:
            row = AaGradeComponentScore(tenant_id=_tid(), grade_task_id=task.id,
                grade_record_id=record.id, student_id=student_id, component_code=code)
            db.add(row)
        row.is_deleted = False
        row.grade_record_id = record.id
        row.component_name, row.weight = item["name"], item["weight"]
        row.score, row.weighted_score = item["score"], item["weightedScore"]
        row.scheme_version = int(scheme.scheme_version or 1)
        row.version = int(row.version or 0) + 1
        if code in {"USUAL", "MIDTERM", "FINAL"}:
            setattr(record, {"USUAL": "usual_score", "MIDTERM": "midterm_score", "FINAL": "final_score"}[code], round(item["score"]))
    for code, row in by_code.items():
        if code not in retained and not row.is_deleted:
            row.is_deleted = True
            row.version = int(row.version or 0) + 1
    total = prepared["totalScore"]
    record.total_score = round(total) if total is not None else None
    record.pass_status = ("PASSED" if total >= float(task.pass_line or 60) else "FAILED") if total is not None else None
    record.exception_flag = prepared["exceptionFlag"]
    record.version = int(record.version or 0) + 1
    return {"gradeTaskId": str(task.id), "studentId": str(student_id), "recordId": str(record.id),
            "rowVersion": record.version, "schemeVersion": int(scheme.scheme_version or 1),
            "components": prepared["components"], "totalScore": total,
            "recordTotalScore": record.total_score, "passStatus": record.pass_status,
            "exceptionFlag": record.exception_flag}


def _enter_batch(task_id, user, rows, *, expected=None, command_key=None, check_rows=False):
    from app.models import AaGradeRecord
    from . import academic_affairs_grade_command_receipt as receipts
    from .academic_affairs_archive_service import guard_term_writable
    if not rows or len(rows) > 500:
        raise AppException("VALIDATION_ERROR", "单次保存须为1至500行")
    with session() as db:
        receipt, previous = receipts.begin(db, user, "GRADE_COMPONENT_BATCH_SAVE", command_key,
            {"gradeTaskId": str(task_id), "expected": expected, "rows": rows})
        if previous is not None:
            return previous
        task = _task(db, task_id, user, lock=True)
        guard_term_writable(db, task.term_id)
        if task.status not in _EDITABLE or task.publish_at:
            raise _conflict("当前状态不可录分；已提交或已发布成绩使用正式更正流程")
        if task.deadline_at and datetime.utcnow() > task.deadline_at:
            raise AppException("GRADE_DEADLINE_EXPIRED", "录分截止时间已过，请先申请延期", http_status=409)
        scheme = _scheme_row(db, task, lock=True)
        if (not scheme or scheme.is_deleted) and db.scalar(select(AaGradeRecord.id).where(
                AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == task.id,
                AaGradeRecord.is_deleted.is_(False)).limit(1)):
            raise _conflict("任务已有固定成绩记录，不能在录分后切换动态方案或清空原分项")
        roster = formal_roster(db, task, lock=True)
        require_expected_identity(task, scheme, roster, expected)
        components = _components(scheme if scheme and not scheme.is_deleted else None, task)
        roster_ids, seen, prepared = set(roster["studentIds"]), set(), []
        for raw in rows:
            if not isinstance(raw, dict):
                raise AppException("VALIDATION_ERROR", "每行成绩须为对象")
            sid_raw = raw.get("studentId")
            if isinstance(sid_raw, bool) or not str(sid_raw).isdigit() or int(sid_raw) <= 0:
                raise AppException("VALIDATION_ERROR", "studentId须为正整数")
            sid = int(sid_raw)
            if sid in seen:
                raise AppException("VALIDATION_ERROR", "整批成绩包含重复学生")
            if sid not in roster_ids:
                raise AppException("NO_DATA_SCOPE", "学生不在当前正式名单", http_status=403)
            seen.add(sid)
            prepared.append((sid, raw, prepare_component_row(components, raw.get("scores", {}), raw.get("exceptionFlag", "NORMAL"))))
        records = db.scalars(select(AaGradeRecord).where(
            AaGradeRecord.tenant_id == _tid(), AaGradeRecord.task_id == task.id,
            AaGradeRecord.student_id.in_(sorted(seen)), AaGradeRecord.is_deleted.is_(False))
            .order_by(AaGradeRecord.student_id, AaGradeRecord.id).with_for_update()
            .execution_options(populate_existing=True)).all()
        by_student = {int(row.student_id): row for row in records}
        if len(by_student) != len(records):
            raise _conflict("正式成绩记录存在重复学生，请先核对")
        for sid, raw, _item in prepared:
            record = by_student.get(sid)
            if record and record.acad_grade_id:
                raise _conflict("该学生成绩已发布，请使用成绩更正")
            if check_rows and (raw.get("expectedRecordId") != (str(record.id) if record else "")
                    or raw.get("expectedRowVersion") != (int(record.version or 0) if record else None)):
                raise _conflict("学生成绩已由其他操作更新，请重新读取分项后确认")
        scheme = _scheme(db, task, create_default=True)
        saved = [write_component_row(db, task, scheme, sid, by_student.get(sid), item)
                 for sid, _raw, item in sorted(prepared, key=lambda value: value[0])]
        if task.status == "NOT_STARTED":
            task.status = "INPUTTING"
        task.version = int(task.version or 0) + 1
        if scheme.status != "LOCKED":
            scheme.status, scheme.locked_at, scheme.locked_by = "LOCKED", datetime.utcnow(), _operator()
        grade_service._audit(db, "AA_GRADE_TASK", task.id, "DYNAMIC_GRADE_BATCH_ENTER",
            f"saved={len(saved)};schemeVersion={scheme.scheme_version};roster={roster['rosterVersionId']}")
        db.flush()
        result = {"gradeTaskId": str(task.id), "taskVersion": task.version,
                  "schemeId": str(scheme.id), "schemeVersion": int(scheme.scheme_version),
                  "savedCount": len(saved), "items": saved, "status": task.status,
                  "rosterIdentity": roster_identity(roster), "qualityReport": quality_in_session(db, task, roster)}
        receipts.finish(db, receipt, result)
        db.commit()
        return result


def enter_component_batch(task_id, user, rows, expected, *, command_key):
    if expected is None or not command_key:
        raise AppException("VALIDATION_ERROR", "动态整批保存须提供版本身份与原命令键")
    return _enter_batch(task_id, user, rows, expected=expected, command_key=command_key, check_rows=True)


def enter_component_scores(task_id, user, student_id, scores, exception_flag="NORMAL") -> dict:
    """Legacy one-row URL keeps its DTO; the mutation uses the same batch kernel."""
    result = _enter_batch(task_id, user, [{"studentId": student_id, "scores": scores, "exceptionFlag": exception_flag}])
    return result["items"][0]


def quality_in_session(db, task, roster):
    """One dynamic completeness predicate for read reports and locked final submit."""
    from collections import defaultdict
    from app.models import AaGradeRecord
    from app.models.academic_affairs_r10 import AaGradeComponentScore
    from .academic_affairs_archive_service import guard_term_writable
    scheme = _scheme(db, task)
    components = _components(scheme, task)
    records = db.scalars(select(AaGradeRecord).where(AaGradeRecord.tenant_id == _tid(),
        AaGradeRecord.task_id == task.id, AaGradeRecord.is_deleted.is_(False))).all()
    scores = db.scalars(select(AaGradeComponentScore).where(AaGradeComponentScore.tenant_id == _tid(),
        AaGradeComponentScore.grade_task_id == task.id, AaGradeComponentScore.is_deleted.is_(False))).all()
    records_by_student, scores_by_student = defaultdict(list), defaultdict(list)
    for row in records:
        records_by_student[int(row.student_id)].append(row)
    for row in scores:
        scores_by_student[int(row.student_id)].append(row)
    known = {item["code"]: item for item in components}
    ids = set(roster["studentIds"])
    profiles = {int(row["studentId"]): row for row in roster.get("items", [])}
    issues, missing, incomplete, special, passed, failed = [], 0, 0, 0, 0, 0
    def issue(sid, code, message):
        profile = profiles.get(sid, {})
        issues.append({"studentId": str(sid), "studentNo": profile.get("studentNo", ""),
                       "realName": profile.get("realName") or profile.get("studentName", ""),
                       "code": code, "message": message})
    for sid in sorted(ids):
        current, evidence = records_by_student[sid], scores_by_student[sid]
        if not current:
            missing += 1; issue(sid, "MISSING", "尚未录入成绩"); continue
        if len(current) != 1:
            incomplete += 1; issue(sid, "DUPLICATE_RECORD", "存在重复学生成绩记录"); continue
        record = current[0]
        flag = str(record.exception_flag or "NORMAL").upper()
        if flag not in _ALLOWED_FLAGS:
            incomplete += 1; issue(sid, "INVALID_EXCEPTION", "异常状态不属于正式枚举"); continue
        if flag != "NORMAL":
            if evidence or any(value is not None for value in (
                    record.usual_score, record.midterm_score, record.final_score,
                    record.total_score, record.pass_status)):
                incomplete += 1; issue(sid, "EXCEPTION_EVIDENCE", "异常状态仍有普通成绩分项或总评")
            else:
                special += 1
            continue
        valid = bool(scheme and scheme.status == "LOCKED" and len(evidence) == len(known)
                     and {row.component_code for row in evidence} == set(known))
        total = 0.0
        for row in evidence:
            item = known.get(row.component_code)
            try:
                value, weight, weighted = float(row.score), float(row.weight), float(row.weighted_score)
                if (not item or not all(math.isfinite(v) for v in (value, weight, weighted)) or not 0 <= value <= 100
                        or value != round(value, 2) or row.grade_record_id != record.id or row.scheme_version != int(scheme.scheme_version if scheme else 0)
                        or row.component_name != item["name"] or abs(weight - item["weight"]) > 0.0001
                        or abs(weighted - round(value * weight / 100, 4)) > 0.0001):
                    valid = False
                total += weighted
            except (TypeError, ValueError, OverflowError):
                valid = False
        if not math.isfinite(total):
            valid = False; total = 0
        total = round(total, 2)
        expected_pass = "PASSED" if total >= float(task.pass_line or 60) else "FAILED"
        if not valid or record.total_score != round(total) or record.pass_status != expected_pass:
            incomplete += 1; issue(sid, "COMPONENT_EVIDENCE", "分项缺失、版本/权重或正式总评不一致"); continue
        if expected_pass == "PASSED":
            passed += 1
        else:
            failed += 1
    outside = sorted((set(records_by_student) | set(scores_by_student)) - ids)
    for sid in outside:
        issue(sid, "OUTSIDE_ROSTER", "存在正式名单外成绩或分项")
    writable, blocked = True, ""
    try:
        guard_term_writable(db, task.term_id)
    except AppException as exc:
        writable, blocked = False, exc.message
    overdue = bool(task.deadline_at and datetime.utcnow() > task.deadline_at)
    ready = bool(ids) and not missing and not incomplete and not outside and bool(scheme and scheme.status == "LOCKED")
    can_submit = ready and task.status in {"INPUTTING", "RETURNED"} and writable and not overdue and not task.publish_at and not any(row.acad_grade_id for row in records)
    return {"gradeTaskId": str(task.id), "taskVersion": int(task.version or 0), "status": task.status,
        "schemeVersion": int(scheme.scheme_version or 1) if scheme else 1,
        "rosterIdentity": roster_identity(roster), "rosterVersionId": str(roster["rosterVersionId"]),
        "rosterHash": roster["rosterHash"], "rosterSource": roster.get("source"),
        "ready": ready, "canSubmit": bool(can_submit), "readOnly": task.status not in _EDITABLE or not writable or overdue,
        "termWritable": writable, "isOverdue": overdue,
        "summary": ("正式动态成绩已录全，可提交学院审核" if can_submit else blocked or
                    ("录分截止时间已过" if overdue else "当前状态或动态分项证据不满足提交条件")),
        "rosterCount": len(ids), "recordedCount": len(records), "missingCount": missing,
        "incompleteCount": incomplete, "outsideRosterCount": len(outside), "specialCount": special,
        "passCount": passed, "failCount": failed, "issues": issues[:100]}


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
