"""就业中心正式运行时服务（A3 / P0-05）。

目标：正式 PC 路由只消费真实数据库事实，并统一继承 StudentAffairsSecurityContext 的
CLASS/COLLEGE/STUDENT/TENANT_ALL 数据范围。未配置范围 fail-closed，绝不回退全校。
底层 employment_service 继续承载成熟事务/审计逻辑；本层负责正式入口的范围裁决、
SQL 层分页与正式材料详情聚合。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, not_found
from app.models import (College, EmpAuditTrail, EmpFollowup, EmpMaterial, EmpStudent,
                        Major, SchoolClass, StudentProfile)
from app.modules.employment.services import employment_service as base
from app.services import shadow_student_service as shadow
from app.services.db_service import _iso, _tid, session


def _ctx(db, user: dict):
    return build_affairs_context(user or {}, db)


def _scope_condition(db, user: dict):
    """返回 EmpStudent 的 SQL scope 条件；None 表示 TENANT_ALL。"""
    ctx = _ctx(db, user)
    if ctx.scope_type == "TENANT_ALL":
        return None
    if ctx.scope_type in {"NONE", "SELF", "DORM_BUILDING"}:
        return EmpStudent.id == -1
    if ctx.scope_type == "STUDENT":
        ids = {int(i) for i in (ctx.psychology_student_ids | ctx.student_ids) if i}
        if not ids:
            return EmpStudent.id == -1
        return EmpStudent.student_id.in_(ids)

    class_ids = ctx.allowed_class_ids(db)
    if not class_ids:
        return EmpStudent.id == -1
    class_ids = {int(i) for i in class_ids}
    # 已绑定主档必须按主档“当前班级”裁决；只有未绑定 legacy 行才允许按就业快照 class_id 收敛。
    # 否则学生转班后，旧就业快照仍可能把他暴露给原班辅导员，形成“列表可见、详情 403”的事实裂缝。
    profile_ids = select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.class_id.in_(class_ids),
        StudentProfile.is_deleted.is_(False),
    )
    return or_(
        and_(EmpStudent.student_id.is_not(None), EmpStudent.student_id.in_(profile_ids)),
        and_(EmpStudent.student_id.is_(None), EmpStudent.class_id.in_([str(i) for i in class_ids])),
    )


def _assert_emp_student(db, emp: EmpStudent | None, user: dict) -> EmpStudent:
    if not emp or emp.is_deleted or int(emp.tenant_id) != int(_tid()):
        raise not_found("就业记录不存在或不在当前数据范围内")
    ctx = _ctx(db, user)
    if ctx.scope_type == "TENANT_ALL":
        return emp
    if emp.student_id:
        ctx.require_student(db, int(emp.student_id))
        return emp
    # 精确 STUDENT scope 不能把“同班级的未绑定历史行”推断成可见，否则会从点名授权放大成班级授权。
    if ctx.scope_type == "STUDENT":
        raise no_data_scope("该历史就业记录未绑定学生主档，无法证明属于您的点名学生范围")
    allowed = ctx.allowed_class_ids(db)
    if not allowed:
        raise no_data_scope("该就业记录不在您的数据范围内")
    try:
        class_id = int(emp.class_id or 0)
    except (TypeError, ValueError):
        class_id = 0
    if class_id not in allowed:
        raise no_data_scope("该就业记录不在您的数据范围内")
    return emp


def _assert_emp_id(db, sid, user: dict) -> EmpStudent:
    try:
        emp = db.get(EmpStudent, int(sid))
    except (TypeError, ValueError):
        raise not_found("就业记录不存在或不在当前数据范围内")
    return _assert_emp_student(db, emp, user)


def _assert_emp_ids(ids, user: dict) -> None:
    if not ids:
        raise AppException("VALIDATION_ERROR", "请选择至少一条记录")
    with session() as db:
        for sid in ids:
            _assert_emp_id(db, sid, user)


def _assert_material(db, mid, user: dict) -> tuple[EmpMaterial, EmpStudent]:
    try:
        material = db.get(EmpMaterial, int(mid))
    except (TypeError, ValueError):
        material = None
    if not material or material.is_deleted or int(material.tenant_id) != int(_tid()):
        raise not_found("材料不存在或不在当前数据范围内")
    emp = _assert_emp_id(db, material.emp_student_id, user)
    return material, emp


def _assert_followup(db, fid, user: dict) -> tuple[EmpFollowup, EmpStudent]:
    try:
        followup = db.get(EmpFollowup, int(fid))
    except (TypeError, ValueError):
        followup = None
    if not followup or followup.is_deleted or int(followup.tenant_id) != int(_tid()):
        raise not_found("跟进记录不存在或不在当前数据范围内")
    emp = _assert_emp_id(db, followup.emp_student_id, user)
    return followup, emp


def _page_query(db, stmt, count_stmt, page: int, ps: int):
    total = int(db.scalar(count_stmt) or 0)
    rows = db.scalars(stmt.offset((max(1, page) - 1) * ps).limit(ps)).all()
    return rows, total


def list_students(page, ps, *, user: dict, keyword=None, class_id=None,
                  destination_type=None, verify_status=None, help_level=None):
    with session() as db:
        cond = [
            EmpStudent.tenant_id == _tid(),
            EmpStudent.is_deleted.is_(False),
            EmpStudent.record_status == "ACTIVE",
        ]
        scope = _scope_condition(db, user)
        if scope is not None:
            cond.append(scope)
        if class_id:
            cond.append(EmpStudent.class_id == str(class_id))
        if destination_type:
            cond.append(EmpStudent.destination_type == destination_type)
        if verify_status:
            cond.append(EmpStudent.verify_status == verify_status)
        if help_level:
            cond.append(EmpStudent.help_level == help_level)
        if keyword and str(keyword).strip():
            text = f"%{str(keyword).strip()}%"
            cond.append(or_(EmpStudent.name.like(text), EmpStudent.student_no.like(text),
                            EmpStudent.company_name.like(text)))
        stmt = select(EmpStudent).where(*cond).order_by(EmpStudent.id.desc())
        count_stmt = select(func.count()).select_from(EmpStudent).where(*cond)
        rows, total = _page_query(db, stmt, count_stmt, page, ps)
        profiles, cache = shadow.load_profiles(db, rows), {}
        return [base._stu_row(r, db=db, profiles=profiles, cache=cache) for r in rows], total


def get_student_detail(sid, *, user: dict) -> dict:
    with session() as db:
        _assert_emp_id(db, sid, user)
    return base.get_student_detail(sid)


def create_student(body: dict, *, user: dict) -> dict:
    # 先按主档校验当前用户是否可管理目标学生；底层再次解析主档并在独立事务写入。
    with session() as db:
        profile = shadow.resolve_profile_for_shadow(
            db, _tid(), domain_label="就业台账",
            student_id=body.get("studentId") or body.get("profileStudentId"),
            student_no=body.get("studentNo"),
        )
        _ctx(db, user).require_student(db, int(profile.id))
    return base.create_student(body)


def update_student(sid, body: dict, *, user: dict) -> dict:
    with session() as db:
        _assert_emp_id(db, sid, user)
    return base.update_student(sid, body)


def void_student(sid, reason, *, user: dict) -> dict:
    with session() as db:
        _assert_emp_id(db, sid, user)
    return base.void_student(sid, reason)


def batch_mark_destination(ids, destination_type, *, user: dict) -> dict:
    _assert_emp_ids(ids, user)
    return base.batch_mark_destination(ids, destination_type)


def list_materials(page, ps, *, user: dict, keyword=None, status=None, material_type=None):
    with session() as db:
        cond = [EmpMaterial.tenant_id == _tid(), EmpMaterial.is_deleted.is_(False),
                EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False)]
        scope = _scope_condition(db, user)
        if scope is not None:
            cond.append(scope)
        if status:
            cond.append(EmpMaterial.status == status)
        if material_type:
            cond.append(EmpMaterial.material_type == material_type)
        if keyword and str(keyword).strip():
            text = f"%{str(keyword).strip()}%"
            cond.append(or_(EmpStudent.name.like(text), EmpStudent.student_no.like(text),
                            EmpMaterial.file_name.like(text)))
        join_cond = EmpMaterial.emp_student_id == EmpStudent.id
        stmt = select(EmpMaterial).join(EmpStudent, join_cond).where(*cond).order_by(EmpMaterial.id.desc())
        count_stmt = select(func.count()).select_from(EmpMaterial).join(EmpStudent, join_cond).where(*cond)
        rows, total = _page_query(db, stmt, count_stmt, page, ps)
        students = base._emp_students_by_ids(db, rows)
        return [base._mat_row(m, students.get(int(m.emp_student_id))) for m in rows], total


def get_material_detail(mid, *, user: dict) -> dict:
    with session() as db:
        material, emp = _assert_material(db, mid, user)
        logs = db.scalars(select(EmpAuditTrail).where(
            EmpAuditTrail.tenant_id == _tid(),
            EmpAuditTrail.biz_type == "MATERIAL",
            EmpAuditTrail.biz_id == str(material.id),
        ).order_by(EmpAuditTrail.id.desc()).limit(30)).all()
        profiles = shadow.load_profiles(db, [emp])
        return {
            "material": base._mat_row(material, emp),
            "student": base._stu_row(emp, db=db, profiles=profiles),
            "auditLogs": [base._log_row(x) for x in logs],
        }


def approve_material(mid, comment="", *, user: dict) -> dict:
    with session() as db:
        _assert_material(db, mid, user)
    return base.approve_material(mid, comment)


def return_material(mid, reason, *, user: dict) -> dict:
    with session() as db:
        _assert_material(db, mid, user)
    return base.return_material(mid, reason)


def list_unemployed(page, ps, *, user: dict, keyword=None, help_level=None, risk_level=None):
    with session() as db:
        cond = [EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False),
                EmpStudent.record_status == "ACTIVE", EmpStudent.destination_type == "UNEMPLOYED"]
        scope = _scope_condition(db, user)
        if scope is not None:
            cond.append(scope)
        if help_level:
            cond.append(EmpStudent.help_level == help_level)
        if risk_level:
            cond.append(EmpStudent.risk_level == risk_level)
        if keyword and str(keyword).strip():
            text = f"%{str(keyword).strip()}%"
            cond.append(or_(EmpStudent.name.like(text), EmpStudent.student_no.like(text)))
        stmt = select(EmpStudent).where(*cond).order_by(EmpStudent.id.desc())
        count_stmt = select(func.count()).select_from(EmpStudent).where(*cond)
        rows, total = _page_query(db, stmt, count_stmt, page, ps)
        profiles, cache = shadow.load_profiles(db, rows), {}
        items = [{**base._stu_row(r, db=db, profiles=profiles, cache=cache),
                  "assignedTeacher": r.employment_teacher or "未分配"} for r in rows]
        return items, total


def mark_employed(ids, *, user: dict):
    _assert_emp_ids(ids, user)
    return base.mark_employed(ids)


def mark_key_help(ids, *, user: dict):
    _assert_emp_ids(ids, user)
    return base.mark_key_help(ids)


def assign_teacher(ids, teacher, *, user: dict):
    _assert_emp_ids(ids, user)
    return base.assign_teacher(ids, teacher)


def list_followups(page, ps, *, user: dict, keyword=None, status=None):
    with session() as db:
        cond = [EmpFollowup.tenant_id == _tid(), EmpFollowup.is_deleted.is_(False),
                EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False)]
        scope = _scope_condition(db, user)
        if scope is not None:
            cond.append(scope)
        if status:
            cond.append(EmpFollowup.status == status)
        if keyword and str(keyword).strip():
            text = f"%{str(keyword).strip()}%"
            cond.append(or_(EmpStudent.name.like(text), EmpStudent.student_no.like(text),
                            EmpFollowup.content.like(text)))
        join_cond = EmpFollowup.emp_student_id == EmpStudent.id
        stmt = select(EmpFollowup).join(EmpStudent, join_cond).where(*cond).order_by(EmpFollowup.id.desc())
        count_stmt = select(func.count()).select_from(EmpFollowup).join(EmpStudent, join_cond).where(*cond)
        rows, total = _page_query(db, stmt, count_stmt, page, ps)
        students = base._emp_students_by_ids(db, rows)
        return [base._fu_row(f, students.get(int(f.emp_student_id))) for f in rows], total


def create_followup(body: dict, *, user: dict) -> dict:
    with session() as db:
        _assert_emp_id(db, body.get("studentId"), user)
    return base.create_followup(body)


def void_followup(fid, reason, *, user: dict) -> dict:
    with session() as db:
        _assert_followup(db, fid, user)
    return base.void_followup(fid, reason)


def get_filter_options(*, user: dict) -> dict:
    """只返回当前 dataScope 内真实组织选项；不再下发演示学院/班级。"""
    with session() as db:
        ctx = _ctx(db, user)
        allowed = ctx.allowed_class_ids(db)
        if ctx.scope_type == "TENANT_ALL":
            class_stmt = select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False), SchoolClass.status == "ACTIVE")
        elif not allowed:
            return {"classes": [], "colleges": [], "grades": []}
        else:
            class_stmt = select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(allowed),
                SchoolClass.is_deleted.is_(False), SchoolClass.status == "ACTIVE")
        classes = db.scalars(class_stmt.order_by(SchoolClass.class_name)).all()
        major_ids = {int(c.major_id) for c in classes if c.major_id}
        majors = db.scalars(select(Major).where(Major.tenant_id == _tid(), Major.id.in_(major_ids))).all() if major_ids else []
        college_ids = {int(m.college_id) for m in majors if m.college_id}
        colleges = db.scalars(select(College).where(College.tenant_id == _tid(), College.id.in_(college_ids))).all() if college_ids else []
        profile_cond = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        if classes:
            profile_cond.append(StudentProfile.class_id.in_([c.id for c in classes]))
        elif ctx.scope_type != "TENANT_ALL":
            return {"classes": [], "colleges": [], "grades": []}
        grades = sorted({str(g) for g in db.scalars(select(StudentProfile.grade).where(*profile_cond)).all() if g})
        return {
            "classes": [{"value": str(c.id), "label": c.class_name} for c in classes],
            "colleges": [{"value": str(c.id), "label": c.college_name} for c in colleges],
            "grades": [{"value": g, "label": g} for g in grades],
        }


def get_dashboard(*, user: dict) -> dict:
    with session() as db:
        cond = [EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False),
                EmpStudent.record_status == "ACTIVE"]
        scope = _scope_condition(db, user)
        if scope is not None:
            cond.append(scope)
        rows = db.scalars(select(EmpStudent).where(*cond)).all()
        total = len(rows)
        implemented = sum(1 for r in rows if r.destination_type != "UNEMPLOYED")
        unemployed = total - implemented
        key_help = sum(1 for r in rows if r.help_level == "KEY_HELP")
        emp_ids = [int(r.id) for r in rows]
        pend_mat = 0
        if emp_ids:
            pend_mat = int(db.scalar(select(func.count()).select_from(EmpMaterial).where(
                EmpMaterial.tenant_id == _tid(), EmpMaterial.emp_student_id.in_(emp_ids),
                EmpMaterial.status.in_(["SUBMITTED", "REVIEWING"]), EmpMaterial.is_deleted.is_(False))) or 0)
        rate = f"{(implemented / total * 100):.1f}%" if total else "0%"
        dist: dict[str, int] = {}
        for row in rows:
            dist[row.destination_type] = dist.get(row.destination_type, 0) + 1
        return {
            "batchName": "就业服务数据概览",
            "batchPeriod": "按当前账号数据范围实时统计",
            "updateTime": _iso(datetime.utcnow()),
            "kpis": [
                {"label": "就业台账人数", "value": str(total), "trend": "当前数据范围", "trendQuality": "neutral"},
                {"label": "去向已落实", "value": str(implemented), "trend": f"落实率 {rate}", "trendQuality": "good"},
                {"label": "未就业", "value": str(unemployed), "trend": f"待帮扶 {unemployed}", "trendQuality": "bad" if unemployed else "good"},
                {"label": "重点帮扶", "value": str(key_help), "trend": "", "trendQuality": "bad" if key_help else "good"},
                {"label": "材料待审核", "value": str(pend_mat), "trend": "", "trendQuality": "neutral"},
            ],
            "destinationDist": [{"label": base.L_DEST.get(k, k), "value": v} for k, v in dist.items()],
            "todos": [
                {"id": "materials", "label": "材料待审核", "value": pend_mat, "link": "materials"},
                {"id": "unemployed", "label": "未就业帮扶", "value": unemployed, "link": "unemployed"},
            ],
            "flow": [], "collegeRates": [], "riskAlerts": [],
        }