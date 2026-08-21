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
from app.core.tenant_scoped import tenant_get
from app.models import (College, EmpAuditTrail, EmpFollowup, EmpMaterial, EmpStudent,
                        Major, SchoolClass, StudentProfile)
from app.modules.employment.services import employment_material_evidence_service as base_ev
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


def _class_filter_condition(class_id):
    """班级筛选沿用与 dataScope 相同的身份事实口径：绑定主档看当前班级，legacy 才看快照。"""
    raw = str(class_id or "").strip()
    if not raw:
        return None
    try:
        cid = int(raw)
    except (TypeError, ValueError):
        return EmpStudent.id == -1
    profile_ids = select(StudentProfile.id).where(
        StudentProfile.tenant_id == _tid(),
        StudentProfile.class_id == cid,
        StudentProfile.is_deleted.is_(False),
    )
    return or_(
        and_(EmpStudent.student_id.is_not(None), EmpStudent.student_id.in_(profile_ids)),
        and_(EmpStudent.student_id.is_(None), EmpStudent.class_id == raw),
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
        # tenant_get：跨租户 sid 直接当不存在处理，不再依赖 _assert_emp_student
        # 里那道二次校验单独兜底（两层校验对同一事实互为冗余，不冲突）。
        emp = tenant_get(db, EmpStudent, int(sid))
    except (TypeError, ValueError):
        raise not_found("就业记录不存在或不在当前数据范围内")
    return _assert_emp_student(db, emp, user)


def _assert_emp_ids(db, ids, user: dict) -> list[EmpStudent]:
    if not ids:
        raise AppException("VALIDATION_ERROR", "请选择至少一条记录")
    return [_assert_emp_id(db, sid, user) for sid in ids]


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
            cond.append(_class_filter_condition(class_id))
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
    """详情的 scope 裁决与详情读取必须共用一个 session，避免校验后转班产生并发越权读。"""
    with session() as db:
        student = _assert_emp_id(db, sid, user)
        materials = db.scalars(select(EmpMaterial).where(
            EmpMaterial.tenant_id == _tid(),
            EmpMaterial.emp_student_id == student.id,
            EmpMaterial.is_deleted.is_(False),
        ).order_by(EmpMaterial.id.desc())).all()
        followups = db.scalars(select(EmpFollowup).where(
            EmpFollowup.tenant_id == _tid(),
            EmpFollowup.emp_student_id == student.id,
            EmpFollowup.is_deleted.is_(False),
        ).order_by(EmpFollowup.id.desc())).all()
        logs = db.scalars(select(EmpAuditTrail).where(
            EmpAuditTrail.tenant_id == _tid(),
            EmpAuditTrail.biz_type == "RECORD",
            EmpAuditTrail.biz_id == str(student.id),
        ).order_by(EmpAuditTrail.id.desc()).limit(20)).all()
        profiles = shadow.load_profiles(db, [student])
        return {
            "student": base._stu_row(student, db=db, profiles=profiles),
            "materials": base._mat_rows(db, materials, {int(student.id): student} if student else None),
            "followUps": [base._fu_row(item, student) for item in followups],
            "auditLogs": [base._log_row(item) for item in logs],
        }


def create_student(body: dict, *, user: dict) -> dict:
    # scope 校验与创建使用同一事务，避免校验后学生恰好异动导致越范围写入。
    with session() as db:
        profile = shadow.resolve_profile_for_shadow(
            db, _tid(), domain_label="就业台账",
            student_id=body.get("studentId") or body.get("profileStudentId"),
            student_no=body.get("studentNo"),
        )
        _ctx(db, user).require_student(db, int(profile.id))
        result = base.create_student(body, db=db)
        db.commit()
        return result


def update_student(sid, body: dict, *, user: dict) -> dict:
    with session() as db:
        s = _assert_emp_id(db, sid, user)
        shadow.assert_identity_immutable(db, s, body, "就业台账")
        for key, column in {
            "destinationType": "destination_type", "companyName": "company_name",
            "jobTitle": "job_title", "salaryRange": "salary_range", "signDate": "sign_date",
            "employmentTeacher": "employment_teacher",
        }.items():
            if body.get(key) is not None:
                setattr(s, column, body[key])
        s.version = int(s.version or 0) + 1
        base._audit(db, "RECORD", s.id, "编辑就业记录")
        db.commit()
        return {"id": str(s.id)}


def void_student(sid, reason, *, user: dict) -> dict:
    text = str(reason or "").strip()
    if len(text) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        s = _assert_emp_id(db, sid, user)
        s.record_status = "VOIDED"
        s.void_reason = text
        s.is_deleted = True
        s.version = int(s.version or 0) + 1
        base._audit(db, "RECORD", s.id, "作废就业记录", text)
        db.commit()
        return {"id": str(s.id)}


def batch_mark_destination(ids, destination_type, *, user: dict) -> dict:
    if destination_type not in base.L_DEST:
        raise AppException("VALIDATION_ERROR", "非法去向类型")
    with session() as db:
        rows = _assert_emp_ids(db, ids, user)
        for s in rows:
            s.destination_type = destination_type
            s.verify_status = "PENDING_VERIFY"
            s.version = int(s.version or 0) + 1
            if destination_type != "UNEMPLOYED":
                base._todo_done_followup(db, s.id)
            base._audit(db, "RECORD", s.id, "批量标记去向", base.L_DEST[destination_type])
        db.commit()
        return {"count": len(rows)}


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
        return base._mat_rows(db, rows, students), total


def get_destination_verification(sid, *, user: dict) -> dict:
    """教师 PC 去向核验工作区数据（TP-E02）。

    授权走 PC 自己的数据范围权威 `_assert_emp_id`；证据判定与门槛复用共享
    domain 权威，保证与教师小程序看到的是同一套结论。
    """
    from app.modules.employment.services import employment_destination_verification_service as verify_authority

    with session() as db:
        emp = _assert_emp_id(db, sid, user)
        materials = db.scalars(select(EmpMaterial).where(
            EmpMaterial.tenant_id == _tid(),
            EmpMaterial.emp_student_id == emp.id,
            EmpMaterial.is_deleted.is_(False),
        ).order_by(EmpMaterial.id.desc())).all()
        formal_approved = verify_authority.count_formal_approved_materials(db, emp)
        verify_status = str(emp.verify_status or "PENDING_VERIFY").upper()
        can_verify = (
            formal_approved > 0
            and verify_status != "VERIFIED"
            and str(emp.destination_type or "").upper() != "UNEMPLOYED"
        )
        profiles = shadow.load_profiles(db, [emp])
        return {
            "student": base._stu_row(emp, db=db, profiles=profiles),
            "materials": base._mat_rows(db, materials, {int(emp.id): emp}),
            "verifyStatus": verify_status,
            "verifyStatusLabel": base.L_VERIFY.get(verify_status, verify_status),
            "formalApprovedCount": formal_approved,
            "expectedVersion": int(emp.version or 0),
            "allowedActions": (["VERIFY"] if can_verify else []) + (
                ["RETURN"] if verify_status != "RETURNED" else []),
            # 不能操作时给出可执行的原因，而不是只把按钮置灰。
            "blockedReason": (
                "" if can_verify else
                "该学生去向为未就业，没有可核验去向"
                if str(emp.destination_type or "").upper() == "UNEMPLOYED" else
                "该去向已核验通过" if verify_status == "VERIFIED" else
                "至少需要 1 份已审核通过且具有正式 FileBinding 的安全材料才能核验通过"
            ),
        }


def review_destination_verification(sid, body: dict, *, user: dict) -> dict:
    """教师 PC 执行去向核验 / 退回补正（TP-E02）。

    与教师小程序共用同一 domain 命令：状态机、证据门槛、乐观锁、审计完全一致，
    差别只在授权用各自端的数据范围权威。
    """
    from app.modules.employment.services import employment_destination_verification_service as verify_authority

    body = body or {}
    with session() as db:
        emp = _assert_emp_id(db, sid, user)
        result = verify_authority.review(
            db, emp,
            action=body.get("action"),
            comment=body.get("comment") or "",
            expected_version=body.get("expectedVersion"),
        )
        db.commit()
        return result


def get_material_detail(mid, *, user: dict) -> dict:
    with session() as db:
        material, emp = _assert_material(db, mid, user)
        logs = db.scalars(select(EmpAuditTrail).where(
            EmpAuditTrail.tenant_id == _tid(),
            EmpAuditTrail.biz_type == "MATERIAL",
            EmpAuditTrail.biz_id == str(material.id),
        ).order_by(EmpAuditTrail.id.desc()).limit(30)).all()
        profiles = shadow.load_profiles(db, [emp])
        # TP-E03：材料详情必须给出正式文件描述符（fileId/bindingId/scanStatus/
        # fileVersion），老师才可能在审核前看到正式原文；没有正式绑定时
        # file=None + legacyFileNameOnly=True，页面据此标注"历史文本记录"。
        facts = base_ev.resolve_evidence(db, [material.id])
        return {
            "material": base._mat_row(material, emp, facts.get(int(material.id))),
            "student": base._stu_row(emp, db=db, profiles=profiles),
            "auditLogs": [base._log_row(x) for x in logs],
        }


def approve_material(mid, comment="", *, user: dict) -> dict:
    """材料审核通过 —— 委派给唯一权威 `employment_runtime_material_service`。

    PR #183 把 PC 材料审核的权威搬到了 `employment_runtime_material_service`
    （正式路由 `routers/employment.py` 已改调那一支），本函数就此失去调用方，
    但仍留着一份逐字重复的实现。留着重复实现的风险是真实的：将来任何人把它
    接回去，就会绕过那份带显式说明的兼容契约（材料通过同时置
    `verify_status=VERIFIED`），两条路径一旦漂移就是端间事实分叉。

    这里不删除符号（保持向后兼容，可能有动态调用），改为委派，保证无论走哪条
    路径，行为都由同一个权威决定。
    """
    from app.modules.employment.services import employment_runtime_material_service

    return employment_runtime_material_service.approve_material(mid, comment, user=user)


def return_material(mid, reason, *, user: dict) -> dict:
    text = str(reason or "").strip()
    if len(text) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        material, emp = _assert_material(db, mid, user)
        before = material.status
        operator, _ = base._op()
        material.status = "RETURNED"
        material.reviewer = operator
        material.review_time = datetime.utcnow()
        material.return_reason = text
        material.version = int(material.version or 0) + 1
        emp.material_status = "RETURNED"
        base._audit(db, "MATERIAL", material.id, "退回材料", text, before, "RETURNED")
        db.commit()
        return {"id": str(material.id), "status": "RETURNED"}


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
    with session() as db:
        rows = _assert_emp_ids(db, ids, user)
        for s in rows:
            s.destination_type = "SIGNED"
            s.verify_status = "PENDING_VERIFY"
            s.version = int(s.version or 0) + 1
            base._todo_done_followup(db, s.id)
            base._audit(db, "RECORD", s.id, "标记已就业")
        db.commit()
        return {"count": len(rows)}


def mark_key_help(ids, *, user: dict):
    with session() as db:
        rows = _assert_emp_ids(db, ids, user)
        for s in rows:
            s.help_level = "KEY_HELP"
            s.risk_level = "HIGH"
            s.version = int(s.version or 0) + 1
            base._audit(db, "RECORD", s.id, "标记重点帮扶")
        db.commit()
        return {"count": len(rows)}


def assign_teacher(ids, teacher, *, user: dict):
    text = str(teacher or "").strip()
    if not text:
        raise AppException("VALIDATION_ERROR", "就业老师必填")
    with session() as db:
        rows = _assert_emp_ids(db, ids, user)
        assignee_id = base._resolve_teacher_user_id(db, text)
        for s in rows:
            s.employment_teacher = text
            s.version = int(s.version or 0) + 1
            if assignee_id and base._needs_followup(s):
                base._todo_upsert_followup(db, s, assignee_id)
            base._audit(db, "RECORD", s.id, "分配就业老师")
        db.commit()
        return {"count": len(rows)}


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
    content = str(body.get("content") or "").strip()
    if not body.get("studentId") or not content:
        raise AppException("VALIDATION_ERROR", "学生、跟进内容必填")
    with session() as db:
        s = _assert_emp_id(db, body.get("studentId"), user)
        operator, _ = base._op()
        followup = EmpFollowup(
            tenant_id=_tid(), emp_student_id=s.id, way=body.get("way") or "PHONE",
            content=content, result=body.get("result"), next_plan=body.get("nextPlan"),
            operator=operator, status="OPEN", follow_time=datetime.utcnow(),
        )
        db.add(followup)
        s.last_follow_up_time = datetime.utcnow()
        s.follow_up_count = int(s.follow_up_count or 0) + 1
        base._audit(db, "FOLLOWUP", s.id, "新增就业跟进", content)
        db.commit()
        db.refresh(followup)
        return {"id": str(followup.id)}


def void_followup(fid, reason, *, user: dict) -> dict:
    text = str(reason or "").strip()
    if len(text) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        followup, _ = _assert_followup(db, fid, user)
        followup.status = "VOIDED"
        followup.void_reason = text
        followup.is_deleted = True
        followup.version = int(followup.version or 0) + 1
        base._audit(db, "FOLLOWUP", followup.id, "作废跟进", text)
        db.commit()
        return {"id": str(followup.id)}


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