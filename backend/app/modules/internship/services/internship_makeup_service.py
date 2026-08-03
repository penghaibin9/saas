"""岗位实习 · 补卡申请工作流（P1-Stage1）。

学生（移动端本人）发起/撤回；指导教师（PC 管理端，owner 校验 + 数据范围）审批/驳回。
状态机：PENDING →(教师) APPROVED/REJECTED；PENDING →(学生) WITHDRAWN。
通过后真实补写一条 RECORDED 打卡留痕（不伪造定位）。全程审计 target_type=MAKEUP。
数据范围/owner：复用 internship_service 的 _current_scope / _rec_in_scope（不另造权限体系）。
补卡证据在提交审计中冻结引用；OUT_OF_RANGE 必须有证据，存在证据时审批人须先查看。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipCheckin, InternshipMakeup,
                        InternshipRecord, StudentProfile)
from app.modules.internship.services.internship_version import extract_expected_version, versioned_update
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}
TYPE_LABEL = {"MISSING": "缺卡补录", "OUT_OF_RANGE": "超范围补录"}
_ALLOWED_TYPES = set(TYPE_LABEL)
_EVIDENCE_ACTIONS = ("APPLY_CONTEXT", "APPLY")


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _actor_id(user) -> str:
    return str((user or {}).get("userId") or (user or {}).get("loginName") or "").strip()


def _trail(db, mid: int, action: str, detail: dict | None = None, operator: str = "系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=mid, target_type="MAKEUP",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, mid) -> InternshipMakeup:
    m = db.get(InternshipMakeup, _as_id(mid))
    if not m or m.is_deleted or m.tenant_id != _tid():
        raise not_found("补卡申请不存在")
    return m


def _student_record(db, user, *, batch_id=None, for_write: bool = False):
    """定位当前学生用户的实习记录（统一解析器，禁止 .first()）。"""
    from app.modules.internship.services.internship_record_resolver import (
        require_active_student_record,
        resolve_optional_student_record,
    )
    sno = (user or {}).get("studentNo")
    if not sno:
        if for_write:
            raise AppException("VALIDATION_ERROR", "学生身份信息缺失")
        return None, None
    if for_write:
        return require_active_student_record(db, user, batch_id=batch_id, student_no=sno)
    rec, stu, _ctx = resolve_optional_student_record(db, user, batch_id=batch_id, student_no=sno)
    return rec, stu


def _validate_evidence_file(file_id) -> str | None:
    fid = str(file_id or "").strip()
    if not fid:
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "补卡证据不存在或无权访问，请重新上传")
    return fid


def _evidence_required(makeup_type: str | None) -> bool:
    return str(makeup_type or "").upper() == "OUT_OF_RANGE"


def _evidence_requirement_label(makeup_type: str | None) -> str:
    return "超范围补卡必须上传现场、考勤或定位佐证" if _evidence_required(makeup_type) else "可选上传考勤或现场佐证"


def _evidence_file_id(db, m: InternshipMakeup) -> str:
    trails = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == "MAKEUP",
        InternshipAuditTrail.target_id == m.id,
        InternshipAuditTrail.action.in_(_EVIDENCE_ACTIONS),
    ).order_by(InternshipAuditTrail.id.desc())).all()
    for trail in trails:
        detail = trail.detail_json or {}
        fid = str(detail.get("evidenceFileId") or detail.get("fileId") or "").strip()
        if fid:
            return fid
    return ""


def _previous_rejection(db, m: InternshipMakeup):
    return db.scalars(select(InternshipMakeup).where(
        InternshipMakeup.tenant_id == _tid(),
        InternshipMakeup.internship_id == m.internship_id,
        InternshipMakeup.checkin_date == m.checkin_date,
        InternshipMakeup.makeup_type == m.makeup_type,
        InternshipMakeup.status == "REJECTED",
        InternshipMakeup.id != m.id,
        InternshipMakeup.is_deleted.is_(False),
    ).order_by(InternshipMakeup.id.desc())).first()


def _evidence_viewed(db, m: InternshipMakeup, user, evidence_file_id: str | None = None) -> bool:
    fid = str(evidence_file_id or _evidence_file_id(db, m) or "").strip()
    if not fid:
        return False
    actor_id = _actor_id(user)
    operator = _op_name(user)
    trails = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(),
        InternshipAuditTrail.target_type == "MAKEUP",
        InternshipAuditTrail.target_id == m.id,
        InternshipAuditTrail.action == "EVIDENCE_VIEW",
    ).order_by(InternshipAuditTrail.id.desc())).all()
    for trail in trails:
        detail = trail.detail_json or {}
        try:
            same_version = int(detail.get("version")) == int(m.version or 0)
        except (TypeError, ValueError):
            same_version = False
        same_file = str(detail.get("evidenceFileId") or "") == fid
        same_actor = (actor_id and str(detail.get("operatorUserId") or "") == actor_id)
        if not actor_id:
            same_actor = (trail.operator_name or "") == operator
        if same_version and same_file and same_actor:
            return True
    return False


def _row(m: InternshipMakeup, rec, stu, *, db=None, user=None,
         evidence_file_id=None, previous=None, evidence_viewed=None,
         preloaded: bool = False) -> dict:
    if not preloaded:
        evidence_file_id = _evidence_file_id(db, m) if db is not None else ""
        previous = _previous_rejection(db, m) if db is not None else None
        evidence_viewed = (
            _evidence_viewed(db, m, user, evidence_file_id)
            if db is not None and user else False)
    evidence_file_id = str(evidence_file_id or "")
    return {
        "id": str(m.id), "internId": str(m.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "checkinDate": m.checkin_date,
        "makeupType": m.makeup_type, "makeupTypeLabel": TYPE_LABEL.get(m.makeup_type, m.makeup_type),
        "reason": m.reason, "status": m.status, "statusLabel": STATUS_LABEL.get(m.status, m.status),
        "applyBy": m.apply_by_name or "", "reviewBy": m.review_by_name or "",
        "reviewComment": m.review_comment or "", "reviewAt": _iso(m.review_at) or "",
        "version": int(m.version or 0),
        "createdAt": _iso(m.created_at) or "", "submittedAt": _iso(m.created_at) or "",
        "evidenceFileId": evidence_file_id, "hasEvidence": bool(evidence_file_id),
        "evidenceRequired": _evidence_required(m.makeup_type),
        "evidenceRequirementLabel": _evidence_requirement_label(m.makeup_type),
        "evidenceViewed": bool(evidence_viewed),
        "previousReviewComment": previous.review_comment or "" if previous else "",
        "previousReviewAt": _iso(previous.review_at) or "" if previous else "",
    }


def my_makeups(user) -> dict:
    """本人补卡申请列表。"""
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return {"items": [], "total": 0}
        rows = db.scalars(select(InternshipMakeup).where(
            InternshipMakeup.tenant_id == _tid(), InternshipMakeup.is_deleted.is_(False),
            InternshipMakeup.internship_id == rec.id).order_by(InternshipMakeup.id.desc())).all()
        return {"items": [_row(m, rec, stu, db=db, user=user) for m in rows], "total": len(rows)}


def apply(user, checkin_date: str = "", reason: str = "", makeup_type: str = "MISSING",
          internship_id=None, evidence_file_id=None) -> dict:
    makeup_type = str(makeup_type or "MISSING").upper()
    if makeup_type not in _ALLOWED_TYPES:
        raise AppException("VALIDATION_ERROR", "补卡类型无效")
    if not (checkin_date or "").strip() or not (reason or "").strip() or len(reason.strip()) < 2:
        raise AppException("VALIDATION_ERROR", "补卡日期与事由必填（事由不少于 2 字）")
    evidence_file_id = _validate_evidence_file(evidence_file_id)
    if _evidence_required(makeup_type) and not evidence_file_id:
        raise AppException("VALIDATION_ERROR", _evidence_requirement_label(makeup_type))
    with session() as db:
        rec, stu = _student_record(db, user, for_write=True)
        if internship_id and str(internship_id) != str(rec.id):
            raise no_permission("只能对本人实习记录申请补卡")
        dup = db.scalars(select(InternshipMakeup).where(
            InternshipMakeup.tenant_id == _tid(), InternshipMakeup.internship_id == rec.id,
            InternshipMakeup.checkin_date == checkin_date.strip(),
            InternshipMakeup.status == "PENDING", InternshipMakeup.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该日期已有待审核补卡申请")
        m = InternshipMakeup(tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
                             checkin_date=checkin_date.strip(), makeup_type=makeup_type,
                             reason=reason.strip(), status="PENDING",
                             apply_by_name=(stu.real_name if stu else _op_name(user)))
        db.add(m); db.flush()
        if evidence_file_id:
            from app.services import file_service
            file_service.bind_file_biz(evidence_file_id, "INTERNSHIP", str(m.id), user=user, db=db)
        _trail(db, m.id, "APPLY", {
            "date": m.checkin_date, "makeupType": makeup_type,
            "evidenceFileId": evidence_file_id or "",
            "evidenceRequired": _evidence_required(makeup_type),
        }, operator=m.apply_by_name or "学生")
        db.commit()
        return {"id": str(m.id), "status": "PENDING", "statusLabel": "待审核",
                "version": int(m.version or 0), "hasEvidence": bool(evidence_file_id)}


def withdraw(user, makeup_id) -> dict:
    with session() as db:
        m = _get(db, makeup_id)
        rec, _ = _student_record(db, user, for_write=True)
        if not rec or m.internship_id != rec.id:
            raise no_permission("只能撤回本人的补卡申请")
        if m.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        m.status = "WITHDRAWN"
        m.version += 1
        _trail(db, m.id, "WITHDRAW", {}, operator=_op_name(user))
        db.commit()
        return {"id": str(m.id), "status": "WITHDRAWN"}


# ═══════════ 指导教师 / 管理员（PC 管理端，owner + 数据范围） ═══════════

def list_makeups(page, page_size, status=None, batch_id=None, user=None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipMakeup, InternshipRecord, StudentProfile).join(
            InternshipRecord, InternshipRecord.id == InternshipMakeup.internship_id
        ).join(
            StudentProfile, StudentProfile.id == InternshipMakeup.student_id
        ).where(
            InternshipMakeup.tenant_id == _tid(),
            InternshipMakeup.is_deleted.is_(False),
            InternshipMakeup.internship_id.in_(select(scoped.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            query = query.where(InternshipMakeup.status == status)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipMakeup.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size).limit(size)
        ).all()
        makeups = [item[0] for item in rows]
        ids = [item.id for item in makeups]
        evidence_map = {}
        viewed_ids = set()
        if ids:
            trails = db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == _tid(),
                InternshipAuditTrail.target_type == "MAKEUP",
                InternshipAuditTrail.target_id.in_(ids),
                InternshipAuditTrail.action.in_((*_EVIDENCE_ACTIONS, "EVIDENCE_VIEW")),
            ).order_by(InternshipAuditTrail.id.desc())).all()
            actor_id = _actor_id(user) if user else ""
            operator = _op_name(user) if user else ""
            by_id = {item.id: item for item in makeups}
            for trail in trails:
                detail = trail.detail_json or {}
                if trail.action in _EVIDENCE_ACTIONS:
                    file_id = str(detail.get("evidenceFileId") or detail.get("fileId") or "").strip()
                    if file_id:
                        evidence_map.setdefault(trail.target_id, file_id)
            for trail in trails:
                if trail.action != "EVIDENCE_VIEW" or not user:
                    continue
                makeup = by_id.get(trail.target_id)
                file_id = evidence_map.get(trail.target_id, "")
                if not makeup or not file_id:
                    continue
                detail = trail.detail_json or {}
                try:
                    same_version = int(detail.get("version")) == int(makeup.version or 0)
                except (TypeError, ValueError):
                    same_version = False
                same_file = str(detail.get("evidenceFileId") or "") == file_id
                same_actor = (
                    str(detail.get("operatorUserId") or "") == actor_id
                    if actor_id else (trail.operator_name or "") == operator
                )
                if same_version and same_file and same_actor:
                    viewed_ids.add(makeup.id)
        previous_map = {}
        if makeups:
            internship_ids = {item.internship_id for item in makeups}
            rejected = db.scalars(select(InternshipMakeup).where(
                InternshipMakeup.tenant_id == _tid(),
                InternshipMakeup.internship_id.in_(internship_ids),
                InternshipMakeup.status == "REJECTED",
                InternshipMakeup.is_deleted.is_(False),
            ).order_by(InternshipMakeup.id.desc())).all()
            for item in rejected:
                key = (item.internship_id, item.checkin_date, item.makeup_type)
                previous_map.setdefault(key, item)
        result = []
        for makeup, record, student in rows:
            key = (makeup.internship_id, makeup.checkin_date, makeup.makeup_type)
            previous = previous_map.get(key)
            if previous and previous.id == makeup.id:
                previous = None
            result.append(_row(
                makeup, record, student, db=db, user=user,
                evidence_file_id=evidence_map.get(makeup.id, ""),
                previous=previous, evidence_viewed=makeup.id in viewed_ids,
                preloaded=True,
            ))
        return result, total


def get_makeup(makeup_id, user=None) -> dict:
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    from app.services import file_service
    with session() as db:
        m = _get(db, makeup_id)
        rec = db.get(InternshipRecord, m.internship_id)
        stu = db.get(StudentProfile, m.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("该补卡申请不在你的数据范围内")
        evidence_file_id = _evidence_file_id(db, m)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "MAKEUP",
            InternshipAuditTrail.target_id == m.id).order_by(InternshipAuditTrail.id)).all()
        return {**_row(m, rec, stu, db=db, user=user),
                "attachment": file_service.attachment_view(evidence_file_id),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def mark_evidence_viewed(user, makeup_id) -> dict:
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    from app.services import file_service
    with session() as db:
        m = _get(db, makeup_id)
        rec = db.get(InternshipRecord, m.internship_id)
        stu = db.get(StudentProfile, m.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("该补卡申请不在你的数据范围内")
        evidence_file_id = _evidence_file_id(db, m)
        if not evidence_file_id or not file_service.get_file_meta(evidence_file_id, user=user):
            raise not_found("补卡证据不存在或无权查看")
        _trail(db, m.id, "EVIDENCE_VIEW", {
            "version": int(m.version or 0),
            "evidenceFileId": evidence_file_id,
            "operatorUserId": _actor_id(user),
        }, operator=_op_name(user))
        db.commit()
        return {"id": str(m.id), "version": int(m.version or 0),
                "evidenceViewed": True, "evidenceFileId": evidence_file_id}


def review(user, makeup_id, action: str, comment: str = "", *, expected_version=None,
           expected_batch_id=None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        m = _get(db, makeup_id)
        rec = db.get(InternshipRecord, m.internship_id)
        stu = db.get(StudentProfile, m.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("只能审批本人指导学生的补卡申请")
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_record_batch(rec, expected_batch_id)
        if m.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该申请已处理，请刷新")
        evidence_file_id = _evidence_file_id(db, m)
        if action == "APPROVE":
            if _evidence_required(m.makeup_type) and not evidence_file_id:
                raise AppException("DATA_CONFLICT", "超范围补卡缺少证据材料，不能通过")
            if evidence_file_id and not _evidence_viewed(db, m, user, evidence_file_id):
                raise AppException("DATA_CONFLICT", "请先查看补卡证据材料，再执行通过")
        status = "APPROVED" if action == "APPROVE" else "REJECTED"
        new_ver = versioned_update(
            db, InternshipMakeup, entity_id=m.id, tenant_id=_tid(),
            expected_version=extract_expected_version({"expectedVersion": expected_version}),
            expected_status="PENDING", values={"status": status, "review_by_name": _op_name(user),
                                                "review_at": datetime.utcnow(),
                                                "review_comment": (comment or "").strip() or None})
        if action == "APPROVE":
            exist = db.scalars(select(InternshipCheckin).where(
                InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == rec.id,
                InternshipCheckin.checkin_date == m.checkin_date)).first()
            if not exist:
                db.add(InternshipCheckin(tenant_id=_tid(), internship_id=rec.id,
                                         checkin_date=m.checkin_date, checkin_at=datetime.utcnow(),
                                         result="RECORDED", note=f"补卡通过：{(m.reason or '')[:100]}"))
        _trail(db, m.id, f"REVIEW_{action}", {
            "comment": (comment or "").strip(),
            "evidenceFileId": evidence_file_id,
            "evidenceViewed": bool(evidence_file_id),
        }, operator=_op_name(user))
        db.commit()
        return {"id": str(m.id), "status": status, "statusLabel": STATUS_LABEL[status], "version": new_ver}


def export_makeups(status=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_makeups, status=status, batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "校内指导教师", "补卡日期", "补卡类型", "事由", "证据材料", "状态", "审批人", "审批意见"]
    data_rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["checkinDate"],
                  it["makeupTypeLabel"], it["reason"], "已上传" if it["hasEvidence"] else "未上传",
                  it["statusLabel"], it["reviewBy"], it["reviewComment"]] for it in items]
    wm = (f"岗位实习中心·补卡审批台账 · 导出人：{_op_name(user)} · "
          f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("补卡审批台账", headers, data_rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "补卡审批台账.xlsx", len(items))
