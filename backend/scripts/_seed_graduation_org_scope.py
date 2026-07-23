"""毕业设计学院/专业 claim 开箱种子（幂等）。

写入 TeacherStudentScope(COLLEGE/MAJOR)，并回填 GraduationStudent.college_id/major_id。
登录签发 JWT 时由 auth_service_db._inject_org_scope_claims 解析为 collegeId/majorId。

用法（backend 目录）：

  python -c "from app.db.session import get_sessionmaker; from _seed_graduation_org_scope import seed_graduation_org_scope; db=get_sessionmaker()(); print(seed_graduation_org_scope(db)); db.commit()"
"""
from __future__ import annotations

from sqlalchemy import select

from app.models import (
    College, GraduationStudent, Major, StudentProfile, TeacherStudentScope, User,
)

TID = 1000000000000000001

# teacher_key, teacher_name, role_code, scope_type, ref_value（学院名/专业名；None=取租户首个）
SCOPE_TARGETS = [
    ("e2e_college_secretary", "E2E学院秘书", "GD_COLLEGE_ADMIN", "COLLEGE", "E2E智能制造学院"),
    ("e2e_major_admin", "E2E专业负责人", "GD_MAJOR_ADMIN", "MAJOR", "E2E工业机器人技术"),
    ("college_admin01", "张晓明", "GD_COLLEGE_ADMIN", "COLLEGE", None),
    ("college_admin01", "张晓明", "COLLEGE_ADMIN", "COLLEGE", None),
]


def _ensure_scope_row(db, tenant_id: int, teacher_key: str, teacher_name: str,
                      role_code: str, scope_type: str, ref_value: str) -> str:
    row = db.scalars(select(TeacherStudentScope).where(
        TeacherStudentScope.tenant_id == tenant_id,
        TeacherStudentScope.teacher_key == teacher_key,
        TeacherStudentScope.role_code == role_code,
        TeacherStudentScope.scope_type == scope_type,
        TeacherStudentScope.ref_value == ref_value,
    )).first()
    if row:
        changed = False
        if row.is_deleted or row.status != "ACTIVE":
            row.is_deleted = False
            row.status = "ACTIVE"
            changed = True
        if (row.teacher_name or "") != teacher_name:
            row.teacher_name = teacher_name
            changed = True
        return "updated" if changed else "exists"
    db.add(TeacherStudentScope(
        tenant_id=tenant_id, teacher_key=teacher_key, teacher_name=teacher_name,
        role_code=role_code, scope_type=scope_type, ref_value=ref_value, status="ACTIVE",
    ))
    return "created"


def _resolve_college_name(db, tenant_id: int, preferred: str | None) -> str | None:
    if preferred:
        hit = db.scalars(select(College).where(
            College.tenant_id == tenant_id,
            College.college_name == preferred,
            College.is_deleted.is_(False),
        )).first()
        if hit:
            return hit.college_name
    first = db.scalars(select(College).where(
        College.tenant_id == tenant_id,
        College.is_deleted.is_(False),
    ).order_by(College.id)).first()
    return first.college_name if first else None


def _resolve_major_name(db, tenant_id: int, preferred: str | None) -> str | None:
    if preferred:
        hit = db.scalars(select(Major).where(
            Major.tenant_id == tenant_id,
            Major.major_name == preferred,
            Major.is_deleted.is_(False),
        )).first()
        if hit:
            return hit.major_name
    first = db.scalars(select(Major).where(
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.id)).first()
    return first.major_name if first else None


def _user_exists(db, tenant_id: int, login_name: str) -> bool:
    return db.scalars(select(User.id).where(
        User.tenant_id == tenant_id,
        User.login_name == login_name,
        User.is_deleted.is_(False),
    ).limit(1)).first() is not None


def backfill_graduation_student_org(db, tenant_id: int = TID) -> dict:
    """从学籍主档回填毕设学生 college_id/major_id；仍缺省则用租户首个学院/专业。"""
    college = db.scalars(select(College).where(
        College.tenant_id == tenant_id, College.is_deleted.is_(False),
    ).order_by(College.id)).first()
    major = db.scalars(select(Major).where(
        Major.tenant_id == tenant_id, Major.is_deleted.is_(False),
    ).order_by(Major.id)).first()
    default_college = str(college.id) if college else ""
    default_major = str(major.id) if major else ""

    updated = 0
    students = db.scalars(select(GraduationStudent).where(
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
    )).all()
    for stu in students:
        changed = False
        profile = db.get(StudentProfile, stu.student_id) if stu.student_id else None
        college_id = str(stu.college_id or "").strip()
        major_id = str(getattr(stu, "major_id", None) or "").strip()
        if not college_id and profile and profile.college_id:
            college_id = str(profile.college_id)
            changed = True
        if not major_id and profile and profile.major_id:
            major_id = str(profile.major_id)
            changed = True
        if not college_id and default_college:
            college_id = default_college
            changed = True
        if not major_id and default_major:
            major_id = default_major
            changed = True
        if changed:
            stu.college_id = college_id or None
            stu.major_id = major_id or None
            updated += 1
    return {"studentsChecked": len(students), "studentsUpdated": updated,
            "defaultCollegeId": default_college or None, "defaultMajorId": default_major or None}


def seed_graduation_org_scope(db, tenant_id: int = TID) -> dict:
    created = updated = skipped = 0
    details = []
    for teacher_key, teacher_name, role_code, scope_type, preferred_ref in SCOPE_TARGETS:
        if not _user_exists(db, tenant_id, teacher_key):
            skipped += 1
            details.append({"teacherKey": teacher_key, "status": "skipped_no_user"})
            continue
        if scope_type == "COLLEGE":
            ref = _resolve_college_name(db, tenant_id, preferred_ref)
        else:
            ref = _resolve_major_name(db, tenant_id, preferred_ref)
        if not ref:
            skipped += 1
            details.append({"teacherKey": teacher_key, "status": "skipped_no_org"})
            continue
        status = _ensure_scope_row(db, tenant_id, teacher_key, teacher_name, role_code, scope_type, ref)
        if status == "created":
            created += 1
        elif status == "updated":
            updated += 1
        else:
            skipped += 1
        details.append({"teacherKey": teacher_key, "role": role_code,
                        "scopeType": scope_type, "ref": ref, "status": status})

    backfill = backfill_graduation_student_org(db, tenant_id)
    return {"created": created, "updated": updated, "skipped": skipped,
            "details": details, "backfill": backfill}
