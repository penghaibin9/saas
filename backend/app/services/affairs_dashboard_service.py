"""13A 学工中心 · 首页/工作台/班级骨架（P1）。

- 首页三角色视图（学工处/学院学工/辅导员）：聚合既有六域 + 待办，13A 自有业务卡空态。
- 班级骨架：班级列表 + 班干部任免（真实读写），越权跨班 403（全局 handler 自动写审计）。
数据范围复用既有 resolve_teacher_scope（不另起炉灶，草案总纲 12 条 / C4 §5）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

# 角色 → 学工首页视图（P0 §6 权限矩阵角色口径）
_SA_ADMIN_ROLES = {"SCHOOL_ADMIN", "SCHOOL_LEADER", "SA_ADMIN"}
_COLLEGE_ROLES = {"COLLEGE_ADMIN", "COLLEGE_SA"}

_VIEW_LABEL = {"SA_ADMIN": "学工处（全校）", "COLLEGE_SA": "学院学工（本院）", "COUNSELOR": "辅导员（本班）"}

# 13A 13 个业务模块卡（P1 仅班级 LIVE，其余各阶段上线，先渲染空态）
_MODULE_CARDS = [
    ("class", "班级管理", "LIVE"),
    ("leave", "请假销假", "LIVE"),
    ("aid", "困难认定", "LIVE"),
    ("funding", "奖助管理", "LIVE"),
    ("discipline", "违纪处分", "LIVE"),
    ("risk", "风险预警", "LIVE"),
    ("talk", "谈心谈话", "LIVE"),
    ("family", "家校联系", "LIVE"),
    ("dorm", "宿舍管理", "LIVE"),
    ("archive", "学工归档", "LIVE"),
    ("profile", "学生画像", "LIVE"),
    ("psy", "心理关注", "PENDING"),
    ("activity", "学生活动", "PENDING"),
]


def _resolve_view(user: dict) -> str:
    role = (user.get("currentRoleCode") or "").upper()
    if role in _SA_ADMIN_ROLES:
        return "SA_ADMIN"
    if role in _COLLEGE_ROLES:
        return "COLLEGE_SA"
    return "COUNSELOR"  # 默认按最小范围（辅导员/班主任）


def _students_in_classes(db, class_ids):
    """返回给定班级下的学生 id 列表（空哨兵避免 IN() 空表达式）。"""
    from app.models import StudentProfile
    if not class_ids:
        return [-1]
    rows = db.scalars(select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        StudentProfile.class_id.in_(class_ids))).all()
    return list(rows) or [-1]


_MODE_OF = {"TENANT_ALL": "ADMIN_TENANT", "NONE": "NONE", "SELF": "SELF"}

# 用户可见数据范围文案（禁止向老师展示 TENANT_ALL / SCOPED 等内部码）
_SCOPE_LABEL = {
    "TENANT_ALL": "全校",
    "COLLEGE": "本院",
    "CLASS": "本人负责范围",
    "STUDENT": "本人负责范围",
    "DORM_BUILDING": "本人负责范围",
    "SELF": "本人负责范围",
    "NONE": "无数据范围",
}


def _allowed_class_ids(db, user: dict):
    """返回 (allowed_class_ids, scope_shim)。allowed=None 仅当角色为 TENANT_ALL；
    未配范围的非管理角色返回**空集合**（fail-closed，绝不回退全租户）。统一走 StudentAffairsSecurityContext。"""
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(user, db)
    allowed = ctx.allowed_class_ids(db)
    mode = _MODE_OF.get(ctx.scope_type, "SCOPED")
    if ctx.scope_type == "NONE" or (
            ctx.scope_type in ("CLASS", "COLLEGE", "SELF") and not ctx.is_scope_configured):
        scope_label = "无数据范围"
    else:
        scope_label = _SCOPE_LABEL.get(ctx.scope_type, "本人负责范围")
    return allowed, {"mode": mode, "ctx": ctx, "scopeType": ctx.scope_type,
                     "scopeLabel": scope_label,
                     "isScopeConfigured": ctx.is_scope_configured}


# ═══════════ 学工首页 ═══════════

def get_dashboard(user: dict) -> dict:
    view = _resolve_view(user)
    # 待办口径复用统一待办服务（本人指派 + 范围内池待办；fail-closed；不回退全校）
    from app.services.workbench_todo_service import summary as todo_summary
    todo = int((todo_summary(user) or {}).get("pending") or 0)
    with session() as db:
        from app.models import SchoolClass, StudentProfile
        allowed, scope = _allowed_class_ids(db, user)
        stu_q = select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))
        cls_q = select(func.count()).select_from(SchoolClass).where(SchoolClass.tenant_id == _tid())
        if allowed is not None:
            scoped = allowed or {-1}  # 空集合用哨兵值避免 IN() 空表达式
            stu_q = stu_q.where(StudentProfile.class_id.in_(scoped))
            cls_q = cls_q.where(SchoolClass.id.in_(scoped))
        stu_total = db.scalar(stu_q) or 0
        cls_total = db.scalar(cls_q) or 0
        # 请假统计（真实聚合 affairs_status）
        from app.models import CsLeave
        leave_cond = [CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False)]
        if allowed is not None:
            leave_cond.append(CsLeave.student_id.in_(_students_in_classes(db, allowed)))
        pending_leave = db.scalar(select(func.count()).select_from(CsLeave).where(
            *leave_cond, CsLeave.affairs_status.in_(
                ["COUNSELOR_REVIEW", "COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW"]))) or 0
        overdue_leave = db.scalar(select(func.count()).select_from(CsLeave).where(
            *leave_cond, CsLeave.affairs_status == "OVERDUE")) or 0
        # 困难认定 / 奖助待审统计
        from app.models import AidApply, FundingApplication
        stu_ids = _students_in_classes(db, allowed) if allowed is not None else None
        aid_cond = [AidApply.tenant_id == _tid(), AidApply.is_deleted.is_(False),
                    AidApply.status.in_(["CLASS_REVIEW", "COUNSELOR_REVIEW", "COLLEGE_REVIEW",
                                         "SCHOOL_REVIEW", "PUBLICITY"])]
        fund_cond = [FundingApplication.tenant_id == _tid(), FundingApplication.is_deleted.is_(False),
                     FundingApplication.status.in_(["COUNSELOR_REVIEW", "COLLEGE_REVIEW",
                                                    "SCHOOL_REVIEW", "PUBLICITY"])]
        if stu_ids is not None:
            aid_cond.append(AidApply.student_id.in_(stu_ids))
            fund_cond.append(FundingApplication.student_id.in_(stu_ids))
        pending_aid = db.scalar(select(func.count()).select_from(AidApply).where(*aid_cond)) or 0
        pending_funding = db.scalar(select(func.count()).select_from(FundingApplication).where(*fund_cond)) or 0
        # 处分待审 / 在办风险统计
        from app.models import AffairsRiskRecord, DisciplineCase
        disc_cond = [DisciplineCase.tenant_id == _tid(), DisciplineCase.is_deleted.is_(False),
                     DisciplineCase.status.in_(["COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW",
                                                "SCHOOL_REVIEW", "REMOVE_REVIEW"])]
        risk_cond = [AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.is_deleted.is_(False),
                     AffairsRiskRecord.status.notin_(["CLOSED"])]
        if stu_ids is not None:
            disc_cond.append(DisciplineCase.student_id.in_(stu_ids))
            risk_cond.append(AffairsRiskRecord.student_id.in_(stu_ids))
        pending_disc = db.scalar(select(func.count()).select_from(DisciplineCase).where(*disc_cond)) or 0
        risk_open = db.scalar(select(func.count(func.distinct(AffairsRiskRecord.student_id)))
                              .select_from(AffairsRiskRecord).where(*risk_cond)) or 0
        # 下钻路径与首页统计同口径；宿舍异常无与学工范围对齐的可信统计，本轮不展示该指标
        cards = [
            {"key": "studentTotal", "label": "学生数(范围内)", "value": stu_total, "unit": "人",
             "drillPath": "/admin/student/list"},
            {"key": "classTotal", "label": "班级数", "value": cls_total, "unit": "个",
             "drillPath": "/admin/campus-service/classes"},
            {"key": "pendingTodo", "label": "待办", "value": todo, "unit": "件",
             "drillPath": "/admin/approval/todos"},
            {"key": "pendingLeave", "label": "待审请假", "value": pending_leave, "unit": "件",
             "drillPath": "/admin/campus-service/leave"},
            {"key": "overdueLeave", "label": "逾期未销假", "value": overdue_leave, "unit": "件",
             "drillPath": "/admin/campus-service/leave-ledger?status=OVERDUE"},
            {"key": "pendingAid", "label": "待审困难认定", "value": pending_aid, "unit": "件",
             "drillPath": "/admin/student-affairs/aid?status=REVIEW"},
            {"key": "pendingFunding", "label": "待审奖助", "value": pending_funding, "unit": "件",
             "drillPath": "/admin/student-affairs/funding?status=REVIEW"},
            {"key": "pendingDiscipline", "label": "待审处分", "value": pending_disc, "unit": "件",
             "drillPath": "/admin/student-affairs/discipline?status=REVIEW"},
            {"key": "riskStudents", "label": "风险学生", "value": risk_open, "unit": "人",
             "drillPath": "/admin/student-affairs/risk?status=OPEN"},
        ]
        return {
            "view": view,
            "viewLabel": _VIEW_LABEL[view],
            "scopeMode": scope["mode"],
            "scopeType": scope["scopeType"],
            "scopeLabel": scope["scopeLabel"],
            "updatedAt": _iso(datetime.now()),
            "summaryCards": cards,
            "moduleCards": [
                {"key": k, "label": label, "status": st,
                 "empty": st != "LIVE",
                 "emptyHint": "" if st == "LIVE" else "当前暂无相关记录"}
                for k, label, st in _MODULE_CARDS
            ],
        }


# ═══════════ 班级 / 班干部 ═══════════

def _cadre_row(r, student=None) -> dict:
    return {
        "cadreId": str(r.id), "classId": str(r.class_id), "studentId": str(r.student_id),
        # 班干部列表此前只回 studentId，PC 端只能显示内部主键；补 join 学生姓名/学号（历史欠账 §班级 ②）。
        "studentName": (student.real_name if student else "") or "",
        "studentNo": (student.student_no if student else "") or "",
        "position": r.position, "termCode": r.term_code or "", "status": r.status,
        "appointedAt": _iso(r.appointed_at), "removedAt": _iso(r.removed_at),
    }


def _audit(db, biz_type: str, biz_id, action: str, detail: str = "") -> None:
    """写学工域业务留痕（append-only）。班干部为 TRAIL 级，不落安全审计。"""
    from app.models import AffairsAuditTrail
    u = get_current_user_ctx() or {}
    db.add(AffairsAuditTrail(
        tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
        action=action, operator=str(u.get("userId") or ""), role_name=u.get("currentRoleCode"),
        detail=detail, occurred_at=datetime.utcnow()))


def _class_in_scope_or_403(db, class_id, user: dict):
    """校验班级存在且在数据范围内；越权抛 NO_DATA_SCOPE（全局 handler 自动写 PERMISSION_DENIED 审计）。"""
    from app.models import SchoolClass
    c = db.get(SchoolClass, int(class_id))
    if not c or c.tenant_id != _tid():
        raise not_found("班级不存在")
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is not None and int(class_id) not in allowed:
        raise AppException("NO_DATA_SCOPE", "该班级不在您的数据范围内")
    return c


def list_classes(user: dict) -> list[dict]:
    with session() as db:
        from app.models import SchoolClass
        allowed, _ = _allowed_class_ids(db, user)
        q = select(SchoolClass).where(SchoolClass.tenant_id == _tid())
        if allowed is not None:
            q = q.where(SchoolClass.id.in_(allowed or {-1}))
        rows = db.scalars(q.order_by(SchoolClass.id)).all()
        return [{"classId": str(c.id), "className": c.class_name, "grade": c.grade or "",
                 "majorId": str(c.major_id)} for c in rows]


def list_cadres(class_id, user: dict) -> list[dict]:
    """在任班干部名单。修复：此前不按 status 过滤，配合 remove_cadre 只置
    status=REMOVED（不做软删除 is_deleted）的既有设计，已免去成员会永久残留在「在任班干部」
    列表里，PC 前端 ClassProfileView.vue 也原样渲染出一个始终可点的「免去」按钮——不是越权
    问题，但会让辅导员误判在任情况。免去记录仍可经审计追溯，此处只收紧列表口径为在任成员。"""
    with session() as db:
        _class_in_scope_or_403(db, class_id, user)
        from app.models import AffairsClassCadre, StudentProfile
        rows = db.scalars(select(AffairsClassCadre).where(
            AffairsClassCadre.tenant_id == _tid(), AffairsClassCadre.class_id == int(class_id),
            AffairsClassCadre.status == "ACTIVE",
            AffairsClassCadre.is_deleted.is_(False)).order_by(AffairsClassCadre.id)).all()
        sids = {int(r.student_id) for r in rows if r.student_id}
        students = {s.id: s for s in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_(sids))).all()} if sids else {}
        return [_cadre_row(r, students.get(int(r.student_id))) for r in rows]


def add_cadre(class_id, body, user: dict) -> dict:
    with session() as db:
        _class_in_scope_or_403(db, class_id, user)
        from app.models import AffairsClassCadre
        dup = db.scalars(select(AffairsClassCadre).where(
            AffairsClassCadre.tenant_id == _tid(), AffairsClassCadre.class_id == int(class_id),
            AffairsClassCadre.position == body.position, AffairsClassCadre.status == "ACTIVE",
            AffairsClassCadre.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该班级该职务已有在任班干部")
        r = AffairsClassCadre(
            tenant_id=_tid(), class_id=int(class_id), student_id=int(body.studentId),
            position=body.position, term_code=body.termCode, appointed_at=datetime.utcnow(),
            status="ACTIVE", record_status="ACTIVE")
        db.add(r)
        db.flush()
        _audit(db, "CLASS_CADRE", r.id, "APPOINT",
               f"class={class_id},position={body.position},student={body.studentId}")
        db.commit()
        db.refresh(r)
        from app.models import StudentProfile
        return _cadre_row(r, db.get(StudentProfile, int(r.student_id)) if r.student_id else None)


def remove_cadre(cadre_id, user: dict, reason: str = "") -> dict:
    with session() as db:
        from app.models import AffairsClassCadre
        r = db.get(AffairsClassCadre, int(cadre_id))
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("班干部记录不存在")
        _class_in_scope_or_403(db, r.class_id, user)
        r.status = "REMOVED"
        r.removed_at = datetime.utcnow()
        r.version += 1
        _audit(db, "CLASS_CADRE", r.id, "REMOVE", reason)
        db.commit()
        return {"cadreId": str(r.id), "status": "REMOVED"}
