"""13A-P7 多端收口：学工中心学生自视图 + 学生自选床位 + 教师学工待办（mobile 前缀）。

学生端只见本人(resolve_student 解析登录学生→按 student_id 查各域)；处分只回数量不回明细；
宿舍读学校自选开关决定选床还是提示辅导员分配。教师端聚合本校学工待办卡。
"""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException, no_permission
from app.services.db_service import _iso, _tid, session
from app.services.mobile_student_service import _require_student, resolve_student


def _me(db, user):
    u = _require_student(user)
    stu = resolve_student(db, u)
    if not stu:
        raise no_permission("尚未建立你的学生档案")
    return stu


# ═══════════ 学生自视图 ═══════════

def leave_my(user) -> dict:
    """本人请假记录：t_cs_leave 双状态列并行(P0 §4.2 集成①)——13A 新提交走
    student_id+affairs_status；老 campus-service 提交只有 cs_student_id+status。
    只按 student_id 查会漏掉老记录（学生自己在「我的申请」能看到、在本页却看不到），
    这里同 my_applications 一样再按 CsServiceStudent 解析补上 cs_student_id 分支。"""
    from app.models import CsLeave, CsServiceStudent
    with session() as db:
        stu = _me(db, user)
        cs = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(), CsServiceStudent.is_deleted.is_(False),
            (CsServiceStudent.student_no == stu.student_no) | (CsServiceStudent.name == stu.real_name))).first()
        conds = [CsLeave.student_id == stu.id]
        if cs:
            conds.append(CsLeave.cs_student_id == cs.id)
        rows = db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(), or_(*conds), CsLeave.is_deleted.is_(False))
            .order_by(CsLeave.id.desc())).all()
        return {"items": [{"leaveId": str(x.id), "leaveType": x.leave_type, "days": float(x.days or 0),
                           "startTime": _iso(x.start_time), "endTime": _iso(x.end_time),
                           "status": x.affairs_status or x.status, "reason": x.reason or "",
                           "returnReason": getattr(x, "return_reason", None) or ""} for x in rows]}


def aid_my(user) -> dict:
    from app.models import AidApply
    with session() as db:
        stu = _me(db, user)
        rows = db.scalars(select(AidApply).where(
            AidApply.tenant_id == _tid(), AidApply.student_id == stu.id,
            AidApply.is_deleted.is_(False)).order_by(AidApply.id.desc())).all()
        approved = next((x for x in rows if x.status == "APPROVED"), None)
        return {"currentLevel": (approved.final_level if approved else None),
                "items": [{"applyId": str(x.id), "applyLevel": x.apply_level,
                           "finalLevel": x.final_level, "status": x.status,
                           "returnReason": getattr(x, "return_reason", None) or ""} for x in rows]}


def funding_my(user) -> dict:
    from app.models import FundingAppeal, FundingApplication
    L = {"DRAFT": "草稿", "SUBMITTED": "已提交", "COUNSELOR_REVIEW": "辅导员初审",
         "COLLEGE_REVIEW": "学院评审", "SCHOOL_REVIEW": "学校审批", "PUBLICITY": "公示中",
         "GRANTED": "已获资助", "REJECTED": "已驳回", "RETURNED": "已退回",
         "CANCELLED": "已取消", "ARCHIVED": "已归档"}
    with session() as db:
        stu = _me(db, user)
        rows = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == _tid(), FundingApplication.student_id == stu.id,
            FundingApplication.is_deleted.is_(False)).order_by(FundingApplication.id.desc())).all()
        open_ids = set(db.scalars(select(FundingAppeal.application_id).where(
            FundingAppeal.tenant_id == _tid(), FundingAppeal.student_id == stu.id,
            FundingAppeal.status == "SUBMITTED", FundingAppeal.is_deleted.is_(False))).all())
        items = []
        for x in rows:
            pending = int(x.id) in open_ids
            items.append({
                "applicationId": str(x.id), "projectType": x.project_type,
                "status": x.status, "statusLabel": L.get(x.status, x.status),
                "returnReason": x.return_reason or "",
                "canAppeal": x.status == "PUBLICITY" and not pending,
                "hasPendingAppeal": pending,
            })
        return {"items": items}


def discipline_my(user) -> dict:
    """学生端仅回数量+生效处分的申诉入口所需最小信息（caseId/申诉状态），不回完整卷宗细节
    （既有 t_cs_discipline 约定，13A 沿用）。"""
    from app.models import DisciplineAppeal, DisciplineCase
    L_DISC_TYPE = {"WARNING": "警告", "SERIOUS_WARNING": "严重警告", "DEMERIT": "记过",
                   "PROBATION": "留校察看", "EXPEL": "开除学籍"}
    with session() as db:
        stu = _me(db, user)
        rows = db.scalars(select(DisciplineCase).where(
            DisciplineCase.tenant_id == _tid(), DisciplineCase.student_id == stu.id,
            DisciplineCase.status == "EFFECTIVE", DisciplineCase.is_deleted.is_(False))
            .order_by(DisciplineCase.id.desc())).all()
        appeals = db.scalars(select(DisciplineAppeal).where(
            DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.student_id == stu.id,
            DisciplineAppeal.is_deleted.is_(False)).order_by(DisciplineAppeal.id.desc())).all()
        latest_appeal = {}
        for a in appeals:
            latest_appeal.setdefault(str(a.case_id), a)
        items = []
        for x in rows:
            ap = latest_appeal.get(str(x.id))
            items.append({
                "caseId": str(x.id), "discType": x.disc_type,
                "discTypeLabel": L_DISC_TYPE.get(x.disc_type, x.disc_type),
                "effectiveAt": _iso(x.effective_at),
                "appealStatus": ap.status if ap else None,
                "appealResult": ap.result if ap else None,
                "appealReviewOpinion": ap.review_opinion if ap else "",
                "canAppeal": not (ap and ap.status in ("SUBMITTED", "REVIEWING")),
            })
        return {"activeCount": len(rows), "detailNote": "处分明细不在移动端展示，如有疑问请联系辅导员",
               "items": items}


def dorm_my(user) -> dict:
    """我的宿舍：当前床位 + 学校自选开关(决定是否显示选床入口)。"""
    from app.models import DormBed, DormBuilding, DormRoom
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        stu = _me(db, user)
        bed = db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(), DormBed.student_id == stu.id,
            DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False))).first()
        my_bed = None
        if bed:
            b = db.get(DormBuilding, int(bed.building_id))
            room = db.get(DormRoom, int(bed.room_id))
            my_bed = {"bedId": str(bed.id), "building": b.building_name if b else "",
                      "room": room.room_no if room else "", "bedNo": bed.bed_no,
                      "occupiedAt": _iso(bed.occupied_at)}
    cfg = dorm.get_dorm_config(user)  # selfSelectEnabled + studentNotice
    return {"myBed": my_bed, "hasBed": bool(my_bed), **cfg}


def overview_my(user) -> dict:
    """学工自视图总览（各域本人计数）。"""
    from app.models import (AffairsRiskRecord, AidApply, CsLeave, DisciplineCase,
                            FundingApplication, TalkRecord)
    with session() as db:
        stu = _me(db, user)
        sid = stu.id

        def _c(model, *extra):
            return db.scalar(select(func.count()).select_from(model).where(
                model.tenant_id == _tid(), model.student_id == sid,
                model.is_deleted.is_(False), *extra)) or 0

        return {
            "studentName": stu.real_name,
            "leaveCount": _c(CsLeave, CsLeave.affairs_status.is_not(None)),
            "aidApproved": _c(AidApply, AidApply.status == "APPROVED"),
            "fundingGranted": _c(FundingApplication, FundingApplication.status == "GRANTED"),
            "disciplineActive": _c(DisciplineCase, DisciplineCase.status == "EFFECTIVE"),
            "riskOpen": _c(AffairsRiskRecord, AffairsRiskRecord.status.notin_(["CLOSED"])),
            "talkCount": _c(TalkRecord),
        }


# ═══════════ 学生自选床位（受学校开关控制）═══════════

def dorm_select_options(user) -> dict:
    """选床可选项：先回配置，放开时按本人性别列可选楼(带空床数)。"""
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        stu = _me(db, user)
        gender = stu.gender
    cfg = dorm.get_dorm_config(user)
    if not cfg["selfSelectEnabled"]:
        return {**cfg, "buildings": []}
    buildings, _ = dorm.list_buildings(user, gender=gender)
    return {**cfg, "buildings": buildings}


def _require_self_select_on(user):
    from app.services import affairs_dorm_service as dorm
    if not dorm.is_self_select_enabled():
        raise no_permission(dorm._NOTICE_OFF)


def dorm_rooms(user, building_id, floor=None) -> dict:
    """学生浏览某楼房间（选床级联，仅学校放开自选时可用）。"""
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        _me(db, user)
    _require_self_select_on(user)
    items, total = dorm.list_rooms(building_id, user, floor)
    return {"items": items, "total": total}


def dorm_beds(user, room_id) -> dict:
    """学生浏览某房床位（选床级联，仅学校放开自选时可用）。"""
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        _me(db, user)
    _require_self_select_on(user)
    return {"items": dorm.list_beds(room_id, user)}


def dorm_self_select(user, bed_id) -> dict:
    """学生自选某空床入住本人。学校未放开→403（含提醒文案）。只能给自己选。"""
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
    return dorm.self_select_checkin(bed_id, user, sid)


# ═══════════ 教师端学工待办卡 ═══════════

def teacher_affairs(user) -> dict:
    """教师工作台学工卡：本校待处理学工待办按类型聚合。"""
    from app.models import UnifiedTodo
    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    with session() as db:
        rows = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False))).all()
        by_type = {}
        for r in rows:
            by_type[r.todo_type] = by_type.get(r.todo_type, 0) + 1
        label = {"LEAVE_APPROVAL": "请假待审", "LEAVE_CANCEL": "销假待确认",
                 "LEAVE_OVERDUE": "逾期未销假", "LEAVE_EXTENSION": "续假待审",
                 "AID_APPROVAL": "困难认定待审", "AID_ADJUST": "困难等级调整待审",
                 "FUNDING_APPROVAL": "奖助待审", "DISCIPLINE_APPROVAL": "处分待审",
                 "DISCIPLINE_REMOVE": "处分解除待审", "RISK_HANDLE": "风险待处置"}
        cards = [{"todoType": k, "label": label.get(k, k), "count": v} for k, v in sorted(by_type.items())]
        return {"total": sum(by_type.values()), "cards": cards}
