#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(
    str(ROOT / "scripts/maintenance/fix_abcd_regression_contracts_round2.py"),
    run_name="__main__",
)


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) < count:
        raise SystemExit(f"round3 expected snippet not found: {path}\n---\n{old[:600]}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")
    print(f"round3 patched {path}")


# 1) 课堂考勤：测试直接建立正式教学班、LOCKED名单版本和成员事实，
# 避免用不完整的教学任务夹具绕过当前生产名单合同。
replace(
    "backend/tests/test_mobile_attendance.py",
    '''def _seed_teaching_task(class_id, teacher_key, tenant_id=MAIN):
    """构造当前学期正式教学任务；teacher_key 与 token 的稳定 userId 完全一致。"""
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=tenant_id, year_code="2026-2027", term_no=1,
            term_name="2026-2027学年第一学期",
            start_date=datetime(2026, 1, 1), end_date=datetime(2026, 12, 31),
            teaching_weeks=20, is_current=True, status="PUBLISHED")
        db.add(term); db.flush()
        batch = AaTeachingTaskBatch(
            tenant_id=tenant_id, term_id=term.id,
            batch_name="考勤测试教学任务批次", status="APPROVED")
        db.add(batch); db.flush()
        task = AaTeachingTask(
            tenant_id=tenant_id, batch_id=batch.id, course_id=1, class_id=class_id,
            course_name="测试课程", teacher_key=f"u-{teacher_key}",
            teacher_name=teacher_key, status="READY")
        db.add(task); db.flush()
        task_id = task.id
        db.commit()
        return task_id
    finally:
        db.close()
''',
    '''def _seed_teaching_task(class_id, teacher_key, tenant_id=MAIN):
    """建立当前学期教学任务及其正式LOCKED教学班名单，返回真实 taskId。"""
    import hashlib
    from datetime import datetime
    from app.db.session import get_sessionmaker
    from app.models import (
        AaTeachingClass, AaTeachingClassMember, AaTeachingClassRosterVersion,
        AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch, AaTerm,
        StudentProfile,
    )
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=tenant_id, year_code="2026-2027", term_no=1,
            term_name="2026-2027学年第一学期",
            start_date=datetime(2026, 1, 1), end_date=datetime(2026, 12, 31),
            teaching_weeks=20, is_current=True, status="PUBLISHED")
        db.add(term); db.flush()
        batch = AaTeachingTaskBatch(
            tenant_id=tenant_id, term_id=term.id,
            batch_name="考勤测试教学任务批次", status="APPROVED")
        db.add(batch); db.flush()
        task = AaTeachingTask(
            tenant_id=tenant_id, batch_id=batch.id, course_id=1, class_id=class_id,
            course_name="测试课程", teacher_key=f"u-{teacher_key}",
            teacher_name=teacher_key, status="READY")
        db.add(task); db.flush()

        student_ids = [
            int(value) for (value,) in db.query(StudentProfile.id).filter(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.class_id == int(class_id),
                StudentProfile.is_deleted.is_(False),
            ).order_by(StudentProfile.student_no, StudentProfile.id).all()
        ]
        assert student_ids, "考勤测试行政班必须存在学生"
        teaching_class = AaTeachingClass(
            tenant_id=tenant_id, teaching_task_id=task.id, term_id=term.id,
            course_id=task.course_id, class_code=f"TC-{term.id}-{task.id}",
            class_name=f"{task.course_name} · 考勤测试班", class_type="ADMIN",
            source_type="TEACHING_TASK", source_id=task.id,
            capacity=len(student_ids), current_roster_version_no=0,
            roster_status="DRAFT", status="ACTIVE", source_snapshot_json="{}")
        db.add(teaching_class); db.flush()
        digest = hashlib.sha256(
            ",".join(str(value) for value in sorted(set(student_ids))).encode("utf-8")
        ).hexdigest()
        version = AaTeachingClassRosterVersion(
            tenant_id=tenant_id, teaching_class_id=teaching_class.id,
            version_no=1, source_type="ADMIN_CLASS", source_id=int(class_id),
            member_count=len(student_ids), roster_hash=digest, status="LOCKED",
            reason="考勤合同测试正式名单", locked_at=datetime.utcnow(),
            locked_by=f"u-{teacher_key}")
        db.add(version); db.flush()
        for student_id in student_ids:
            db.add(AaTeachingClassMember(
                tenant_id=tenant_id, teaching_class_id=teaching_class.id,
                roster_version_id=version.id, student_id=student_id,
                source_type="ADMIN_CLASS", source_id=int(class_id), status="ACTIVE"))
        db.add(AaTeachingClassTeacher(
            tenant_id=tenant_id, teaching_class_id=teaching_class.id,
            teacher_key=f"u-{teacher_key}", teacher_name=teacher_key,
            role_type="PRIMARY", status="ACTIVE"))
        teaching_class.current_roster_version_id = version.id
        teaching_class.current_roster_version_no = 1
        teaching_class.roster_status = "LOCKED"
        task.expected_students = len(student_ids)
        db.commit()
        return task.id
    finally:
        db.close()
''',
)
replace(
    "backend/tests/test_mobile_attendance.py",
    '''    assert r["code"] == 0
''',
    '''    assert r["code"] == 0, r
''',
)
replace(
    "backend/tests/test_mobile_attendance.py",
    '''    sid = r["data"]["sessionId"]
''',
    '''    assert r["code"] == 0, r
    sid = r["data"]["sessionId"]
''',
)
replace(
    "backend/tests/test_mobile_attendance.py",
    '''    s1 = client.post(f"{BASE}/sessions", headers=hdr, json={
        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",
        "termCode": "2026-1", "sessionDate": "2026-07-14"}).json()["data"]
''',
    '''    s1_payload = client.post(f"{BASE}/sessions", headers=hdr, json={
        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",
        "termCode": "2026-1", "sessionDate": "2026-07-14"}).json()
    assert s1_payload["code"] == 0, s1_payload
    s1 = s1_payload["data"]
''',
)

# 2) 通知和改密统一使用真实测试租户。学生消息读取使用真实账号、STUDENT角色和稳定主档绑定。
replace(
    "backend/tests/test_mobile_wave10.py",
    '''# ══════════ 通知发布 ══════════

_NOTIFY_STUDENTS = {}
''',
    '''# ══════════ 通知发布 ══════════

_NOTIFY_STUDENTS = {}
_NOTIFY_PASSWORD = "StudentPass123"


def _ensure_test_tenant(db, tenant_id=MAIN):
    from app.models import Tenant
    tenant = db.get(Tenant, int(tenant_id))
    if tenant is None:
        tenant = Tenant(
            id=int(tenant_id), tenant_code="demo", school_name="测试学校",
            short_name="测试学校", status="ACTIVE")
        db.add(tenant); db.flush()
    return tenant
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''def _notify_student_token(class_id, index=0):
    from app.core.security import create_access_token
    item = _NOTIFY_STUDENTS[int(class_id)][index]
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"db-{item['userId']}", "studentId": str(item["studentId"]),
        "studentNo": item["studentNo"], "realName": item["realName"],
        "userType": "STUDENT", "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}
''',
    '''def _notify_student_token(client, class_id, index=0):
    item = _NOTIFY_STUDENTS[int(class_id)][index]
    result = client.post("/api/v1/auth/login", json={
        "tenantCode": "demo", "loginName": item["studentNo"],
        "password": _NOTIFY_PASSWORD, "clientType": "MP",
    }).json()
    assert result["code"] == 0, result
    return {"Authorization": f"Bearer {result['data']['accessToken']}"}
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope, User
''',
    '''    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import (
        Role, SchoolClass, StudentAccountLink, StudentProfile,
        TeacherStudentScope, User, UserRole,
    )
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    try:
        c = SchoolClass(tenant_id=tenant_id, major_id=1, class_name="通知测2601",
''',
    '''    try:
        _ensure_test_tenant(db, tenant_id)
        student_role = Role(
            tenant_id=tenant_id, role_code="STUDENT", role_name="学生",
            role_type="SYSTEM", status="ACTIVE")
        db.add(student_role); db.flush()
        c = SchoolClass(tenant_id=tenant_id, major_id=1, class_name="通知测2601",
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''            account = User(
                tenant_id=tenant_id, login_name=student_no, real_name=real_name,
                password_hash=hash_password("Unused123"), user_type="STUDENT", status="ACTIVE")
            db.add(account); db.flush()
            account_rows.append({
                "studentId": profile.id, "userId": account.id,
                "studentNo": student_no, "realName": real_name,
            })
''',
    '''            account = User(
                tenant_id=tenant_id, login_name=student_no, real_name=real_name,
                password_hash=hash_password(_NOTIFY_PASSWORD),
                user_type="STUDENT", status="ACTIVE")
            db.add(account); db.flush()
            db.add(UserRole(
                tenant_id=tenant_id, user_id=account.id,
                role_id=student_role.id, status="ACTIVE"))
            db.add(StudentAccountLink(
                tenant_id=tenant_id, student_id=profile.id, user_id=account.id,
                link_status="ACTIVE", source="MANUAL",
                bound_login_name=student_no, bound_student_no=student_no,
                bound_at=datetime.utcnow()))
            account_rows.append({
                "studentId": profile.id, "userId": account.id,
                "studentNo": student_no, "realName": real_name,
            })
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    stu_hdr = _notify_student_token(cid)
''',
    '''    stu_hdr = _notify_student_token(client, cid)
''',
    count=2,
)

# 3) 修改密码：同样补齐真实租户，并在登录请求中显式携带学校编码。
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    db = get_sessionmaker()()
    try:
        u = User(tenant_id=tenant_id, login_name=login_name, real_name="改密测试师",
''',
    '''    db = get_sessionmaker()()
    try:
        _ensure_test_tenant(db, tenant_id)
        u = User(tenant_id=tenant_id, login_name=login_name, real_name="改密测试师",
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    result = client.post("/api/v1/auth/login", json={
        "loginName": login_name, "password": password, "clientType": "MP",
    }).json()
''',
    '''    result = client.post("/api/v1/auth/login", json={
        "tenantCode": "demo", "loginName": login_name,
        "password": password, "clientType": "MP",
    }).json()
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    login_old = client.post("/api/v1/auth/login",
                            json={"loginName": "cp_test02", "password": "OldPass123"}).json()
''',
    '''    login_old = client.post("/api/v1/auth/login", json={
        "tenantCode": "demo", "loginName": "cp_test02", "password": "OldPass123"}).json()
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    login_new = client.post("/api/v1/auth/login",
                            json={"loginName": "cp_test02", "password": "NewPass456"}).json()
''',
    '''    login_new = client.post("/api/v1/auth/login", json={
        "tenantCode": "demo", "loginName": "cp_test02", "password": "NewPass456"}).json()
''',
)

print("ABCD D-stage final contract fixture patch complete")
