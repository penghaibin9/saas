"""13A-P5 学工画像 + 成长时间线聚合（集中兑现 P2-P4 进360）。

画像：读 t_student_profile + 各域沉淀汇总（leave/aid/funding/discipline/risk/talk）。
时间线：合并 StudentStageEvent（各阶段写入的域事件）倒序呈现，即 360 成长时间线。
处分明细/心理来源按权限；无权限只出计数/"需关注"标记。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_DISC_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "COLLEGE_ADMIN", "COUNSELOR"}
_PSY_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "PSYCHOLOGY_TEACHER"}

# 360 时间线事件 → 中文标题
_STAGE_LABEL = {
    "LEAVE_CLOSED": "请假销假", "AID_APPROVED": "困难认定通过", "FUNDING_GRANTED": "获得资助",
    "DISCIPLINE_EFFECTIVE": "处分生效", "DISCIPLINE_REMOVED": "处分解除",
    "RISK_CLOSED": "风险处置关闭", "TALK_COMPLETED": "谈心谈话", "TALK_CLOSED": "谈话办结",
}
_STAGE_MODULE = {
    "LEAVE_CLOSED": "leave", "AID_APPROVED": "aid", "FUNDING_GRANTED": "funding",
    "DISCIPLINE_EFFECTIVE": "discipline", "DISCIPLINE_REMOVED": "discipline",
    "RISK_CLOSED": "risk", "TALK_COMPLETED": "talk", "TALK_CLOSED": "talk",
}


def _scope_or_403(db, student_id, user):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("学生不存在")
    if allowed is not None and s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", "该学生不在您的数据范围内")
    return s


def get_profile(student_id, user) -> dict:
    from app.models import (AffairsRiskRecord, AidApply, CsLeave, DisciplineCase, DormBed,
                            DormBuilding, DormRoom, FamilyContactLog, FundingApplication,
                            SchoolClass, StudentContact, TalkRecord)
    role = (user or {}).get("currentRoleCode")
    with session() as db:
        s = _scope_or_403(db, student_id, user)
        sid = int(student_id)

        def _count(model, *extra):
            return db.scalar(select(func.count()).select_from(model).where(
                model.tenant_id == _tid(), model.student_id == sid,
                model.is_deleted.is_(False), *extra)) or 0

        # 班级真实名称（禁止把 class_id 当 className 返回）
        class_name = ""
        if s.class_id:
            cls = db.get(SchoolClass, int(s.class_id))
            class_name = (cls.class_name if cls else "") or ""

        # 请假
        leave_total = _count(CsLeave)
        # 困难认定：当前等级（困难库）
        aid = db.scalars(select(AidApply).where(
            AidApply.tenant_id == _tid(), AidApply.student_id == sid,
            AidApply.status == "APPROVED", AidApply.is_deleted.is_(False)).order_by(
            AidApply.id.desc())).first()
        # 奖助
        funding_granted = _count(FundingApplication, FundingApplication.status == "GRANTED")
        # 处分（按权限出计数；无权限也只给数量，明细另走详情端点）
        disc_active = _count(DisciplineCase, DisciplineCase.status == "EFFECTIVE")
        disc_visible = role in _DISC_ROLES
        # 风险
        risk_open = _count(AffairsRiskRecord, AffairsRiskRecord.status.notin_(["CLOSED"]))
        risk_levels = [r.risk_level for r in db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.student_id == sid,
            AffairsRiskRecord.status.notin_(["CLOSED"]), AffairsRiskRecord.is_deleted.is_(False))).all()]
        rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        top_risk = max(risk_levels, key=lambda x: rank.get(x, 0)) if risk_levels else "NONE"
        # 心理关注标记（有 MENTAL 来源风险即"需关注"，明细不出）
        psy_flag = db.scalar(select(func.count()).select_from(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.student_id == sid,
            AffairsRiskRecord.source == "MENTAL", AffairsRiskRecord.is_deleted.is_(False))) or 0
        # 谈话
        talks = db.scalars(select(TalkRecord).where(
            TalkRecord.tenant_id == _tid(), TalkRecord.student_id == sid,
            TalkRecord.is_deleted.is_(False)).order_by(TalkRecord.id.desc())).all()
        last_talk = next((t.talk_at for t in talks if t.talk_at), None)

        # 宿舍入住摘要（有则楼栋+房+床；无则空态，不造假）
        bed = db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(), DormBed.student_id == sid,
            DormBed.is_deleted.is_(False)).order_by(DormBed.id.desc())).first()
        dorm_summary = {"hasDorm": False, "text": ""}
        if bed and bed.room_id:
            room = db.get(DormRoom, int(bed.room_id))
            building = db.get(DormBuilding, int(room.building_id)) if room and room.building_id else None
            parts = []
            if building and building.building_name:
                parts.append(building.building_name)
            if room and room.room_no:
                parts.append(str(room.room_no))
            if bed.bed_no:
                parts.append(f"{bed.bed_no}床")
            dorm_summary = {"hasDorm": True, "text": " · ".join(parts) if parts else "已入住"}

        # 家庭联系人：仅计数/有无；号码本体不在此返回（敏感访问另走家校接口）
        contact_count = db.scalar(select(func.count()).select_from(StudentContact).where(
            StudentContact.tenant_id == _tid(), StudentContact.student_id == sid,
            StudentContact.is_deleted.is_(False),
            StudentContact.contact_type.in_(["GUARDIAN_PHONE", "EMERGENCY_PHONE"]))) or 0
        family_log_count = db.scalar(select(func.count()).select_from(FamilyContactLog).where(
            FamilyContactLog.tenant_id == _tid(), FamilyContactLog.student_id == sid)) or 0
        family_summary = {
            "hasContact": bool(contact_count or family_log_count),
            "contactCount": int(contact_count),
            "logCount": int(family_log_count),
        }

        return {
            "baseInfo": {"studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                         "classId": str(s.class_id or ""), "className": class_name,
                         "currentStage": s.current_stage, "studentStatus": s.student_status},
            "leaveSummary": {"total": leave_total},
            "aidSummary": {"difficultLevel": (aid.final_level if aid else None),
                           "inLibrary": bool(aid)},
            "fundingSummary": {"grantedCount": funding_granted},
            "disciplineSummary": ({"activeCount": disc_active} if disc_visible
                                  else {"activeCount": None, "restricted": True}),
            "riskSummary": {"openCount": risk_open, "topLevel": top_risk},
            "psyFlag": ("需关注" if psy_flag else "无"),
            "talkSummary": {"total": len(talks), "lastTalkAt": _iso(last_talk)},
            "dormSummary": dorm_summary,
            "familySummary": family_summary,
            "timelineUrl": f"/api/v1/student-affairs/students/{sid}/timeline",
        }


def get_timeline(student_id, user, event_type=None, page=1, page_size=20):
    """成长时间线：合并 StudentStageEvent（P2-P5 各域进360事件）倒序。"""
    from app.models import StudentStageEvent
    with session() as db:
        _scope_or_403(db, student_id, user)
        rows = db.scalars(select(StudentStageEvent).where(
            StudentStageEvent.tenant_id == _tid(), StudentStageEvent.student_id == int(student_id))
            .order_by(StudentStageEvent.id.desc())).all()
        out = []
        for e in rows:
            module = _STAGE_MODULE.get(e.to_stage or "", "system")
            if event_type and module != event_type:
                continue
            out.append({
                "eventId": str(e.id), "eventType": e.to_stage or "",
                "module": module, "title": _STAGE_LABEL.get(e.to_stage or "", e.reason or e.to_stage or ""),
                "detail": e.reason or "", "occurredAt": _iso(e.created_at),
            })
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
