"""岗位实习中心 · 岗位库服务（DB_ENABLED=true 走本模块）。

复用共享企业主档 t_emp_company（不重复造企业表）：岗位关联 company_id；
上架强约束——黑名单企业 / 非「合作中」企业不能上架。
状态机：DRAFT→PENDING→PUBLISHED↔OFFLINE↔SUSPENDED，PUBLISHED→FULL，任意→RISK / →ARCHIVED。
横切：租户隔离 + is_deleted 软删 + 审计到 t_internship_audit_trail(target_type=POSITION)。
batch_id 仅预留（nullable），本模块不依赖实习批次模块已完成。

隔离：本文件不引用批次表/服务；企业校验直接读 EmpCompany（不改企业库服务写逻辑）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (EmpCompany, InternshipAuditTrail, InternshipEnterpriseContact,
                        InternshipPosition, InternshipBatch, InternshipRecord,
                        InternshipSpecialFiling)
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"DRAFT": "草稿", "PENDING": "待审核", "PUBLISHED": "已上架", "OFFLINE": "已下架",
                "SUSPENDED": "已暂停", "FULL": "已满员", "RISK": "风险岗位", "ARCHIVED": "已归档"}
STATUS_TONE = {"DRAFT": "default", "PENDING": "warning", "PUBLISHED": "success", "OFFLINE": "default",
               "SUSPENDED": "warning", "FULL": "primary", "RISK": "danger", "ARCHIVED": "default"}
COOP_LABEL = {"PENDING": "待审核", "ACTIVE": "合作中", "REJECTED": "已驳回",
              "SUSPENDED": "已暂停", "BLACKLIST": "黑名单", "ARCHIVED": "已归档"}


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, pos_id: int, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=pos_id, target_type="POSITION",
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _opt_int(v, field="参数"):
    """body 里可选的数字字段（schema 为 str/Optional[str]）安全转 int：
    空→None；非数字→400 VALIDATION_ERROR（此前裸 int() 对非数字抛 ValueError→500，历史欠账收口）。"""
    raw = str(v or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise AppException("VALIDATION_ERROR", f"{field}格式不正确")
    return int(raw)


def _company(db, company_id) -> EmpCompany:
    cid = _opt_int(company_id, "企业")
    if cid is None:
        raise AppException("VALIDATION_ERROR", "请选择关联企业")
    c = db.get(EmpCompany, cid)
    if not c or c.is_deleted or c.tenant_id != _tid():
        raise not_found("企业不存在或不在当前数据范围内")
    return c


def _get(db, pos_id) -> InternshipPosition:
    p = db.get(InternshipPosition, _as_id(pos_id))
    if not p or p.is_deleted or p.tenant_id != _tid():
        raise not_found("岗位不存在或不在当前数据范围内")
    return p


def _row(p: InternshipPosition, db=None) -> dict:
    out = {
        "id": str(p.id), "companyId": str(p.company_id), "companyName": p.company_name or "",
        "batchId": str(p.batch_id) if p.batch_id else "",
        "title": p.title, "category": p.category or "",
        "majorRequirement": p.major_requirement or "", "gradeRequirement": p.grade_requirement or "",
        "workLocation": p.work_location or "", "salaryRange": p.salary_range or "",
        "geofenceLat": p.geofence_lat, "geofenceLng": p.geofence_lng,
        "geofenceRadiusM": p.geofence_radius_m,
        "subsidy": p.subsidy or "", "headcount": p.headcount, "allocatedCount": p.allocated_count,
        "remaining": max(0, p.headcount - p.allocated_count),
        "mentorContactId": str(p.mentor_contact_id) if p.mentor_contact_id else "",
        "mentorName": p.mentor_name or "",
        "riskFlag": bool(p.risk_flag), "riskNote": p.risk_note or "",
        "workContent": p.work_content,
        "workAddress": p.work_address or p.work_location,
        "dailyHours": p.daily_hours, "weeklyHours": p.weekly_hours,
        "shiftType": p.shift_type, "nightShift": p.night_shift,
        "overtimeAllowed": p.overtime_allowed,
        "restDaysPerWeek": p.rest_days_per_week,
        "remunerationType": p.remuneration_type,
        "remunerationAmount": p.remuneration_amount,
        "remunerationCycle": p.remuneration_cycle,
        "accommodationProvided": p.accommodation_provided,
        "mealProvided": p.meal_provided, "hazardousFlag": p.hazardous_flag,
        "specialEquipment": p.special_equipment,
        "prohibitedReason": p.prohibited_reason,
        "rightsStatus": p.rights_status or "UNKNOWN",
        "rightsCheckedAt": _iso(p.rights_checked_at),
        "rightsRuleVersion": p.rights_rule_version,
        "status": p.status, "statusLabel": STATUS_LABEL.get(p.status, p.status),
        "statusTone": STATUS_TONE.get(p.status, "default"),
        "remark": p.remark or "", "publishAt": _iso(p.publish_at),
        "archivedAt": _iso(p.archived_at), "archivedBy": p.archived_by or "",
        "updatedAt": _iso(p.updated_at), "version": int(p.version or 0),
    }
    if db is not None:
        from app.modules.internship.services.internship_position_rights import (
            evaluate_position_publishability)
        company = db.get(EmpCompany, p.company_id)
        batch = db.get(InternshipBatch, p.batch_id) if p.batch_id else None
        result = evaluate_position_publishability(p, company, batch, db=db)
        out.update({
            "publishable": result["passed"],
            "complianceBlockerCount": len(result["blockers"]),
            "complianceWarningCount": len(result["warnings"]),
            "complianceUnknownCount": len(result["unknowns"]),
            "complianceRuleVersion": result["ruleVersion"],
            "compliance": result,
        })
    return out


# ═══════════ 列表 / 详情 ═══════════

def list_positions(page: int, page_size: int, keyword=None, status=None,
                   company_id=None, batch_id=None, risk=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(InternshipPosition).where(InternshipPosition.tenant_id == _tid(),
                                             InternshipPosition.is_deleted.is_(False))
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.where(or_(InternshipPosition.title.like(like),
                            InternshipPosition.company_name.like(like),
                            InternshipPosition.major_requirement.like(like)))
        if status:
            q = q.where(InternshipPosition.status == status)
        cid = _opt_int(company_id, "企业")
        if cid is not None:
            q = q.where(InternshipPosition.company_id == cid)
        bid = _opt_int(batch_id, "批次")  # 岗位按实习批次筛选（batch_id 联调收口）
        if bid is not None:
            q = q.where(InternshipPosition.batch_id == bid)
        if risk is not None:
            q = q.where(InternshipPosition.risk_flag.is_(bool(risk)))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(InternshipPosition.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_row(p, db) for p in rows], total


def get_position(pos_id) -> dict:
    with session() as db:
        p = _get(db, pos_id)
        c = db.get(EmpCompany, p.company_id)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "POSITION",
            InternshipAuditTrail.target_id == p.id).order_by(
            InternshipAuditTrail.occurred_at.desc()).limit(30)).all()
        company = None
        if c and not c.is_deleted:
            company = {"id": str(c.id), "name": c.name, "coopStatus": c.coop_status,
                       "coopStatusLabel": COOP_LABEL.get(c.coop_status, c.coop_status),
                       "blacklist": bool(c.blacklist)}
        # 反向补：本岗位已分配学生（allocated_count 的真实来源，实习学生分配闭环回填）
        from app.models import InternshipRecord, StudentProfile
        recs = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
            InternshipRecord.position_id == p.id).order_by(InternshipRecord.id)).all()
        smap = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([r.student_id for r in recs]))).all()} if recs else {}
        assigned = [{"recordId": str(r.id), "studentId": str(r.student_id),
                     "name": (smap.get(r.student_id).real_name if smap.get(r.student_id) else "-"),
                     "studentNo": (smap.get(r.student_id).student_no if smap.get(r.student_id) else "-"),
                     "status": r.status} for r in recs]
        return {
            **_row(p, db),
            "company": company,
            "assignedStudents": assigned,
            "assignedCount": len(assigned),
            "auditTrail": [{"action": a.action, "operator": a.operator_name or "",
                            "detail": a.detail_json or {}, "occurredAt": _iso(a.occurred_at)}
                           for a in trail],
        }


# ═══════════ 增 / 改 ═══════════

def _resolve_mentor(db, company_id: int, mentor_contact_id) -> tuple[int | None, str | None]:
    if not mentor_contact_id:
        return None, None
    t = db.get(InternshipEnterpriseContact, _as_id(mentor_contact_id))
    if not t or t.is_deleted or t.tenant_id != _tid() or t.company_id != company_id:
        raise AppException("VALIDATION_ERROR", "企业导师不存在或不属于该企业")
    return t.id, t.name


def _validate_geofence(lat, lng, radius) -> None:
    """A geofence is only active when its center and radius are all present."""
    supplied = (lat is not None, lng is not None, radius is not None)
    if any(supplied) and not all(supplied):
        raise AppException("VALIDATION_ERROR", "岗位围栏须同时填写中心经纬度和半径")


def create_position(body) -> dict:
    with session() as db:
        title = (getattr(body, "title", "") or "").strip()
        if not title:
            raise AppException("VALIDATION_ERROR", "岗位名称必填")
        c = _company(db, body.companyId)  # 岗位必须关联企业
        mentor_id, mentor_name = _resolve_mentor(db, c.id, getattr(body, "mentorContactId", None))
        _validate_geofence(getattr(body, "geofenceLat", None), getattr(body, "geofenceLng", None),
                           getattr(body, "geofenceRadiusM", None))
        p = InternshipPosition(
            tenant_id=_tid(), company_id=c.id, company_name=c.name,
            batch_id=_opt_int(getattr(body, "batchId", None), "批次"),
            title=title, category=getattr(body, "category", None),
            major_requirement=getattr(body, "majorRequirement", None),
            grade_requirement=getattr(body, "gradeRequirement", None),
            work_location=getattr(body, "workLocation", None),
            geofence_lat=getattr(body, "geofenceLat", None),
            geofence_lng=getattr(body, "geofenceLng", None),
            geofence_radius_m=getattr(body, "geofenceRadiusM", None),
            salary_range=getattr(body, "salaryRange", None), subsidy=getattr(body, "subsidy", None),
            work_content=(getattr(body, "workContent", None) or "").strip() or None,
            work_address=getattr(body, "workAddress", None),
            daily_hours=getattr(body, "dailyHours", None),
            weekly_hours=getattr(body, "weeklyHours", None),
            shift_type=getattr(body, "shiftType", None),
            night_shift=getattr(body, "nightShift", None),
            overtime_allowed=getattr(body, "overtimeAllowed", None),
            rest_days_per_week=getattr(body, "restDaysPerWeek", None),
            remuneration_type=getattr(body, "remunerationType", None),
            remuneration_amount=getattr(body, "remunerationAmount", None),
            remuneration_cycle=getattr(body, "remunerationCycle", None),
            accommodation_provided=getattr(body, "accommodationProvided", None),
            meal_provided=getattr(body, "mealProvided", None),
            hazardous_flag=getattr(body, "hazardousFlag", None),
            special_equipment=getattr(body, "specialEquipment", None),
            prohibited_reason=getattr(body, "prohibitedReason", None),
            headcount=getattr(body, "headcount", 1) or 1,
            mentor_contact_id=mentor_id, mentor_name=mentor_name,
            remark=getattr(body, "remark", None), status="DRAFT")
        db.add(p)
        db.flush()
        _trail(db, p.id, "CREATE", {"title": title, "companyId": str(c.id)})
        db.commit()
        db.refresh(p)
        return _row(p, db)


def update_position(pos_id, body) -> dict:
    with session() as db:
        p = db.scalar(select(InternshipPosition).where(
            InternshipPosition.id == _as_id(pos_id),
            InternshipPosition.tenant_id == _tid(),
            InternshipPosition.is_deleted.is_(False)).with_for_update())
        if not p:
            raise not_found("岗位不存在或不在当前数据范围内")
        if int(p.version or 0) != int(body.expectedVersion):
            raise AppException("DATA_CONFLICT", "岗位已被其他用户修改，请刷新后重试")
        before = {name: getattr(p, name) for name in (
            "work_content", "work_address", "daily_hours", "weekly_hours", "shift_type",
            "night_shift", "overtime_allowed", "rest_days_per_week", "remuneration_type",
            "remuneration_amount", "remuneration_cycle", "accommodation_provided",
            "meal_provided", "hazardous_flag", "special_equipment", "prohibited_reason")}
        lat, lng, radius = (getattr(body, "geofenceLat", None), getattr(body, "geofenceLng", None),
                            getattr(body, "geofenceRadiusM", None))
        if any(v is not None for v in (lat, lng, radius)):
            _validate_geofence(p.geofence_lat if lat is None else lat,
                               p.geofence_lng if lng is None else lng,
                               p.geofence_radius_m if radius is None else radius)
        if p.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档岗位不可编辑")
        for src, col in [("title", "title"), ("category", "category"),
                         ("majorRequirement", "major_requirement"),
                         ("gradeRequirement", "grade_requirement"),
                         ("workLocation", "work_location"), ("salaryRange", "salary_range"),
                         ("geofenceLat", "geofence_lat"), ("geofenceLng", "geofence_lng"),
                         ("geofenceRadiusM", "geofence_radius_m"),
                         ("subsidy", "subsidy"), ("remark", "remark"),
                         ("workContent", "work_content"), ("workAddress", "work_address"),
                         ("dailyHours", "daily_hours"), ("weeklyHours", "weekly_hours"),
                         ("shiftType", "shift_type"), ("nightShift", "night_shift"),
                         ("overtimeAllowed", "overtime_allowed"),
                         ("restDaysPerWeek", "rest_days_per_week"),
                         ("remunerationType", "remuneration_type"),
                         ("remunerationAmount", "remuneration_amount"),
                         ("remunerationCycle", "remuneration_cycle"),
                         ("accommodationProvided", "accommodation_provided"),
                         ("mealProvided", "meal_provided"),
                         ("hazardousFlag", "hazardous_flag"),
                         ("specialEquipment", "special_equipment"),
                         ("prohibitedReason", "prohibited_reason")]:
            if src in body.model_fields_set:
                setattr(p, col, getattr(body, src))
        hc = getattr(body, "headcount", None)
        if hc is not None:
            if hc < p.allocated_count:
                raise AppException("VALIDATION_ERROR", f"容量不能小于已分配人数（{p.allocated_count}）")
            p.headcount = hc
        bid = getattr(body, "batchId", None)
        if bid is not None:
            p.batch_id = _opt_int(bid, "批次")
        mc = getattr(body, "mentorContactId", None)
        if mc is not None:
            p.mentor_contact_id, p.mentor_name = _resolve_mentor(db, p.company_id, mc) if mc else (None, None)
        after = {name: getattr(p, name) for name in before}
        changed = [name for name in before if before[name] != after[name]]
        rec_ids = db.scalars(select(InternshipRecord.id).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.position_id == p.id,
            InternshipRecord.is_deleted.is_(False))).all() if changed else []
        if changed and rec_ids:
            from app.modules.internship.services.internship_consent_service import supersede_for_major_change
            for rec_id in rec_ids:
                supersede_for_major_change(db, rec_id)
                for filing in db.scalars(select(InternshipSpecialFiling).where(
                    InternshipSpecialFiling.tenant_id == _tid(),
                    InternshipSpecialFiling.internship_id == rec_id,
                    InternshipSpecialFiling.status == "APPROVED",
                    InternshipSpecialFiling.is_deleted.is_(False)).with_for_update()).all():
                    filing.status = "SUPERSEDED"
                    filing.version = int(filing.version or 0) + 1
            p.rights_status = "UNKNOWN"
            p.rights_checked_at = None
            p.rights_rule_version = None
        p.version = int(p.version or 0) + 1
        _trail(db, p.id, "UPDATE", {"before": before, "after": after,
                                     "majorChangedFields": changed})
        db.commit()
        db.refresh(p)
        return _row(p, db)


# ═══════════ 状态机 ═══════════

def set_status(pos_id, action: str, reason: str = "") -> dict:
    """SUBMIT / PUBLISH / OFFLINE / SUSPEND / ARCHIVE。上架强约束黑名单/停用企业。"""
    with session() as db:
        p = _get(db, pos_id)
        if p.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档岗位不可再变更状态")
        if action == "SUBMIT":
            if p.status != "DRAFT":
                raise AppException("DATA_CONFLICT", "仅「草稿」可提交审核")
            p.status = "PENDING"
        elif action == "PUBLISH":
            if p.status not in ("PENDING", "OFFLINE", "SUSPENDED"):
                raise AppException("DATA_CONFLICT", "仅待审核/已下架/已暂停岗位可上架")
            c = _company(db, p.company_id)
            batch = db.get(InternshipBatch, p.batch_id) if p.batch_id else None
            from app.modules.internship.services.internship_position_rights import (
                evaluate_position_publishability)
            rights = evaluate_position_publishability(
                p, c, batch, operation="PUBLISH", db=db)
            p.rights_status = "COMPLIANT" if rights["passed"] else "NON_COMPLIANT"
            p.rights_checked_at = datetime.utcnow()
            p.rights_rule_version = rights["ruleVersion"]
            if not rights["passed"]:
                reasons = [x["reason"] for x in rights["blockers"] + rights["unknowns"]]
                raise AppException("DATA_CONFLICT", "岗位发布检查未通过：" + "；".join(reasons))
            p.status = "PUBLISHED"
            p.publish_at = datetime.utcnow()
        elif action == "OFFLINE":
            if p.status not in ("PUBLISHED", "SUSPENDED", "FULL"):
                raise AppException("DATA_CONFLICT", "仅上架/暂停/满员岗位可下架")
            p.status = "OFFLINE"
        elif action == "SUSPEND":
            if p.status != "PUBLISHED":
                raise AppException("DATA_CONFLICT", "仅「已上架」岗位可暂停")
            p.status = "SUSPENDED"
        elif action == "ARCHIVE":
            active_count = int(db.scalar(select(func.count()).select_from(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.position_id == p.id,
                InternshipRecord.status.in_(("PREPARING", "READY", "ONBOARD", "ASSESSING")),
                InternshipRecord.is_deleted.is_(False))) or 0)
            if int(p.allocated_count or 0) > 0 or active_count > 0:
                raise AppException(
                    "DATA_CONFLICT",
                    f"岗位仍有 {max(int(p.allocated_count or 0), active_count)} 名有效学生，不可归档；请先完成正式调岗/退岗")
            p.status = "ARCHIVED"
            p.archived_at = datetime.utcnow()
            p.archived_by = _op_name()
        else:
            raise AppException("VALIDATION_ERROR", "非法状态动作")
        _trail(db, p.id, f"STATUS_{action}", {"reason": reason, "to": p.status})
        db.commit()
        db.refresh(p)
        return _row(p, db)


def mark_risk(pos_id, on: bool, note: str = "") -> dict:
    with session() as db:
        p = _get(db, pos_id)
        if p.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档岗位不可标记风险")
        if on:
            if not (note or "").strip():
                raise AppException("VALIDATION_ERROR", "标记风险岗位必须填写风险说明")
            p.risk_flag = True
            p.risk_note = note.strip()
            p.status = "RISK"
        else:
            p.risk_flag = False
            p.risk_note = None
            p.status = "OFFLINE"  # 解除风险后回到已下架，需重新上架
        _trail(db, p.id, "RISK_ON" if on else "RISK_OFF", {"note": note})
        db.commit()
        db.refresh(p)
        return _row(p, db)


# ═══════════ 统计 ═══════════

def position_stats() -> dict:
    with session() as db:
        base = [InternshipPosition.tenant_id == _tid(), InternshipPosition.is_deleted.is_(False)]
        total = int(db.scalar(select(func.count()).select_from(InternshipPosition).where(*base)) or 0)
        by_status = []
        for st in STATUS_LABEL:
            by_status.append({"status": st, "label": STATUS_LABEL[st],
                              "count": int(db.scalar(select(func.count()).select_from(
                                  InternshipPosition).where(*base, InternshipPosition.status == st)) or 0)})
        risk = int(db.scalar(select(func.count()).select_from(InternshipPosition).where(
            *base, InternshipPosition.risk_flag.is_(True))) or 0)
        cap = db.execute(select(func.coalesce(func.sum(InternshipPosition.headcount), 0),
                                func.coalesce(func.sum(InternshipPosition.allocated_count), 0)).where(
            *base, InternshipPosition.status == "PUBLISHED")).first()
        published_capacity = int(cap[0] or 0)
        published_allocated = int(cap[1] or 0)
        util = round(published_allocated * 100.0 / published_capacity, 1) if published_capacity else 0.0
        # 已上架岗位按专业要求聚合；空专业计入 unlimitedMajorCount
        pub_rows = db.scalars(select(InternshipPosition).where(
            *base, InternshipPosition.status == "PUBLISHED")).all()
        major_map: dict[str, dict] = {}
        unlimited = 0
        for p in pub_rows:
            req = (p.major_requirement or "").strip()
            if not req:
                unlimited += 1
                key = "(不限专业)"
            else:
                key = req
            bucket = major_map.setdefault(key, {"major": key, "count": 0, "capacity": 0, "allocated": 0})
            bucket["count"] += 1
            bucket["capacity"] += int(p.headcount or 0)
            bucket["allocated"] += int(p.allocated_count or 0)
        by_major = sorted(major_map.values(), key=lambda x: (-x["count"], x["major"]))
        return {
            "total": total, "byStatus": by_status, "riskCount": risk,
            "publishedCapacity": published_capacity, "publishedAllocated": published_allocated,
            "capacityUtilization": util,
            "unlimitedMajorCount": unlimited,
            "byMajor": by_major,
        }


def count_for_enterprise(company_id) -> dict:
    """企业库反向补：某企业岗位数摘要（不含软删）。"""
    with session() as db:
        base = [InternshipPosition.tenant_id == _tid(), InternshipPosition.is_deleted.is_(False),
                InternshipPosition.company_id == int(company_id)]
        total = int(db.scalar(select(func.count()).select_from(InternshipPosition).where(*base)) or 0)
        published = int(db.scalar(select(func.count()).select_from(InternshipPosition).where(
            *base, InternshipPosition.status == "PUBLISHED")) or 0)
        return {"total": total, "published": published}


# ═══════════ 导入 / 导出（Excel 真导入导出；dry-run 与粘贴共用）═══════════

def _resolve_company(companies, key: str):
    by_code = {c.credit_code: c for c in companies if c.credit_code}
    by_name = {c.name: c for c in companies}
    return by_code.get(key) or by_name.get(key)


def _company_import_block(c) -> str | None:
    """导入岗位时企业须存在且非黑名单、须合作中。"""
    if not c:
        return None
    if c.blacklist or c.coop_status == "BLACKLIST":
        return "黑名单企业不能导入岗位"
    if c.coop_status != "ACTIVE":
        return f"停用/未合作企业不能导入岗位（当前：{COOP_LABEL.get(c.coop_status, c.coop_status)}）"
    return None


def _nullable_bool(value):
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().lower()
    if text in ("是", "true", "1", "y", "yes"):
        return True
    if text in ("否", "false", "0", "n", "no"):
        return False
    raise ValueError("须填写是/否")


def import_dry_run(rows: list[dict], template_version=None) -> dict:
    """逐行预校验：title/company 必填；企业须存在且合作中；容量为正整数；批内+库内去重。"""
    with session() as db:
        if template_version != "POSITION_IMPORT_V2":
            raise AppException("VALIDATION_ERROR", "仅支持 POSITION_IMPORT_V2 模板")
        companies = db.scalars(select(EmpCompany).where(
            EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False))).all()
        existing = {(p.company_id, (p.title or "").strip().lower()) for p in db.scalars(
            select(InternshipPosition).where(
                InternshipPosition.tenant_id == _tid(),
                InternshipPosition.is_deleted.is_(False))).all()}
        errors, seen, valid = [], set(), 0
        for i, r in enumerate(rows or []):
            row_no = i + 1
            if (r.get("templateVersion") or "").strip() != "POSITION_IMPORT_V2":
                errors.append({"rowNo": row_no, "field": "templateVersion",
                               "message": "模板版本必须为 POSITION_IMPORT_V2"})
                continue
            title = (r.get("title") or "").strip()
            key = (r.get("company") or "").strip()
            if not title:
                errors.append({"rowNo": row_no, "field": "title", "message": "岗位名称必填"})
                continue
            if not key:
                errors.append({"rowNo": row_no, "field": "company", "message": "关联企业必填"})
                continue
            c = _resolve_company(companies, key)
            if not c:
                errors.append({"rowNo": row_no, "field": "company",
                               "message": f"未匹配到企业（信用码/名称）：{key}"})
                continue
            blk = _company_import_block(c)
            if blk:
                errors.append({"rowNo": row_no, "field": "company", "message": blk})
                continue
            batch_no = (r.get("batchNo") or "").strip()
            batch = db.scalars(select(InternshipBatch).where(
                InternshipBatch.tenant_id == _tid(), InternshipBatch.batch_no == batch_no,
                InternshipBatch.is_deleted.is_(False))).first()
            if not batch:
                errors.append({"rowNo": row_no, "field": "batchNo", "message": "实习批次编号不存在"})
                continue
            for field in ("workContent", "dailyHours", "weeklyHours", "nightShift",
                          "overtimeAllowed", "restDaysPerWeek", "remunerationType",
                          "accommodationProvided", "mealProvided", "hazardousFlag"):
                if r.get(field) is None or str(r.get(field)).strip() == "":
                    errors.append({"rowNo": row_no, "field": field,
                                   "message": f"{field} 为发布规则必填事实，不能留空"})
            try:
                for field in ("nightShift", "overtimeAllowed", "accommodationProvided",
                              "mealProvided", "hazardousFlag"):
                    _nullable_bool(r.get(field))
                if float(r.get("dailyHours")) > 24 or float(r.get("weeklyHours")) > 168:
                    raise ValueError("工时超出DTO范围")
            except (TypeError, ValueError) as exc:
                errors.append({"rowNo": row_no, "field": "rights",
                               "message": f"劳动权益字段格式错误：{exc}"})
            if any(x["rowNo"] == row_no for x in errors):
                continue
            hc_raw = (r.get("headcount") or "1").strip() if isinstance(r.get("headcount"), str) else r.get("headcount")
            try:
                hc = int(hc_raw or 1)
                if hc < 1:
                    raise ValueError()
            except (TypeError, ValueError):
                errors.append({"rowNo": row_no, "field": "headcount", "message": "容量必须为正整数"})
                continue
            dup_key = (c.id, title.lower())
            if dup_key in existing:
                errors.append({"rowNo": row_no, "field": "title", "message": f"库内已存在同企业同岗位：{title}"})
                continue
            if dup_key in seen:
                errors.append({"rowNo": row_no, "field": "title", "message": f"文件内同企业岗位重复：{title}"})
                continue
            seen.add(dup_key)
            valid += 1
        return {"total": len(rows or []), "validRows": valid,
                "invalidRows": len(errors), "errors": errors}


def import_confirm(rows: list[dict], template_version=None) -> dict:
    pre = import_dry_run(rows, template_version)
    if pre["invalidRows"] > 0:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")
    with session() as db:
        companies = db.scalars(select(EmpCompany).where(
            EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False))).all()
        created = 0
        for r in rows or []:
            if (r.get("templateVersion") or "").strip() != "POSITION_IMPORT_V2":
                raise AppException("DATA_CONFLICT", "确认导入时模板版本不匹配")
            key = (r.get("company") or "").strip()
            c = _resolve_company(companies, key)
            if not c or _company_import_block(c):
                raise AppException("DATA_CONFLICT", "确认导入时企业状态已变化")
            batch = db.scalars(select(InternshipBatch).where(
                InternshipBatch.tenant_id == _tid(),
                InternshipBatch.batch_no == (r.get("batchNo") or "").strip(),
                InternshipBatch.is_deleted.is_(False))).first()
            if not batch:
                raise AppException("DATA_CONFLICT", "确认导入时批次不存在")
            duplicate = db.scalars(select(InternshipPosition.id).where(
                InternshipPosition.tenant_id == _tid(),
                InternshipPosition.company_id == c.id,
                func.lower(InternshipPosition.title) == (r.get("title") or "").strip().lower(),
                InternshipPosition.is_deleted.is_(False)).with_for_update()).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", "确认导入时发现重复岗位")
            hc_raw = r.get("headcount") or 1
            hc = int(hc_raw) if str(hc_raw).isdigit() else 1
            p = InternshipPosition(
                tenant_id=_tid(), company_id=c.id, company_name=c.name,
                batch_id=batch.id,
                title=(r.get("title") or "").strip(),
                major_requirement=r.get("major") or None,
                grade_requirement=r.get("grade") or None,
                work_content=r.get("workContent") or None,
                work_address=r.get("workAddress") or None,
                work_location=r.get("workAddress") or None,
                daily_hours=float(r["dailyHours"]), weekly_hours=float(r["weeklyHours"]),
                shift_type=r.get("shiftType") or None,
                night_shift=_nullable_bool(r.get("nightShift")),
                overtime_allowed=_nullable_bool(r.get("overtimeAllowed")),
                rest_days_per_week=float(r["restDaysPerWeek"]),
                remuneration_type=r.get("remunerationType") or None,
                remuneration_amount=float(r["remunerationAmount"]) if str(r.get("remunerationAmount") or "").strip() else None,
                remuneration_cycle=r.get("remunerationCycle") or None,
                accommodation_provided=_nullable_bool(r.get("accommodationProvided")),
                meal_provided=_nullable_bool(r.get("mealProvided")),
                hazardous_flag=_nullable_bool(r.get("hazardousFlag")),
                special_equipment=r.get("specialEquipment") or None,
                prohibited_reason=r.get("prohibitedReason") or None,
                headcount=max(1, hc), status="DRAFT",
                mentor_name=r.get("mentor") or None,
                remark=r.get("remark") or None)
            db.add(p)
            db.flush()
            _trail(db, p.id, "IMPORT", {"title": p.title})
            created += 1
        db.commit()
        return {"created": created}


def export_positions(keyword=None, status=None, company_id=None, batch_id=None) -> dict:
    from app.services import xlsx_util
    from app.modules.internship.services.internship_export_util import require_exportable
    with session() as db:
        count_query = select(func.count()).select_from(InternshipPosition).where(
            InternshipPosition.tenant_id == _tid(),
            InternshipPosition.is_deleted.is_(False))
        if keyword:
            like = f"%{keyword.strip()}%"
            count_query = count_query.where(or_(
                InternshipPosition.title.like(like),
                InternshipPosition.company_name.like(like),
                InternshipPosition.major_requirement.like(like)))
        if status:
            count_query = count_query.where(InternshipPosition.status == status)
        if company_id:
            count_query = count_query.where(
                InternshipPosition.company_id == _opt_int(company_id, "企业"))
        if batch_id:
            count_query = count_query.where(
                InternshipPosition.batch_id == _opt_int(batch_id, "批次"))
        total = int(db.scalar(count_query) or 0)
        require_exportable(total)
    items, _ = list_positions(1, total, keyword=keyword, status=status,
                              company_id=company_id, batch_id=batch_id)
    headers = ["批次ID", "岗位名称", "关联企业", "工作内容", "工作地址", "每日工时",
               "每周工时", "班次", "是否夜班", "是否允许加班", "每周休息天数",
               "报酬类型", "报酬金额", "发放周期", "是否住宿", "是否供餐",
               "是否危险岗位", "特殊设备", "禁止安排原因", "容量", "专业要求",
               "年级要求", "企业导师", "状态", "权益状态", "规则版本", "备注"]
    data_rows = []
    for it in items:
        data_rows.append([
            it["batchId"], it["title"], it["companyName"], it["workContent"] or "",
            it["workAddress"] or "", it["dailyHours"], it["weeklyHours"], it["shiftType"] or "",
            it["nightShift"], it["overtimeAllowed"], it["restDaysPerWeek"],
            it["remunerationType"] or "", it["remunerationAmount"], it["remunerationCycle"] or "",
            it["accommodationProvided"], it["mealProvided"], it["hazardousFlag"],
            it["specialEquipment"] or "", it["prohibitedReason"] or "", it["headcount"],
            it["majorRequirement"], it["gradeRequirement"], it["mentorName"], it["statusLabel"],
            it["rightsStatus"], it["rightsRuleVersion"] or "", it.get("remark") or ""])
    user = get_current_user_ctx() or {}
    wm = (f"岗位实习中心·岗位库台账 · 导出人：{user.get('realName', '-')} · "
          f"{datetime.now():%Y-%m-%d %H:%M}")
    content = xlsx_util.build_ledger_xlsx("岗位库台账", headers, data_rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "岗位库台账.xlsx", len(items))
