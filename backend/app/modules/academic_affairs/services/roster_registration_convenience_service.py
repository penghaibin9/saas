"""D2-U 学籍名册/注册便利性服务。

只提供候选 enrich、批量预览和批量编排；不新增事实表，不直接写学生主档。
最终注册逐项复用 academic_affairs_service.register_student() canonical 写入口。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException, not_found
from app.models import AaRegistrationBatch, Major, SchoolClass, StudentProfile
from app.modules.academic_affairs.services import academic_affairs_service as svc
from app.services.db_service import _tid, session


_MAX_BULK = 100


def _status_label(status: str | None) -> str:
    return svc._STATUS_LABEL.get(status, status or "—")


def _explanation(batch, registration, student) -> str:
    elig = registration.eligibility_status if registration else "PENDING"
    note = ((registration.eligibility_note if registration else "") or "").strip()
    if elig == "INELIGIBLE":
        return note or "资格核验不通过，请先在“注册异常”处理后再注册"
    if elig == "ELIGIBLE":
        return note or "资格核验已通过"
    kind = {"ENROLL": "入学", "ANNUAL": "学年", "SEMESTER": "学期"}.get(batch.register_type, "当前")
    return f"系统已按{kind}注册候选规则圈定；当前学籍状态为{_status_label(student.student_status)}，资格尚待核验"


def _enrich_pairs(db, batch, pairs):
    students = [s for s, _r in pairs]
    class_ids = {int(s.class_id) for s in students if s.class_id}
    major_ids = {int(s.major_id) for s in students if s.major_id}
    classes = {}
    if class_ids:
        classes = {
            c.id: c for c in db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(),
                SchoolClass.id.in_(list(class_ids)),
                SchoolClass.is_deleted.is_(False),
            )).all()
        }
        major_ids.update(int(c.major_id) for c in classes.values() if c.major_id)
    majors = {}
    if major_ids:
        majors = {
            m.id: m for m in db.scalars(select(Major).where(
                Major.tenant_id == _tid(),
                Major.id.in_(list(major_ids)),
                Major.is_deleted.is_(False),
            )).all()
        }

    out = []
    for student, registration in pairs:
        cls = classes.get(student.class_id)
        major_id = student.major_id or (cls.major_id if cls else None)
        major = majors.get(major_id)
        elig = registration.eligibility_status if registration else "PENDING"
        out.append({
            "studentId": str(student.id),
            "studentNo": student.student_no or "",
            "realName": student.real_name or "",
            "className": cls.class_name if cls else "",
            "majorName": major.major_name if major else "",
            "currentStatus": student.student_status or "",
            "currentStatusLabel": _status_label(student.student_status),
            "registrationStatus": registration.status if registration else "PENDING_REGISTER",
            "eligibilityStatus": elig,
            "eligibilityNote": ((registration.eligibility_note if registration else "") or ""),
            "eligibilityExplanation": _explanation(batch, registration, student),
        })
    return out


def list_registration_candidates(batch_id, user, *, status=None, keyword=None, page=1, page_size=20):
    """权威候选 + 人类可读组织/状态。候选/数据范围完全复用现有注册服务真值。"""
    with session() as db:
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("注册批次不存在")
        ctx = build_affairs_context(user, db)
        allowed = ctx.allowed_class_ids(db)
        pairs = svc._batch_pending_candidates(db, batch, allowed)
        filtered = []
        for student, registration in pairs:
            elig = registration.eligibility_status if registration else "PENDING"
            if status and elig != status:
                continue
            if keyword and keyword not in (student.real_name or "") and keyword not in (student.student_no or ""):
                continue
            filtered.append((student, registration))
        total = len(filtered)
        start = (max(1, int(page)) - 1) * max(1, int(page_size))
        page_pairs = filtered[start:start + max(1, int(page_size))]
        return _enrich_pairs(db, batch, page_pairs), total


def _validate_ids(student_ids) -> list[int]:
    ids = []
    seen = set()
    for raw in student_ids or []:
        sid = int(raw)
        if sid in seen:
            continue
        seen.add(sid)
        ids.append(sid)
    if not ids:
        raise AppException("VALIDATION_ERROR", "请至少选择 1 名学生")
    if len(ids) > _MAX_BULK:
        raise AppException("VALIDATION_ERROR", f"单次最多处理 {_MAX_BULK} 名学生")
    return ids


def bulk_register_preview(batch_id, user, student_ids):
    """零写入预览。未知/越权/非候选 studentId 只返回通用 BLOCKED，不泄露他人资料。"""
    ids = _validate_ids(student_ids)
    with session() as db:
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("注册批次不存在")
        ctx = build_affairs_context(user, db)
        allowed = ctx.allowed_class_ids(db)
        pairs = svc._batch_pending_candidates(db, batch, allowed)
        id_set = set(ids)
        selected_pairs = [(s, r) for s, r in pairs if s.id in id_set]
        by_id = {s.id: (s, r) for s, r in selected_pairs}
        enriched = {int(row["studentId"]): row for row in _enrich_pairs(db, batch, selected_pairs)}

        items = []
        ready = 0
        for sid in ids:
            pair = by_id.get(sid)
            if pair is None:
                items.append({
                    "studentId": str(sid), "status": "BLOCKED", "code": "NOT_AVAILABLE",
                    "message": "该学生不在当前可注册候选范围内",
                })
                continue
            _student, registration = pair
            row = enriched[sid]
            if batch.status != "OPEN":
                status, code, message = "BLOCKED", "DATA_CONFLICT", "注册批次未开放或已关闭"
            elif registration and registration.eligibility_status == "INELIGIBLE":
                status, code, message = "BLOCKED", "INELIGIBLE", row["eligibilityExplanation"]
            else:
                status, code, message = "READY", "", "可提交注册；确认时系统会再次执行正式校验"
                ready += 1
            items.append({**row, "status": status, "code": code, "message": message})
        return {
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "batchStatus": batch.status,
            "selected": len(ids),
            "ready": ready,
            "blocked": len(ids) - ready,
            "items": items,
        }


def _final_ready_check(batch_id, user, student_id) -> tuple[bool, str, str]:
    """确认前逐项重检 dataScope + 候选身份 + 显式不合格；只读且按主键定点查询。"""
    from app.models import AaRegistration

    with session() as db:
        batch = db.get(AaRegistrationBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            return False, "NOT_FOUND", "注册批次不存在"
        if batch.status != "OPEN":
            return False, "DATA_CONFLICT", "注册批次未开放或已关闭"
        ctx = build_affairs_context(user, db)
        try:
            student = ctx.require_student(db, int(student_id))
        except AppException:
            # 不向猜 ID 的调用者泄露越权学生是否存在。
            return False, "NOT_AVAILABLE", "该学生不在当前可注册候选范围内"
        if student.student_status not in svc._batch_target_statuses(batch):
            return False, "NOT_AVAILABLE", "该学生不在当前可注册候选范围内"
        registration = db.scalars(select(AaRegistration).where(
            AaRegistration.tenant_id == _tid(),
            AaRegistration.batch_id == batch.id,
            AaRegistration.student_id == int(student_id),
            AaRegistration.is_deleted.is_(False),
        )).first()
        if registration and registration.status == "REGISTERED":
            return False, "DATA_CONFLICT", "该生已在本批次完成注册"
        if registration and registration.eligibility_status == "INELIGIBLE":
            return False, "INELIGIBLE", ((registration.eligibility_note or "").strip()
                                           or "资格核验不通过，请先处理注册异常")
        return True, "", ""


def bulk_register(batch_id, user, student_ids):
    """逐项 canonical apply。业务冲突显式返回逐项结果；未知异常继续抛出。"""
    preview = bulk_register_preview(batch_id, user, student_ids)
    items = []
    for item in preview["items"]:
        sid = int(item["studentId"])
        if item["status"] != "READY":
            items.append({
                "studentId": item["studentId"],
                "ok": False,
                "code": item["code"],
                "message": item["message"],
            })
            continue
        ready, code, message = _final_ready_check(batch_id, user, sid)
        if not ready:
            items.append({
                "studentId": str(sid), "ok": False,
                "code": code, "message": message,
            })
            continue
        try:
            result = svc.register_student(batch_id, user, sid)
        except AppException as exc:
            items.append({
                "studentId": str(sid), "ok": False,
                "code": exc.code, "message": exc.message,
            })
        else:
            items.append({
                "studentId": str(sid), "ok": True, "code": "",
                "message": "注册成功",
                "registrationId": result["registrationId"],
                "studentStatus": result["studentStatus"],
                "changeType": result["changeType"],
            })
    success_count = sum(1 for x in items if x["ok"])
    return {
        "batchId": str(batch_id),
        "selected": len(items),
        "succeeded": success_count,
        "failed": len(items) - success_count,
        "items": items,
    }
