"""把 sandbox-school 的既有业务范围事实投影到新版角色授权范围表。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.services.role_assignment_scope_service import role_scope_policy


def _scope_name(scope_type: str, row) -> str:
    if scope_type == "COLLEGE":
        return row.college_name
    if scope_type == "MAJOR":
        return row.major_name
    if scope_type == "CLASS":
        return row.class_name
    return f"{row.real_name}（{row.student_no}）"


def reconcile_sandbox_role_assignment_scopes(db, tenant_id: int) -> dict:
    """幂等迁移旧 TeacherStudentScope，并补齐可唯一推导的心理逐生范围。"""
    from app.models import (
        AaTeachingTask,
        College,
        Major,
        PsyReferral,
        Role,
        RoleAssignmentScope,
        SchoolClass,
        StudentProfile,
        TeacherStudentScope,
        Tenant,
        User,
        UserRole,
    )

    tenant = db.get(Tenant, tenant_id)
    if tenant is None or str(tenant.tenant_code or "") != "sandbox-school":
        raise RuntimeError(f"只允许修复 sandbox-school，实际 tenant_id={tenant_id}")

    colleges = {
        int(row.id): row
        for row in db.scalars(select(College).where(
            College.tenant_id == tenant_id,
            College.status == "ACTIVE",
            College.is_deleted.is_(False),
        )).all()
    }
    college_by_name = {row.college_name: row for row in colleges.values()}
    majors = {
        int(row.id): row
        for row in db.scalars(select(Major).where(
            Major.tenant_id == tenant_id,
            Major.status == "ACTIVE",
            Major.is_deleted.is_(False),
        )).all()
    }
    major_by_name = {row.major_name: row for row in majors.values()}
    classes = {
        int(row.id): row
        for row in db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == tenant_id,
            SchoolClass.status == "ACTIVE",
            SchoolClass.is_deleted.is_(False),
        )).all()
    }
    class_by_name = {row.class_name: row for row in classes.values()}
    students = {
        int(row.id): row
        for row in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.status == "ACTIVE",
            StudentProfile.is_deleted.is_(False),
        )).all()
    }
    student_by_no = {row.student_no: row for row in students.values()}

    legacy_rows = list(db.scalars(select(TeacherStudentScope).where(
        TeacherStudentScope.tenant_id == tenant_id,
        TeacherStudentScope.status == "ACTIVE",
        TeacherStudentScope.is_deleted.is_(False),
    )).all())
    legacy_by_identity_role: dict[tuple[str, str], list] = {}
    for row in legacy_rows:
        role_code = str(row.role_code or "").upper()
        for identity in {str(row.teacher_key or ""), str(row.teacher_name or "")} - {""}:
            legacy_by_identity_role.setdefault((identity, role_code), []).append(row)

    existing = list(db.scalars(select(RoleAssignmentScope).where(
        RoleAssignmentScope.tenant_id == tenant_id,
    )).all())
    existing_by_key = {
        (int(row.user_role_id), str(row.scope_type).upper(), int(row.scope_id)): row
        for row in existing
    }
    already_scoped = {
        int(row.user_role_id)
        for row in existing
        if row.status == "ACTIVE" and not row.is_deleted
    }

    user_roles = list(db.execute(
        select(UserRole, User, Role)
        .join(User, User.id == UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserRole.tenant_id == tenant_id,
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            User.tenant_id == tenant_id,
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
            Role.tenant_id == tenant_id,
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        )
        .order_by(User.login_name, Role.role_code)
    ).all())
    inserted = 0
    revived = 0
    psychology_legacy_inserted = 0
    unresolved = []
    now = datetime.utcnow().replace(microsecond=0)
    policy_cache = {}

    def save_scope(user_role, user, role, scope_type: str, scope_row) -> None:
        nonlocal inserted, revived
        key = (int(user_role.id), scope_type, int(scope_row.id))
        target = existing_by_key.get(key)
        if target is None:
            target = RoleAssignmentScope(
                tenant_id=tenant_id,
                user_role_id=int(user_role.id),
                user_id=int(user.id),
                role_code=role.role_code,
                scope_type=scope_type,
                scope_id=int(scope_row.id),
                scope_name_snapshot=_scope_name(scope_type, scope_row),
                source_type="PROJECTED",
                status="ACTIVE",
                effective_at=now,
                reason="sandbox 既有业务范围投影到新版角色授权范围",
            )
            db.add(target)
            existing_by_key[key] = target
            inserted += 1
        elif target.is_deleted or target.status != "ACTIVE":
            target.is_deleted = False
            target.status = "ACTIVE"
            target.expires_at = None
            target.scope_name_snapshot = _scope_name(scope_type, scope_row)
            target.updated_at = now
            revived += 1

    for user_role, user, role in user_roles:
        if int(user_role.id) in already_scoped:
            continue
        policy = policy_cache.get(int(role.id))
        if policy is None:
            policy = role_scope_policy(db, role)
            policy_cache[int(role.id)] = policy
        if policy["scopeMode"] == "AUTO" or policy["scopeType"] == "SCHOOL":
            continue

        role_code = str(role.role_code).upper()
        candidates = []
        seen_legacy_ids = set()
        for identity in (user.login_name, user.real_name):
            for legacy in legacy_by_identity_role.get((str(identity), role_code), []):
                if int(legacy.id) not in seen_legacy_ids:
                    candidates.append(legacy)
                    seen_legacy_ids.add(int(legacy.id))

        resolved: list[tuple[str, object]] = []
        for legacy in candidates:
            legacy_type = str(legacy.scope_type or "").upper()
            ref = str(legacy.ref_value or "")
            if legacy_type == "COLLEGE" and ref in college_by_name:
                resolved.append(("COLLEGE", college_by_name[ref]))
            elif legacy_type == "MAJOR" and ref in major_by_name:
                resolved.append(("MAJOR", major_by_name[ref]))
            elif legacy_type == "CLASS" and ref in class_by_name:
                resolved.append(("CLASS", class_by_name[ref]))
            elif legacy_type in {"STUDENT", "PSY_STUDENT"} and ref in student_by_no:
                resolved.append(("STUDENT", student_by_no[ref]))

        # 心理老师的旧拓扑只到学院；从该学院真实学生中投影一个逐生授权，
        # 优先选择已有人工心理转介的学生，且同步旧敏感域消费者仍读取的范围表。
        if role_code == "PSYCHOLOGY_TEACHER" and not any(t == "STUDENT" for t, _ in resolved):
            college_ids = [
                int(college_by_name[str(row.ref_value)].id)
                for row in candidates
                if str(row.scope_type or "").upper() == "COLLEGE"
                and str(row.ref_value or "") in college_by_name
            ]
            if college_ids:
                referral_student_ids = set(db.scalars(select(PsyReferral.student_id).where(
                    PsyReferral.tenant_id == tenant_id,
                    PsyReferral.is_deleted.is_(False),
                )).all())
                scoped_students = sorted(
                    (row for row in students.values() if int(row.college_id or 0) in college_ids),
                    key=lambda row: (int(row.id) not in referral_student_ids, row.student_no),
                )
                if scoped_students:
                    student = scoped_students[0]
                    resolved.append(("STUDENT", student))
                    legacy = TeacherStudentScope(
                        tenant_id=tenant_id,
                        teacher_key=user.login_name,
                        teacher_name=user.real_name,
                        role_code=role_code,
                        scope_type="PSY_STUDENT",
                        ref_value=student.student_no,
                        status="ACTIVE",
                    )
                    db.add(legacy)
                    psychology_legacy_inserted += 1

        # 个别后加的学院管理兼岗没有旧范围时，以本人真实授课班级所属学院兜底；
        # 多学院任课只取稳定排序第一项，避免无依据扩成全校。
        if not resolved and policy["scopeType"] == "COLLEGE":
            college_ids = list(db.scalars(
                select(Major.college_id)
                .join(SchoolClass, SchoolClass.major_id == Major.id)
                .join(AaTeachingTask, AaTeachingTask.class_id == SchoolClass.id)
                .where(
                    AaTeachingTask.tenant_id == tenant_id,
                    AaTeachingTask.teacher_key == user.login_name,
                    AaTeachingTask.is_deleted.is_(False),
                    SchoolClass.tenant_id == tenant_id,
                    SchoolClass.is_deleted.is_(False),
                    Major.tenant_id == tenant_id,
                    Major.is_deleted.is_(False),
                )
                .distinct()
                .order_by(Major.college_id)
            ).all())
            if college_ids and int(college_ids[0]) in colleges:
                resolved.append(("COLLEGE", colleges[int(college_ids[0])]))

        allowed = set(policy["allowedScopeTypes"])
        resolved = [(scope_type, row) for scope_type, row in resolved if scope_type in allowed]
        if not resolved:
            unresolved.append({
                "loginName": user.login_name,
                "roleCode": role.role_code,
                "scopeType": policy["scopeType"],
            })
            continue
        for scope_type, scope_row in resolved:
            save_scope(user_role, user, role, scope_type, scope_row)

    db.flush()
    return {
        "inserted": inserted,
        "revived": revived,
        "psychologyLegacyStudentScopesInserted": psychology_legacy_inserted,
        "unresolved": unresolved,
    }
