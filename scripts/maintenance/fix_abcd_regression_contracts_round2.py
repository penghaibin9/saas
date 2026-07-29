#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(str(ROOT / "scripts/maintenance/fix_abcd_regression_contracts.py"), run_name="__main__")


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"round2 expected snippet not found: {path}\n---\n{old[:500]}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"round2 patched {path}")


# 考勤：构造当前学期 + 教学任务批次 + 与 token 工号族一致的 READY 教学任务。
replace(
    "backend/tests/test_mobile_attendance.py",
    '''def _seed_teaching_task(class_id, teacher_key, tenant_id=MAIN):
    """新建考勤场次要求当前学期本人已确认教学任务；返回真实 taskId。"""
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    db = get_sessionmaker()()
    try:
        task = AaTeachingTask(tenant_id=tenant_id, batch_id=1, course_id=1, class_id=class_id,
                              course_name="测试课程", teacher_key=teacher_key,
                              teacher_name=teacher_key, status="TEACHER_CONFIRMED")
        db.add(task); db.flush()
        task_id = task.id
        db.commit()
        return task_id
    finally:
        db.close()
''',
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
)

# 通知：消息受众只向已开通校园账号的学生投递；测试同时构造账号并用稳定身份 token 读取。
replace(
    "backend/tests/test_mobile_wave10.py",
    '''# ══════════ 通知发布 ══════════

def _seed_class(counselor_id, tenant_id=MAIN, n_students=2):
''',
    '''# ══════════ 通知发布 ══════════

_NOTIFY_STUDENTS = {}


def _notify_student_token(class_id, index=0):
    from app.core.security import create_access_token
    item = _NOTIFY_STUDENTS[int(class_id)][index]
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"db-{item['userId']}", "studentId": str(item["studentId"]),
        "studentNo": item["studentNo"], "realName": item["realName"],
        "userType": "STUDENT", "tid": "demo", "tenantId": str(MAIN),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed_class(counselor_id, tenant_id=MAIN, n_students=2):
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
''',
    '''    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope, User
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''        for i in range(n_students):
            db.add(StudentProfile(tenant_id=tenant_id, student_no=f"NT{i:04d}",
                                  real_name=f"通知测生{i}", class_id=cid,
                                  current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))
        db.commit()
        return cid
''',
    '''        account_rows = []
        for i in range(n_students):
            student_no = f"NT{i:04d}"
            real_name = f"通知测生{i}"
            profile = StudentProfile(
                tenant_id=tenant_id, student_no=student_no, real_name=real_name, class_id=cid,
                current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
            db.add(profile); db.flush()
            account = User(
                tenant_id=tenant_id, login_name=student_no, real_name=real_name,
                password_hash=hash_password("Unused123"), user_type="STUDENT", status="ACTIVE")
            db.add(account); db.flush()
            account_rows.append({
                "studentId": profile.id, "userId": account.id,
                "studentNo": student_no, "realName": real_name,
            })
        db.commit()
        _NOTIFY_STUDENTS[int(cid)] = account_rows
        return cid
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    stu_hdr = _stu_token("通知测生0", "NT0000")
''',
    '''    stu_hdr = _notify_student_token(cid)
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    stu_hdr = _stu_token("通知测生0", "NT0000")
''',
    '''    stu_hdr = _notify_student_token(cid)
''',
)

# 谈话记录初始 version 来自 CommonMixin，默认是 0。
replace(
    "backend/tests/test_mobile_wave10.py",
    '''                                 "expectedVersion": 1}).json()
''',
    '''                                 "expectedVersion": 0}).json()
''',
)

# 改密必须使用真实登录签发且经数据库复核的访问令牌，不再伪造 claims。
replace(
    "backend/tests/test_mobile_wave10.py",
    '''def _seed_real_user(login_name, password, tenant_id=MAIN):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole
    db = get_sessionmaker()()
    try:
        u = User(tenant_id=tenant_id, login_name=login_name, real_name="改密测试师",
                 password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE")
        db.add(u); db.flush()
        role = Role(tenant_id=tenant_id, role_code="COUNSELOR", role_name="辅导员",
                    role_type="SYSTEM", status="ACTIVE")
        db.add(role); db.flush()
        db.add(UserRole(tenant_id=tenant_id, user_id=u.id, role_id=role.id, status="ACTIVE"))
        db.commit()
        return u.id, role.id
    finally:
        db.close()


def _db_token(uid, role_id):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"db-{uid}", "realName": "改密测试师", "userType": "TEACHER",
        "tid": "demo", "tenantId": str(MAIN), "activeContextId": f"role:{role_id}",
        "currentRoleCode": "COUNSELOR", "clientType": "MP"})}
''',
    '''def _seed_real_user(login_name, password, tenant_id=MAIN):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole
    db = get_sessionmaker()()
    try:
        u = User(tenant_id=tenant_id, login_name=login_name, real_name="改密测试师",
                 password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE")
        db.add(u); db.flush()
        role = Role(tenant_id=tenant_id, role_code="COUNSELOR", role_name="辅导员",
                    role_type="SYSTEM", status="ACTIVE")
        db.add(role); db.flush()
        db.add(UserRole(tenant_id=tenant_id, user_id=u.id, role_id=role.id, status="ACTIVE"))
        db.commit()
    finally:
        db.close()


def _real_login(client, login_name, password):
    result = client.post("/api/v1/auth/login", json={
        "loginName": login_name, "password": password, "clientType": "MP",
    }).json()
    assert result["code"] == 0, result
    return {"Authorization": f"Bearer {result['data']['accessToken']}"}
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    uid, role_id = _seed_real_user("cp_test01", "OldPass123")
    hdr = _db_token(uid, role_id)
''',
    '''    _seed_real_user("cp_test01", "OldPass123")
    hdr = _real_login(client, "cp_test01", "OldPass123")
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    uid, role_id = _seed_real_user("cp_test02", "OldPass123")
    hdr = _db_token(uid, role_id)
''',
    '''    _seed_real_user("cp_test02", "OldPass123")
    hdr = _real_login(client, "cp_test02", "OldPass123")
''',
)

print("ABCD regression contract round2 patch complete")
