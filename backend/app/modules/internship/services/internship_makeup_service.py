"""岗位实习 · 补卡申请工作流（P1-Stage1）。

学生（移动端本人）发起/撤回；指导教师（PC 管理端，owner 校验 + 数据范围）审批/驳回。
状态机：PENDING →(教师) APPROVED/REJECTED；PENDING →(学生) WITHDRAWN。
通过后真实补写一条 RECORDED 打卡留痕（不伪造定位）。全程审计 target_type=MAKEUP。
数据范围/owner：复用 internship_service 的 _current_scope / _rec_in_scope（不另造权限体系）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipCheckin, InternshipMakeup,
                        InternshipRecord, StudentProfile)
from app.services.db_service import _iso, _tid, session

STATUS_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}
TYPE_LABEL = {"MISSING": "缺卡补录", "OUT_OF_RANGE": "超范围补录"}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, mid: int, action: str, detail: dict | None = None, operator: str = "系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=mid, target_type="MAKEUP",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, mid) -> InternshipMakeup:
    m = db.get(InternshipMakeup, int(mid))
    if not m or m.is_deleted or m.tenant_id != _tid():
        raise not_found("补卡申请不存在")
    return m


def _student_record(db, user):
    """定位当前学生用户的实习记录（严格本人，按 studentNo）。"""
    sno = (user or {}).get("studentNo")
    if not sno:
        return None, None
    stu = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.student_no == sno,
        StudentProfile.is_deleted.is_(False))).first()
    if not stu:
        return None, None
    rec = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
        InternshipRecord.is_deleted.is_(False))).first()
    return rec, stu


def _row(m: InternshipMakeup, rec, stu) -> dict:
    return {
        "id": str(m.id), "internId": str(m.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "checkinDate": m.checkin_date,
        "makeupType": m.makeup_type, "makeupTypeLabel": TYPE_LABEL.get(m.makeup_type, m.makeup_type),
        "reason": m.reason, "status": m.status, "statusLabel": STATUS_LABEL.get(m.status, m.status),
        "applyBy": m.apply_by_name or "", "reviewBy": m.review_by_name or "",
        "reviewComment": m.review_comment or "", "reviewAt": _iso(m.review_at) or "",
        "createdAt": _iso(m.created_at) or "",
    }


# ═══════════ 学生本人（移动端） ═══════════

def apply(user, checkin_date: str = "", reason: str = "", makeup_type: str = "MISSING",
          internship_id=None) -> dict:
    if not (checkin_date or "").strip() or not (reason or "").strip() or len(reason.strip()) < 2:
        raise AppException("VALIDATION_ERROR", "补卡日期与事由必填（事由不少于 2 字）")
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            raise not_found("未找到你的实习记录，无法申请补卡")
        if internship_id and str(internship_id) != str(rec.id):
            raise no_permission("只能对本人实习记录申请补卡")
        dup = db.scalars(select(InternshipMakeup).where(
            InternshipMakeup.tenant_id == _tid(), InternshipMakeup.internship_id == rec.id,
            InternshipMakeup.checkin_date == checkin_date.strip(),
            InternshipMakeup.status == "PENDING", InternshipMakeup.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该日期已有待审核补卡申请")
        m = InternshipMakeup(tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
                             checkin_date=checkin_date.strip(), makeup_type=makeup_type or "MISSING",
                             reason=reason.strip(), status="PENDING",
                             apply_by_name=(stu.real_name if stu else _op_name(user)))
        db.add(m); db.flush()
        _trail(db, m.id, "APPLY", {"date": m.checkin_date}, operator=m.apply_by_name or "学生")
        db.commit()
        return {"id": str(m.id), "status": "PENDING", "statusLabel": "待审核"}


def withdraw(user, makeup_id) -> dict:
    with session() as db:
        m = _get(db, makeup_id)
        rec, _ = _student_record(db, user)
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

def list_makeups(page, page_size, status=None, user=None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        q = select(InternshipMakeup).where(InternshipMakeup.tenant_id == _tid(),
                                           InternshipMakeup.is_deleted.is_(False))
        if status:
            q = q.where(InternshipMakeup.status == status)
        rows = db.scalars(q.order_by(InternshipMakeup.id.desc())).all()
        scope = _current_scope(user)
        items = []
        for m in rows:
            rec = db.get(InternshipRecord, m.internship_id)
            stu = db.get(StudentProfile, m.student_id)
            if not _rec_in_scope(scope, db, rec, stu):  # 数据范围
                continue
            items.append(_row(m, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_makeup(makeup_id, user=None) -> dict:
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        m = _get(db, makeup_id)
        rec = db.get(InternshipRecord, m.internship_id)
        stu = db.get(StudentProfile, m.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):
            raise no_permission("该补卡申请不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "MAKEUP",
            InternshipAuditTrail.target_id == m.id).order_by(InternshipAuditTrail.id)).all()
        return {**_row(m, rec, stu),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def review(user, makeup_id, action: str, comment: str = "") -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and (not comment or len(comment.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    with session() as db:
        m = _get(db, makeup_id)
        rec = db.get(InternshipRecord, m.internship_id)
        stu = db.get(StudentProfile, m.student_id)
        if not _rec_in_scope(_current_scope(user), db, rec, stu):  # owner 级写校验
            raise no_permission("只能审批本人指导学生的补卡申请")
        if m.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该申请已处理，请刷新")
        m.status = "APPROVED" if action == "APPROVE" else "REJECTED"
        m.review_by_name = _op_name(user)
        m.review_at = datetime.utcnow()
        m.review_comment = (comment or "").strip() or None
        m.version += 1
        if action == "APPROVE":  # 真实补写打卡留痕（不伪造定位）
            exist = db.scalars(select(InternshipCheckin).where(
                InternshipCheckin.tenant_id == _tid(), InternshipCheckin.internship_id == rec.id,
                InternshipCheckin.checkin_date == m.checkin_date)).first()
            if not exist:
                db.add(InternshipCheckin(tenant_id=_tid(), internship_id=rec.id,
                                         checkin_date=m.checkin_date, checkin_at=datetime.utcnow(),
                                         result="RECORDED", note=f"补卡通过：{(m.reason or '')[:100]}"))
        _trail(db, m.id, f"REVIEW_{action}", {"comment": (comment or "").strip()},
               operator=_op_name(user))
        db.commit()
        return {"id": str(m.id), "status": m.status, "statusLabel": STATUS_LABEL[m.status]}


def export_makeups(status=None, user=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_makeups(1, 100000, status=status, user=user)
    headers = ["学号", "姓名", "校内指导教师", "补卡日期", "补卡类型", "事由", "状态", "审批人", "审批意见"]
    data_rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["checkinDate"],
                  it["makeupTypeLabel"], it["reason"], it["statusLabel"], it["reviewBy"],
                  it["reviewComment"]] for it in items]
    wm = (f"岗位实习中心·补卡审批台账 · 导出人：{_op_name(user)} · "
          f"{datetime.now():%Y-%m-%d %H:%M} · 导出留痕")
    content = xlsx_util.build_ledger_xlsx("补卡审批台账", headers, data_rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "补卡审批台账.xlsx", len(items))
