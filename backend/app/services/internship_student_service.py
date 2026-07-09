"""岗位实习中心 · 实习学生服务（生产级，DB_ENABLED=true 走本模块）。

核心：把实习学生记录 t_internship_record 与企业库(t_emp_company)/岗位库(t_internship_position)真实打通——
学生-岗位分配闭环让岗位库 allocated_count 变为真实值，并落地「满员不可再分配 / 黑名单·未上架岗位不可分配」。
再叠加 学生实习状态机 + 实习资格 + 实习去向 + 统计 + 导入导出。
横切：租户隔离 + is_deleted 软删 + 手机号脱敏 + 审计到 t_internship_audit_trail(target_type=INTERN_STUDENT)。
数据范围（预留）：默认按租户；辅导员/指导教师限本班/本人指导，接 resolve_teacher_scope。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (EmpCompany, InternshipAuditTrail, InternshipPosition, InternshipRecord,
                        StudentContact, StudentProfile)
from app.services.db_service import _iso, _mask_phone, _tid, session

STATUS_LABEL = {"PREPARING": "准备中", "READY": "待上岗", "ONBOARD": "在岗中",
                "ASSESSING": "考核中", "ARCHIVED": "已归档"}
STATUS_TONE = {"PREPARING": "default", "READY": "warning", "ONBOARD": "success",
               "ASSESSING": "primary", "ARCHIVED": "default"}
RISK_LABEL = {"NONE": "无", "LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
ELIG_LABEL = {"PENDING": "待认定", "QUALIFIED": "资格合格", "UNQUALIFIED": "资格不合格"}
DEST_LABEL = {"NONE": "未落实", "ASSIGNED": "已分配岗位", "SELF_ARRANGED": "自主实习", "EXEMPTED": "免实习"}


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, rec_id: int, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=rec_id, target_type="INTERN_STUDENT",
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, rec_id) -> InternshipRecord:
    r = db.get(InternshipRecord, int(rec_id))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("实习学生记录不存在或不在当前数据范围内")
    return r


def _students_map(db, ids: list[int]) -> dict:
    if not ids:
        return {}
    rows = db.scalars(select(StudentProfile).where(StudentProfile.id.in_(ids))).all()
    return {s.id: s for s in rows}


def _row(r: InternshipRecord, stu: StudentProfile | None) -> dict:
    return {
        "id": str(r.id), "studentId": str(r.student_id),
        "name": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "className": (stu.grade + "级") if stu and stu.grade else "-",
        "classId": str(stu.class_id) if stu and stu.class_id else "",
        "batchId": str(r.batch_id) if r.batch_id else "",
        "enterpriseId": str(r.enterprise_id) if r.enterprise_id else "",
        "enterpriseName": r.enterprise_name or "",
        "positionId": str(r.position_id) if r.position_id else "",
        "positionName": r.position_name or "",
        "mentorContactId": str(r.mentor_contact_id) if r.mentor_contact_id else "",
        "mentorName": r.enterprise_mentor_name or "", "advisorName": r.advisor_name or "",
        "status": r.status, "statusLabel": STATUS_LABEL.get(r.status, r.status),
        "statusTone": STATUS_TONE.get(r.status, "default"),
        "riskLevel": r.risk_level, "riskLabel": RISK_LABEL.get(r.risk_level, r.risk_level),
        "eligibilityStatus": r.eligibility_status,
        "eligibilityLabel": ELIG_LABEL.get(r.eligibility_status, r.eligibility_status),
        "destinationType": r.destination_type,
        "destinationLabel": DEST_LABEL.get(r.destination_type, r.destination_type),
        "internRange": (f"{_iso(r.intern_start_date)[:10]} ~ {_iso(r.intern_end_date)[:10]}"
                        if r.intern_start_date and r.intern_end_date else ""),
        "updatedAt": _iso(r.updated_at),
    }


def _row_of(db, r: InternshipRecord) -> dict:
    return _row(r, db.get(StudentProfile, r.student_id))


# ═══════════ 列表 / 详情 ═══════════

def list_students(page: int, page_size: int, keyword=None, class_id=None, status=None,
                  risk_level=None, eligibility=None, destination=None,
                  has_position=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(InternshipRecord).where(InternshipRecord.tenant_id == _tid(),
                                           InternshipRecord.is_deleted.is_(False))
        if status:
            q = q.where(InternshipRecord.status == status)
        if risk_level:
            q = q.where(InternshipRecord.risk_level == risk_level)
        if eligibility:
            q = q.where(InternshipRecord.eligibility_status == eligibility)
        if destination:
            q = q.where(InternshipRecord.destination_type == destination)
        if has_position is True:
            q = q.where(InternshipRecord.position_id.is_not(None))
        elif has_position is False:
            q = q.where(InternshipRecord.position_id.is_(None))
        rows = db.scalars(q.order_by(InternshipRecord.id.desc())).all()
        smap = _students_map(db, [r.student_id for r in rows])
        items = []
        for r in rows:
            stu = smap.get(r.student_id)
            if keyword:
                kw = keyword.strip()
                if not stu or (kw not in (stu.real_name or "") and kw not in (stu.student_no or "")):
                    continue
            if class_id and (not stu or str(stu.class_id) != str(class_id)):
                continue
            items.append(_row(r, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_student(rec_id) -> dict:
    """详情：主档 + 企业/岗位/导师关联 + 资格/去向/状态 + 联系电话脱敏 + 审计。"""
    with session() as db:
        r = _get(db, rec_id)
        stu = db.get(StudentProfile, r.student_id)
        phone = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == _tid(), StudentContact.student_id == r.student_id,
            StudentContact.contact_type == "PHONE")).first()
        company = position = None
        if r.enterprise_id:
            c = db.get(EmpCompany, r.enterprise_id)
            if c and not c.is_deleted:
                company = {"id": str(c.id), "name": c.name, "coopStatus": c.coop_status,
                           "blacklist": bool(c.blacklist)}
        if r.position_id:
            p = db.get(InternshipPosition, r.position_id)
            if p and not p.is_deleted:
                position = {"id": str(p.id), "title": p.title, "status": p.status,
                            "workLocation": p.work_location or "",
                            "capacity": f"{p.allocated_count}/{p.headcount}"}
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "INTERN_STUDENT",
            InternshipAuditTrail.target_id == r.id).order_by(
            InternshipAuditTrail.occurred_at.desc()).limit(20)).all()
        return {
            **_row(r, stu),
            "phone": _mask_phone(phone.contact_value_encrypted if phone else None),
            "insurance": r.insurance_info or "", "agreement": r.agreement_info or "",
            "remark": r.remark or "", "company": company, "position": position,
            "auditTrail": [{"action": a.action, "operator": a.operator_name or "",
                            "detail": a.detail_json or {}, "occurredAt": _iso(a.occurred_at)}
                           for a in trail],
        }


# ═══════════ 建档 / 编辑 ═══════════

def create_student_record(body) -> dict:
    with session() as db:
        sid = int(getattr(body, "studentId"))
        stu = db.get(StudentProfile, sid)
        if not stu or stu.is_deleted or stu.tenant_id != _tid():
            raise not_found("学生不存在或不在当前数据范围内")
        batch_id = int(body.batchId) if getattr(body, "batchId", None) else None
        dup = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == sid,
            InternshipRecord.batch_id == batch_id,
            InternshipRecord.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学生在此批次已有实习记录")
        r = InternshipRecord(
            tenant_id=_tid(), student_id=sid, batch_id=batch_id,
            advisor_name=getattr(body, "advisorName", None), remark=getattr(body, "remark", None),
            status="PREPARING", eligibility_status="PENDING", destination_type="NONE", risk_level="NONE")
        db.add(r)
        db.flush()
        _trail(db, r.id, "CREATE", {"studentId": str(sid)})
        db.commit()
        return _row_of(db, r)


def update_student_record(rec_id, body) -> dict:
    with session() as db:
        r = _get(db, rec_id)
        if r.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可编辑")
        for src, col in [("advisorName", "advisor_name"), ("insurance", "insurance_info"),
                         ("agreement", "agreement_info"), ("remark", "remark")]:
            v = getattr(body, src, None)
            if v is not None:
                setattr(r, col, v)
        r.version += 1
        _trail(db, r.id, "UPDATE", {})
        db.commit()
        return _row_of(db, r)


# ═══════════ 学生-岗位分配（岗位库 allocated_count 收口）═══════════

def assign_position(rec_id, position_id) -> dict:
    with session() as db:
        r = _get(db, rec_id)
        if r.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档记录不可分配岗位")
        p = db.get(InternshipPosition, int(position_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("岗位不存在或不在当前数据范围内")
        if r.position_id == p.id:
            raise AppException("DATA_CONFLICT", "该学生已分配到此岗位")
        if p.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", f"仅「已上架」岗位可分配（当前：{p.status}）")
        c = db.get(EmpCompany, p.company_id)
        if not c or c.is_deleted:
            raise not_found("岗位所属企业不存在")
        if c.blacklist or c.coop_status == "BLACKLIST":
            raise AppException("DATA_CONFLICT", "黑名单企业岗位不可分配学生")
        if p.allocated_count >= p.headcount:
            raise AppException("DATA_CONFLICT", "该岗位已满员，不能再分配")
        # 调岗：释放旧岗位名额
        if r.position_id:
            old = db.get(InternshipPosition, r.position_id)
            if old and old.allocated_count > 0:
                old.allocated_count -= 1
                if old.status == "FULL" and old.allocated_count < old.headcount:
                    old.status = "PUBLISHED"
        # 回填关联 + 占用新岗位名额
        r.position_id = p.id
        r.enterprise_id = c.id
        r.mentor_contact_id = p.mentor_contact_id
        r.position_name = p.title
        r.enterprise_name = c.name
        r.enterprise_mentor_name = p.mentor_name
        r.destination_type = "ASSIGNED"
        p.allocated_count += 1
        if p.allocated_count >= p.headcount:
            p.status = "FULL"
        _trail(db, r.id, "ASSIGN_POSITION", {"positionId": str(p.id), "title": p.title})
        db.commit()
        return _row_of(db, r)


def unassign_position(rec_id, reason: str = "") -> dict:
    with session() as db:
        r = _get(db, rec_id)
        if not r.position_id:
            raise AppException("DATA_CONFLICT", "该学生未分配岗位")
        p = db.get(InternshipPosition, r.position_id)
        if p and p.allocated_count > 0:
            p.allocated_count -= 1
            if p.status == "FULL" and p.allocated_count < p.headcount:
                p.status = "PUBLISHED"
        r.position_id = None
        r.enterprise_id = None
        r.mentor_contact_id = None
        r.position_name = None
        r.enterprise_name = None
        r.enterprise_mentor_name = None
        r.destination_type = "NONE"
        _trail(db, r.id, "UNASSIGN_POSITION", {"reason": reason})
        db.commit()
        return _row_of(db, r)


# ═══════════ 状态机 / 资格 / 去向 ═══════════

def set_status(rec_id, action: str, reason: str = "") -> dict:
    """READY / ONBOARD / ASSESS / ARCHIVE。上岗需已合格 + 已分配岗位。"""
    with session() as db:
        r = _get(db, rec_id)
        if action == "READY":
            if r.status != "PREPARING":
                raise AppException("DATA_CONFLICT", "仅「准备中」可置为待上岗")
            if r.eligibility_status != "QUALIFIED":
                raise AppException("DATA_CONFLICT", "实习资格未认定合格，不能待上岗")
            r.status = "READY"
        elif action == "ONBOARD":
            if r.status != "READY":
                raise AppException("DATA_CONFLICT", "仅「待上岗」可上岗")
            if not r.position_id:
                raise AppException("DATA_CONFLICT", "未分配岗位，不能上岗")
            r.status = "ONBOARD"
            if not r.intern_start_date:
                r.intern_start_date = datetime.utcnow()
        elif action == "ASSESS":
            if r.status != "ONBOARD":
                raise AppException("DATA_CONFLICT", "仅「在岗中」可进入考核")
            r.status = "ASSESSING"
        elif action == "ARCHIVE":
            if r.status not in ("ASSESSING", "ONBOARD"):
                raise AppException("DATA_CONFLICT", "仅在岗/考核中可归档")
            r.status = "ARCHIVED"
        else:
            raise AppException("VALIDATION_ERROR", "非法状态动作")
        _trail(db, r.id, f"STATUS_{action}", {"reason": reason, "to": r.status})
        db.commit()
        return _row_of(db, r)


def set_eligibility(rec_id, status: str, reason: str = "") -> dict:
    if status not in ("QUALIFIED", "UNQUALIFIED", "PENDING"):
        raise AppException("VALIDATION_ERROR", "非法资格状态")
    with session() as db:
        r = _get(db, rec_id)
        r.eligibility_status = status
        _trail(db, r.id, "ELIGIBILITY", {"status": status, "reason": reason})
        db.commit()
        return _row_of(db, r)


def set_destination(rec_id, destination: str, reason: str = "") -> dict:
    """自主实习 / 免实习 / 未落实。已分配岗位(ASSIGNED)请走退岗，不在此改。"""
    if destination not in ("SELF_ARRANGED", "EXEMPTED", "NONE"):
        raise AppException("VALIDATION_ERROR", "非法去向（分配岗位请用分配接口）")
    with session() as db:
        r = _get(db, rec_id)
        if r.position_id:
            raise AppException("DATA_CONFLICT", "已分配岗位，请先退岗再改去向")
        r.destination_type = destination
        _trail(db, r.id, "DESTINATION", {"destination": destination, "reason": reason})
        db.commit()
        return _row_of(db, r)


# ═══════════ 统计 ═══════════

def student_stats() -> dict:
    with session() as db:
        base = [InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False)]
        total = int(db.scalar(select(func.count()).select_from(InternshipRecord).where(*base)) or 0)
        by_status = [{"status": s, "label": STATUS_LABEL[s],
                      "count": int(db.scalar(select(func.count()).select_from(InternshipRecord).where(
                          *base, InternshipRecord.status == s)) or 0)} for s in STATUS_LABEL]
        assigned = int(db.scalar(select(func.count()).select_from(InternshipRecord).where(
            *base, InternshipRecord.position_id.is_not(None))) or 0)
        unassigned = total - assigned
        qualified = int(db.scalar(select(func.count()).select_from(InternshipRecord).where(
            *base, InternshipRecord.eligibility_status == "QUALIFIED")) or 0)
        return {"total": total, "byStatus": by_status, "assigned": assigned,
                "unassigned": unassigned, "qualified": qualified}


# ═══════════ 导入 / 导出 ═══════════

def import_dry_run(rows: list[dict]) -> dict:
    """按学号建实习学生记录（预校验：学号必填且能匹配学生，批内/库内不重复建档）。"""
    with session() as db:
        profiles = {s.student_no: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).all()}
        existing_sids = {r.student_id for r in db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id.is_(None))).all()}
        errors, seen, valid = [], set(), 0
        for i, r in enumerate(rows or []):
            no = (r.get("studentNo") or "").strip()
            row_no = i + 1
            if not no:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": "学号必填"})
                continue
            stu = profiles.get(no)
            if not stu:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": f"未匹配到学生：{no}"})
                continue
            if stu.id in existing_sids or no in seen:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": f"该学生已建档：{no}"})
                continue
            seen.add(no)
            valid += 1
        return {"total": len(rows or []), "validRows": valid,
                "invalidRows": len(errors), "errors": errors}


def import_confirm(rows: list[dict]) -> dict:
    pre = import_dry_run(rows)
    if pre["invalidRows"] > 0:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")
    with session() as db:
        profiles = {s.student_no: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).all()}
        created = 0
        for r in rows or []:
            stu = profiles.get((r.get("studentNo") or "").strip())
            rec = InternshipRecord(tenant_id=_tid(), student_id=stu.id,
                                   advisor_name=r.get("advisorName") or None,
                                   status="PREPARING", eligibility_status="PENDING",
                                   destination_type="NONE", risk_level="NONE")
            db.add(rec)
            db.flush()
            _trail(db, rec.id, "IMPORT", {"studentNo": stu.student_no})
            created += 1
        db.commit()
        return {"created": created}


def export_students(keyword=None, status=None, eligibility=None) -> dict:
    items, _ = list_students(1, 100000, keyword=keyword, status=status, eligibility=eligibility)
    header = ["姓名", "学号", "班级", "实习状态", "实习资格", "实习去向", "企业", "岗位",
              "企业导师", "校内指导教师", "风险"]
    lines = [",".join(header)]
    for it in items:
        lines.append(",".join(str(x).replace(",", "，") for x in [
            it["name"], it["studentNo"], it["className"], it["statusLabel"], it["eligibilityLabel"],
            it["destinationLabel"], it["enterpriseName"], it["positionName"], it["mentorName"],
            it["advisorName"], it["riskLabel"]]))
    return {"filename": "实习学生导出.csv", "content": "\n".join(lines), "rowCount": len(items)}
