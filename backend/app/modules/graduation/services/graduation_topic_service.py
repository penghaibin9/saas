"""毕业设计中心 · 题目库服务（生产级，DB_ENABLED=true 走本模块）。

题目主数据：申报 → 提交审核 → 入池(APPROVED/CONFIRMED) → 分配给学生（selected 由毕设学生服务维护）。
租户隔离 + 软删 + 审计 t_gd_audit_trail(biz_type=TOPIC)。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission
from app.models import GraduationAuditTrail, GraduationBatch, GraduationStudent, GraduationTopic
from app.services import excel
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_export_security import sanitize_xlsx_export

SOURCE_LABEL = {"TEACHER": "教师申报", "ENTERPRISE": "企业题目", "STUDENT": "学生自拟", "ADMIN": "管理员录入"}
REVIEW_LABEL = {"DRAFT": "草稿", "PENDING_REVIEW": "待审核", "APPROVED": "已通过", "REJECTED": "已驳回"}
REVIEW_TONE = {"DRAFT": "default", "PENDING_REVIEW": "warning", "APPROVED": "success", "REJECTED": "danger"}
STATUS_LABEL = {"PENDING_CONFIRM": "待确认", "CONFIRMED": "已入池", "DISABLED": "已停用", "ARCHIVED": "已归档"}
STATUS_TONE = {"PENDING_CONFIRM": "warning", "CONFIRMED": "success", "DISABLED": "danger", "ARCHIVED": "default"}
VALID_SOURCE = frozenset(SOURCE_LABEL)
VALID_REVIEW = frozenset(REVIEW_LABEL)
SOURCE_IMPORT = ["教师申报", "企业题目", "学生自拟", "管理员录入"]
SOURCE_REVERSE = {v: k for k, v in SOURCE_LABEL.items()}
DIFF_IMPORT = ["较易", "中等", "较难"]
DIFF_REVERSE = {"较易": "EASY", "中等": "MEDIUM", "较难": "HARD"}
DIFF_LABEL = {"EASY": "较易", "MEDIUM": "中等", "HARD": "较难"}
SUBMIT_IMPORT = ["是", "否"]


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or ""


def _audit(db, tid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="TOPIC", biz_id=str(tid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before,
                                after_val=after, occurred_at=datetime.now(timezone.utc)))


def _get(db, tid) -> GraduationTopic:
    t = db.get(GraduationTopic, int(tid))
    if not t or t.is_deleted or t.tenant_id != _tid():
        raise not_found("题目不存在或不在当前数据范围内")
    return t


def _source_label(st: str | None) -> str:
    return SOURCE_LABEL.get(st or "TEACHER", st or "教师申报")


def _is_full(t: GraduationTopic) -> bool:
    return int(t.selected or 0) >= int(t.capacity or 1)


def _row(t: GraduationTopic, batch: GraduationBatch | None = None, *, student_names: list | None = None) -> dict:
    remaining = max(0, int(t.capacity or 1) - int(t.selected or 0))
    return {
        "id": str(t.id), "batchId": str(t.batch_id) if t.batch_id else "",
        "batchName": batch.batch_name if batch else "",
        "topicNo": t.topic_no or "", "title": t.title,
        "sourceType": t.source_type or "TEACHER",
        "source": t.source or _source_label(t.source_type),
        "sourceLabel": _source_label(t.source_type),
        "advisorName": t.advisor_name or "", "collegeId": t.college_id or "",
        "majorId": t.major_id or "", "majorName": t.major_name or "",
        "category": t.category or "", "difficulty": t.difficulty or "",
        "enterpriseName": t.enterprise_name or "",
        "requirements": t.requirements or "", "outcome": t.outcome or "", "skills": t.skills or "",
        "attachments": t.attachments_json or [],
        "capacity": t.capacity, "selected": t.selected, "remaining": remaining,
        "isFull": _is_full(t),
        "reviewStatus": t.review_status, "reviewLabel": REVIEW_LABEL.get(t.review_status, t.review_status),
        "reviewTone": REVIEW_TONE.get(t.review_status, "default"),
        "reviewComment": t.review_comment or "",
        "status": t.status, "statusLabel": STATUS_LABEL.get(t.status, t.status),
        "statusTone": STATUS_TONE.get(t.status, "default"),
        "students": t.students_json or [],
        "disabledNote": t.disabled_note or "", "archiveReason": t.archive_reason or "",
        "archivedAt": _iso(t.archived_at) if t.archived_at else "",
        "updatedAt": _iso(t.updated_at),
        "assignable": (t.review_status == "APPROVED" and t.status == "CONFIRMED"
                       and not _is_full(t)),
        "studentNames": student_names or [],
        "attachmentCount": len(t.attachments_json or []),
        "hasRequirements": bool((t.requirements or "").strip()),
        "hasAttachments": bool(t.attachments_json),
    }


def _row_of(db, t: GraduationTopic) -> dict:
    batch = db.get(GraduationBatch, t.batch_id) if t.batch_id else None
    return _row(t, batch if batch and not batch.is_deleted else None)


def _apply_body(t: GraduationTopic, body: dict, *, create: bool = False) -> None:
    if "title" in body and body["title"] is not None:
        t.title = body["title"].strip()
    if "batchId" in body:
        t.batch_id = int(body["batchId"]) if body.get("batchId") else None
    if "topicNo" in body:
        t.topic_no = (body.get("topicNo") or "").strip() or None
    if create and body.get("sourceType"):
        st = body["sourceType"]
        if st not in VALID_SOURCE:
            raise AppException("VALIDATION_ERROR", "非法题目来源类型")
        t.source_type = st
        t.source = _source_label(st)
    for k, attr in [("advisorName", "advisor_name"), ("collegeId", "college_id"), ("majorId", "major_id"),
                    ("majorName", "major_name"), ("category", "category"), ("difficulty", "difficulty"),
                    ("enterpriseName", "enterprise_name"), ("requirements", "requirements"),
                    ("outcome", "outcome"), ("skills", "skills")]:
        if k in body:
            setattr(t, attr, (body.get(k) or "").strip() or None)
    if "capacity" in body and body["capacity"] is not None:
        cap = int(body["capacity"])
        if cap < int(t.selected or 0):
            raise AppException("DATA_CONFLICT", f"容量不能小于已选人数（{t.selected}）")
        t.capacity = cap
    if "attachments" in body and body["attachments"] is not None:
        t.attachments_json = body["attachments"]


def _ensure_editable(t: GraduationTopic) -> None:
    if t.status == "ARCHIVED":
        raise AppException("DATA_CONFLICT", "已归档题目不可编辑")
    if t.review_status == "PENDING_REVIEW":
        raise AppException("DATA_CONFLICT", "待审核题目不可编辑，请先撤回或等待审核")
    if t.review_status == "APPROVED" and int(t.selected or 0) > 0:
        raise AppException("DATA_CONFLICT", "已有学生选题，请走题目变更流程（后续版本）")


# ═══════════ 列表 / 详情 ═══════════

def list_topics(page: int, page_size: int, keyword=None, batch_id=None, source_type=None,
                category=None, review_status=None, status=None, is_full=None,
                archive_view=None, has_requirements=None, has_attachments=None,
                missing_category=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(GraduationTopic).where(GraduationTopic.tenant_id == _tid(),
                                          GraduationTopic.is_deleted.is_(False))
        if batch_id:
            q = q.where(GraduationTopic.batch_id == int(batch_id))
        if source_type:
            q = q.where(GraduationTopic.source_type == source_type)
        if category:
            q = q.where(GraduationTopic.category == category)
        if review_status:
            q = q.where(GraduationTopic.review_status == review_status)
        if status:
            q = q.where(GraduationTopic.status == status)
        if archive_view == "archived":
            q = q.where(GraduationTopic.status == "ARCHIVED")
        elif archive_view == "active":
            q = q.where(GraduationTopic.status != "ARCHIVED")
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.where(or_(GraduationTopic.title.like(like),
                            GraduationTopic.topic_no.like(like),
                            GraduationTopic.advisor_name.like(like)))
        rows = db.scalars(q.order_by(GraduationTopic.id.desc())).all()
        batches = {b.id: b for b in db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).all()}
        topic_ids = [t.id for t in rows]
        names_map: dict[int, list[str]] = {}
        if topic_ids:
            for s in db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.topic_id.in_(topic_ids),
                GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE")).all():
                names_map.setdefault(int(s.topic_id), []).append(s.name)
        items = []
        for t in rows:
            if is_full is True and not _is_full(t):
                continue
            if is_full is False and _is_full(t):
                continue
            if has_requirements is True and not (t.requirements or "").strip():
                continue
            if has_requirements is False and (t.requirements or "").strip():
                continue
            if has_attachments is True and not (t.attachments_json or []):
                continue
            if has_attachments is False and (t.attachments_json or []):
                continue
            if missing_category and (t.category or "").strip():
                continue
            items.append(_row(t, batches.get(t.batch_id), student_names=names_map.get(int(t.id), [])))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_topic(tid) -> dict:
    with session() as db:
        t = _get(db, tid)
        batch = db.get(GraduationBatch, t.batch_id) if t.batch_id else None
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.topic_id == t.id,
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE")).all()
        assigned = [{"id": str(s.id), "name": s.name, "studentNo": s.student_no or "",
                       "className": s.class_name or "", "stage": s.stage} for s in students]
        logs = db.scalars(select(GraduationAuditTrail).where(
            GraduationAuditTrail.tenant_id == _tid(), GraduationAuditTrail.biz_type == "TOPIC",
            GraduationAuditTrail.biz_id == str(t.id)).order_by(
            GraduationAuditTrail.id.desc()).limit(30)).all()
        base = _row(t, batch if batch and not batch.is_deleted else None)
        return {
            **base,
            "assignedStudents": assigned,
            "auditTrail": [{"action": x.action, "operator": x.operator or "系统",
                            "occurredAt": _iso(x.occurred_at), "detail": x.detail or ""} for x in logs],
        }


def list_assigned_students(tid) -> list[dict]:
    with session() as db:
        _get(db, tid)
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.topic_id == int(tid),
            GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE")).all()
        return [{"id": str(s.id), "name": s.name, "studentNo": s.student_no or "",
                 "className": s.class_name or "", "stage": s.stage} for s in students]


# ═══════════ 写操作 ═══════════

def create_topic(body) -> dict:
    data = body.model_dump() if hasattr(body, "model_dump") else dict(body)
    st = data.get("sourceType") or "TEACHER"
    if st not in VALID_SOURCE:
        raise AppException("VALIDATION_ERROR", "非法题目来源类型")
    with session() as db:
        if data.get("batchId"):
            b = db.get(GraduationBatch, int(data["batchId"]))
            if not b or b.is_deleted or b.tenant_id != _tid():
                raise not_found("毕设批次不存在")
        t = GraduationTopic(
            tenant_id=_tid(), title=data["title"].strip(), source_type=st,
            source=_source_label(st), review_status="DRAFT", status="PENDING_CONFIRM",
            capacity=int(data.get("capacity") or 1), selected=0)
        _apply_body(t, data, create=True)
        if st == "TEACHER":
            from app.modules.graduation.services import graduation_identity as gid
            owner = gid.current_user_mentor(db)
            if owner:
                t.advisor_mentor_id = int(owner.id)
                t.advisor_name = owner.teacher_name
        db.add(t)
        db.flush()
        _audit(db, t.id, "CREATE", t.title)
        if data.get("submitReview"):
            t.review_status = "PENDING_REVIEW"
            _audit(db, t.id, "SUBMIT_REVIEW", "创建并提交审核")
        db.commit()
        return _row_of(db, t)


def update_topic(tid, body) -> dict:
    data = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else dict(body)
    with session() as db:
        t = _get(db, tid)
        _ensure_editable(t)
        if data.get("batchId"):
            b = db.get(GraduationBatch, int(data["batchId"]))
            if not b or b.is_deleted or b.tenant_id != _tid():
                raise not_found("毕设批次不存在")
        before = t.title
        _apply_body(t, data)
        t.version += 1
        _audit(db, t.id, "UPDATE", t.title, before, t.title)
        db.commit()
        return _row_of(db, t)


def submit_review(tid) -> dict:
    with session() as db:
        t = _get(db, tid)
        if t.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档不可提交审核")
        if t.review_status not in ("DRAFT", "REJECTED"):
            raise AppException("DATA_CONFLICT", "仅草稿或已驳回题目可提交审核")
        before = t.review_status
        t.review_status = "PENDING_REVIEW"
        t.review_comment = None
        _audit(db, t.id, "SUBMIT_REVIEW", "", before, "PENDING_REVIEW")
        db.commit()
        return _row_of(db, t)


def review_topic(tid, action: str, comment: str = "") -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        t = _get(db, tid)
        if t.review_status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核题目可审核")
        before = t.review_status
        if action == "APPROVE":
            t.review_status = "APPROVED"
            t.status = "CONFIRMED"
            t.review_comment = (comment or "").strip() or None
            _audit(db, t.id, "APPROVE", comment or "审核通过", before, "APPROVED")
        else:
            t.review_status = "REJECTED"
            t.status = "PENDING_CONFIRM"
            t.review_comment = comment.strip()
            _audit(db, t.id, "REJECT", comment, before, "REJECTED")
        db.commit()
        return _row_of(db, t)


def disable_topic(tid, reason: str) -> dict:
    with session() as db:
        t = _get(db, tid)
        if t.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档不可停用")
        before = t.status
        t.status = "DISABLED"
        t.disabled_note = reason.strip()
        _audit(db, t.id, "DISABLE", reason, before, "DISABLED")
        db.commit()
        return _row_of(db, t)


def enable_topic(tid, reason: str = "") -> dict:
    with session() as db:
        t = _get(db, tid)
        if t.status != "DISABLED":
            raise AppException("DATA_CONFLICT", "仅已停用题目可启用")
        before = t.status
        t.status = "CONFIRMED" if t.review_status == "APPROVED" else "PENDING_CONFIRM"
        t.disabled_note = None
        _audit(db, t.id, "ENABLE", reason or "重新启用", before, t.status)
        db.commit()
        return _row_of(db, t)


def archive_topic(tid, reason: str = "") -> dict:
    with session() as db:
        t = _get(db, tid)
        if t.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档")
        if int(t.selected or 0) > 0:
            raise AppException("DATA_CONFLICT", "仍有学生关联此题，请先退选后再归档")
        before = t.status
        t.status = "ARCHIVED"
        t.archive_reason = (reason or "").strip() or None
        t.archived_at = datetime.now(timezone.utc)
        _audit(db, t.id, "ARCHIVE", reason or "归档", before, "ARCHIVED")
        db.commit()
        return _row_of(db, t)


def topic_stats(batch_id=None) -> dict:
    with session() as db:
        base = [GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False)]
        if batch_id is not None and batch_id != "":
            base.append(GraduationTopic.batch_id == int(batch_id))
        active = base + [GraduationTopic.status != "ARCHIVED"]
        rows = db.scalars(select(GraduationTopic).where(*active)).all()
        total = len(rows)
        pending = sum(1 for t in rows if t.review_status == "PENDING_REVIEW")
        in_pool = sum(1 for t in rows if t.review_status == "APPROVED" and t.status == "CONFIRMED")
        full = sum(1 for t in rows if _is_full(t))
        avail = sum(1 for t in rows if t.review_status == "APPROVED" and t.status == "CONFIRMED" and not _is_full(t))
        req_gap = sum(1 for t in rows if not (t.requirements or "").strip())
        att_gap = sum(1 for t in rows if not (t.attachments_json or []))
        uncat = sum(1 for t in rows if not (t.category or "").strip())
        cat_map: dict[str, dict] = {}
        for t in rows:
            key = (t.category or "").strip() or "未分类"
            bucket = cat_map.setdefault(key, {"category": key, "count": 0, "inPool": 0, "full": 0})
            bucket["count"] += 1
            if t.review_status == "APPROVED" and t.status == "CONFIRMED":
                bucket["inPool"] += 1
            if _is_full(t):
                bucket["full"] += 1
        return {
            "total": total, "pendingReview": pending, "inPool": in_pool,
            "fullCount": full, "availableCount": avail,
            "requirementsGap": req_gap, "attachmentsGap": att_gap, "uncategorized": uncat,
            "categoryStats": sorted(cat_map.values(), key=lambda x: -x["count"]),
            "batchId": str(batch_id) if batch_id else None,
        }


def category_stats(batch_id=None) -> list[dict]:
    return topic_stats(batch_id=batch_id).get("categoryStats", [])


def list_topic_history(page: int, page_size: int, keyword=None, topic_id=None, action=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(GraduationAuditTrail).where(
            GraduationAuditTrail.tenant_id == _tid(), GraduationAuditTrail.biz_type == "TOPIC")
        if topic_id:
            q = q.where(GraduationAuditTrail.biz_id == str(topic_id))
        if action:
            q = q.where(GraduationAuditTrail.action == action)
        logs = db.scalars(q.order_by(GraduationAuditTrail.occurred_at.desc())).all()
        topic_ids = {int(x.biz_id) for x in logs if x.biz_id and str(x.biz_id).isdigit()}
        titles = {}
        if topic_ids:
            for t in db.scalars(select(GraduationTopic).where(GraduationTopic.id.in_(topic_ids))).all():
                titles[int(t.id)] = t.title
        items = []
        for x in logs:
            tid = int(x.biz_id) if x.biz_id and str(x.biz_id).isdigit() else None
            title = titles.get(tid, "") if tid else ""
            if keyword:
                kw = keyword.strip()
                if kw not in title and kw not in (x.action or "") and kw not in (x.detail or ""):
                    continue
            items.append({
                "id": str(x.id), "topicId": x.biz_id or "", "topicTitle": title,
                "action": x.action or "", "operator": x.operator or "系统",
                "roleName": x.role_name or "", "detail": x.detail or "",
                "beforeVal": x.before_val or "", "afterVal": x.after_val or "",
                "occurredAt": _iso(x.occurred_at),
            })
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def build_history_export_spec() -> excel.ExportSpec:
    C = excel.ColumnSpec
    return excel.ExportSpec(
        module_key="graduationDesign", biz_type="gd-topic-history", sheet_title="题目操作历史",
        file_name="题目操作历史.xlsx",
        columns=[
            C("occurredAt", "操作时间"),
            C("action", "操作类型"),
            C("topicTitle", "题目名称"),
            C("topicId", "题目ID"),
            C("operator", "操作人"),
            C("roleName", "角色"),
            C("detail", "详情"),
            C("beforeVal", "变更前"),
            C("afterVal", "变更后"),
        ],
    )


@sanitize_xlsx_export
def export_topic_history_xlsx(keyword=None, topic_id=None, action=None) -> dict:
    items, _ = list_topic_history(1, 100000, keyword=keyword, topic_id=topic_id, action=action)
    user = get_current_user_ctx() or {}
    return excel.build_export(build_history_export_spec(), items, operator_name=user.get("realName") or "系统")


def update_attachments(tid, attachments: list[dict]) -> dict:
    with session() as db:
        t = _get(db, tid)
        if t.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档题目不可改附件")
        before = len(t.attachments_json or [])
        t.attachments_json = attachments or []
        t.version += 1
        _audit(db, t.id, "UPDATE_ATTACHMENTS", f"{before}→{len(t.attachments_json)}", str(before), str(len(t.attachments_json)))
        db.commit()
        return _row_of(db, t)


def update_capacity(tid, capacity: int) -> dict:
    return update_topic(tid, {"capacity": capacity})


def is_assignable(topic_id: int) -> bool:
    """供毕设学生 assign_topic 校验。"""
    with session() as db:
        t = db.get(GraduationTopic, topic_id)
        if not t or t.is_deleted or t.tenant_id != _tid():
            return False
        return (t.review_status == "APPROVED" and t.status == "CONFIRMED"
                and not _is_full(t))


# ═══════════ 导入 / 导出（公共 Excel 底座）═══════════

def _batches_by_no(db) -> dict[str, GraduationBatch]:
    return {b.batch_no: b for b in db.scalars(select(GraduationBatch).where(
        GraduationBatch.tenant_id == _tid(), GraduationBatch.is_deleted.is_(False))).all()}


def _import_transform(row: dict) -> dict:
    src = (row.get("sourceType") or "教师申报").strip()
    st = SOURCE_REVERSE.get(src, src)
    diff = (row.get("difficulty") or "").strip()
    dr = DIFF_REVERSE.get(diff, diff or None)
    sub = (row.get("submitReview") or "否").strip()
    cap_raw = (row.get("capacity") or "1").strip()
    return {
        **row,
        "sourceType": st if st in VALID_SOURCE else "TEACHER",
        "difficulty": dr if dr in DIFF_REVERSE.values() else None,
        "submitReview": sub in ("是", "Y", "1", "true", "True"),
        "capacity": int(cap_raw) if cap_raw.isdigit() else 1,
    }


def _import_business_validate(row: dict, row_no: int) -> str | None:
    src = (row.get("sourceType") or "").strip()
    if src == "企业题目" and not (row.get("enterpriseName") or "").strip():
        return "来源为「企业题目」时，企业名称必填"
    cap = (row.get("capacity") or "").strip()
    if cap:
        try:
            n = int(cap)
            if n < 1 or n > 99:
                return "容量须在 1~99"
        except ValueError:
            return "容量须为整数"
    batch_no = (row.get("batchNo") or "").strip()
    if batch_no:
        with session() as db:
            batches = _batches_by_no(db)
            if batch_no not in batches:
                return f"毕设批次编号不存在：{batch_no}"
            if batches[batch_no].status in ("ARCHIVED", "VOIDED"):
                return "批次已归档/作废，不可导入题目"
    return None


def _import_dup_check(rows: list[dict]) -> dict[int, str]:
    out: dict[int, str] = {}
    seen_no: set[str] = set()
    seen_combo: set[tuple] = set()
    with session() as db:
        topics = db.scalars(select(GraduationTopic).where(
            GraduationTopic.tenant_id == _tid(), GraduationTopic.is_deleted.is_(False))).all()
        existing_nos = {t.topic_no for t in topics if t.topic_no}
        existing_combo = {(t.title, t.advisor_name or "", t.batch_id) for t in topics}
        batches = _batches_by_no(db)
        for i, r in enumerate(rows or []):
            row_no = i + 1
            tno = (r.get("topicNo") or "").strip()
            if tno:
                if tno in seen_no:
                    out[row_no] = f"文件内题目编号重复：{tno}"
                    continue
                seen_no.add(tno)
                if tno in existing_nos:
                    out[row_no] = f"题目编号已存在：{tno}"
                    continue
            title = (r.get("title") or "").strip()
            advisor = (r.get("advisorName") or "").strip()
            batch_no = (r.get("batchNo") or "").strip()
            batch_id = batches[batch_no].id if batch_no in batches else None
            combo = (title, advisor, batch_id)
            if title:
                if combo in seen_combo:
                    out[row_no] = "文件内重复：同题目名称+导师+批次"
                    continue
                seen_combo.add(combo)
                if combo in existing_combo:
                    out[row_no] = "库内已有相同题目（名称+导师+批次）"
    return out


def _persist_import_topics(rows: list[dict]) -> dict:
    with session() as db:
        batches = _batches_by_no(db)
        created = 0
        for r in rows or []:
            st = r.get("sourceType") or "TEACHER"
            batch_no = (r.get("batchNo") or "").strip()
            batch_id = batches[batch_no].id if batch_no in batches else None
            t = GraduationTopic(
                tenant_id=_tid(), title=r["title"].strip(), source_type=st,
                source=_source_label(st), review_status="DRAFT", status="PENDING_CONFIRM",
                capacity=int(r.get("capacity") or 1), selected=0)
            _apply_body(t, {
                "batchId": batch_id, "topicNo": r.get("topicNo"), "advisorName": r.get("advisorName"),
                "majorName": r.get("majorName"), "category": r.get("category"),
                "difficulty": r.get("difficulty"), "enterpriseName": r.get("enterpriseName"),
                "requirements": r.get("requirements"), "outcome": r.get("outcome"),
                "skills": r.get("skills"), "capacity": int(r.get("capacity") or 1),
            }, create=True)
            db.add(t)
            db.flush()
            _audit(db, t.id, "IMPORT", t.title)
            if r.get("submitReview"):
                t.review_status = "PENDING_REVIEW"
                _audit(db, t.id, "SUBMIT_REVIEW", "导入并提交审核")
            created += 1
        job = excel.job_service.add_import_job(
            db, "graduationDesign", "gd-topic", created=created,
        )
        db.commit()
        return {"created": created, **job}


def build_import_spec() -> excel.ImportSpec:
    C = excel.ColumnSpec
    return excel.ImportSpec(
        module_key="graduationDesign", biz_type="gd-topic", template_name="题目库导入",
        columns=[
            C("title", "题目名称", required=True, max_length=300, example="智慧校园综合管理平台设计与实现"),
            C("batchNo", "批次编号", example="GD-2026-1", help_text="可选；须为毕设批次管理中已存在的编号"),
            C("topicNo", "题目编号", unique_in_file=True, max_length=50, example="T-2026-001"),
            C("sourceType", "题目来源", type="enum", options=SOURCE_IMPORT, example="教师申报"),
            C("advisorName", "指导教师", max_length=50, example="王芳"),
            C("majorName", "专业", max_length=100, example="软件技术"),
            C("category", "分类", example="软件系统"),
            C("difficulty", "难度", type="enum", options=DIFF_IMPORT, example="中等"),
            C("enterpriseName", "企业名称", max_length=200, example="某科技有限公司",
              help_text="来源为「企业题目」时必填"),
            C("capacity", "容量", type="int", example="2", help_text="1~99，默认 1"),
            C("requirements", "题目要求", max_length=2000, example="完成需求分析与系统设计"),
            C("outcome", "预期成果", max_length=2000, example="可运行的系统与论文"),
            C("skills", "技能要求", max_length=500, example="Java/Vue/MySQL"),
            C("submitReview", "提交审核", type="enum", options=SUBMIT_IMPORT, example="否",
              help_text="填「是」则导入后直接进入待审核"),
        ],
        notes=[
            "1. 只导入「导入模板」页；第一行表头请勿改动。",
            "2. 带 * 为必填：题目名称。",
            "3. 题目编号租户内唯一；未填编号时按「名称+导师+批次」查重。",
            "4. 导入后默认草稿；「提交审核」填「是」则进入待审核。",
            "5. 审核通过后方可分配给学生（在毕设学生名单操作）。",
        ],
        duplicate_check=_import_dup_check,
        business_validate=_import_business_validate,
        transform_row=_import_transform,
        persist_rows=_persist_import_topics,
        permission_key="graduationDesign.topic.create",
        audit_action="导入毕设题目",
    )


def build_export_spec() -> excel.ExportSpec:
    C = excel.ColumnSpec
    return excel.ExportSpec(
        module_key="graduationDesign", biz_type="gd-topic", sheet_title="题目库台账",
        file_name="题目库台账.xlsx",
        columns=[
            C("topicNo", "题目编号"),
            C("title", "题目名称"),
            C("batchName", "批次"),
            C("sourceLabel", "来源"),
            C("advisorName", "指导教师"),
            C("majorName", "专业"),
            C("category", "分类"),
            C("difficultyLabel", "难度"),
            C("enterpriseName", "企业名称"),
            C("capacityText", "容量(已选/上限)"),
            C("reviewLabel", "审核状态"),
            C("statusLabel", "题目状态"),
            C("requirements", "题目要求"),
            C("updatedAt", "更新时间"),
        ],
    )


def import_template_bytes() -> bytes:
    return excel.build_template(build_import_spec())


def import_read(content: bytes) -> list[dict]:
    return excel.read_upload(build_import_spec(), content)


def import_errors_pack(rows: list[dict], errors: list[dict]) -> dict:
    return excel.build_error_rows(build_import_spec(), rows, errors)


def import_dry_run(rows: list[dict], evidence: dict | None = None) -> dict:
    return excel.pre_validate(build_import_spec(), rows, evidence)


def import_confirm(rows: list[dict], preview_token: str | None = None) -> dict:
    spec = build_import_spec()
    result = excel.confirm_import(spec, rows, preview_token)
    return {"created": result.get("created", 0), "jobId": result.get("jobId")}


@sanitize_xlsx_export
def export_topics_xlsx(keyword=None, batch_id=None, source_type=None, category=None,
                       review_status=None, status=None, is_full=None, archive_view=None,
                       has_requirements=None, has_attachments=None, missing_category=None) -> dict:
    enforce_permission(get_current_user_ctx() or {}, "graduationDesign.topic.export")
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "导出前必须选择毕业设计批次")
    items, _ = list_topics(1, 100000, keyword=keyword, batch_id=batch_id, source_type=source_type,
                           category=category, review_status=review_status, status=status,
                           is_full=is_full, archive_view=archive_view,
                           has_requirements=has_requirements, has_attachments=has_attachments,
                           missing_category=missing_category)
    export_items = [{
        **it,
        "difficultyLabel": DIFF_LABEL.get(it.get("difficulty") or "", it.get("difficulty") or ""),
        "capacityText": f"{it.get('selected', 0)}/{it.get('capacity', 0)}",
    } for it in items]
    user = get_current_user_ctx() or {}
    return excel.build_export(build_export_spec(), export_items, operator_name=user.get("realName") or "系统")
