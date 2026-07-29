#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected snippet not found: {path}\n---\n{old[:400]}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {path}")


# 1) 教师移动端谈话记录：生产接口必须透传乐观锁版本。
replace(
    "backend/app/services/mobile_teacher_service.py",
    '''def talk_record(user: dict, talk_id, body: dict) -> dict:\n    _require_teacher(user)  # 纵深防御：与同族 talk_* 一致显式收口非教师（底层 _scope_or_403 仍在）\n    from app.services import affairs_talk_service as talk\n    b = body or {}\n    return talk.record_talk(talk_id, user, b.get("content"), b.get("result", ""), bool(b.get("needFollow")))\n''',
    '''def talk_record(user: dict, talk_id, body: dict) -> dict:\n    _require_teacher(user)  # 纵深防御：与同族 talk_* 一致显式收口非教师（底层 _scope_or_403 仍在）\n    from app.services import affairs_talk_service as talk\n    b = body or {}\n    expected_version = b.get("expectedVersion", b.get("version"))\n    return talk.record_talk(\n        talk_id, user, b.get("content"), b.get("result", ""),\n        bool(b.get("needFollow")), expected_version=expected_version)\n''',
)

# 2) 移动教师通用结构测试：需要全租户可见时显式使用 SCHOOL_ADMIN，
# 不再让无范围 COUNSELOR 绕过 fail-closed 数据范围。
replace(
    "backend/tests/test_mobile.py",
    '''def _teacher_token(tenant_id=MAIN, tid="demo"):\n    from app.core.security import create_access_token\n    return {"Authorization": "Bearer " + create_access_token({\n        "userId": "u-teacher", "realName": "王辅导", "userType": "TEACHER",\n        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",\n        "currentRoleCode": "COUNSELOR", "clientType": "MP"})}\n''',
    '''def _teacher_token(tenant_id=MAIN, tid="demo", role="COUNSELOR"):\n    from app.core.security import create_access_token\n    return {"Authorization": "Bearer " + create_access_token({\n        "userId": "u-teacher", "realName": "王辅导", "userType": "TEACHER",\n        "tid": tid, "tenantId": str(tenant_id), "activeContextId": "ctx",\n        "currentRoleCode": role, "clientType": "MP"})}\n''',
)
replace(
    "backend/tests/test_mobile.py",
    '''    main = client.get("/api/v1/mobile/teacher/risk-students", headers=_teacher_token()).json()\n    assert main["code"] == 0 and main["data"]["total"] >= 1  # 主租户有风险学生\n    demo = client.get("/api/v1/mobile/teacher/risk-students",\n                      headers=_teacher_token(tenant_id=DEMO, tid="demo-school")).json()\n''',
    '''    main = client.get("/api/v1/mobile/teacher/risk-students",\n                      headers=_teacher_token(role="SCHOOL_ADMIN")).json()\n    assert main["code"] == 0 and main["data"]["total"] >= 1  # 主租户有风险学生\n    demo = client.get("/api/v1/mobile/teacher/risk-students",\n                      headers=_teacher_token(tenant_id=DEMO, tid="demo-school",\n                                             role="SCHOOL_ADMIN")).json()\n''',
)
replace(
    "backend/tests/test_mobile.py",
    '''    ok = client.get(f"/api/v1/mobile/teacher/student/{sid}", headers=_teacher_token()).json()\n''',
    '''    ok = client.get(f"/api/v1/mobile/teacher/student/{sid}",\n                    headers=_teacher_token(role="SCHOOL_ADMIN")).json()\n''',
)
replace(
    "backend/tests/test_mobile.py",
    '''    it = client.get("/api/v1/mobile/teacher/internship", headers=_teacher_token()).json()\n''',
    '''    admin_headers = _teacher_token(role="SCHOOL_ADMIN")\n    it = client.get("/api/v1/mobile/teacher/internship", headers=admin_headers).json()\n''',
)
replace(
    "backend/tests/test_mobile.py",
    '''    gd = client.get("/api/v1/mobile/teacher/graduation", headers=_teacher_token()).json()\n''',
    '''    gd = client.get("/api/v1/mobile/teacher/graduation", headers=admin_headers).json()\n''',
)
replace(
    "backend/tests/test_mobile.py",
    '''    em = client.get("/api/v1/mobile/teacher/employment", headers=_teacher_token()).json()\n''',
    '''    em = client.get("/api/v1/mobile/teacher/employment", headers=admin_headers).json()\n''',
)
replace(
    "backend/tests/test_mobile.py",
    '''    msg = client.get("/api/v1/mobile/teacher/messages", headers=_teacher_token()).json()\n''',
    '''    msg = client.get("/api/v1/mobile/teacher/messages", headers=admin_headers).json()\n''',
)
replace(
    "backend/tests/test_mobile.py",
    '''    ap = client.get("/api/v1/mobile/teacher/approvals", headers=_teacher_token()).json()\n''',
    '''    ap = client.get("/api/v1/mobile/teacher/approvals", headers=admin_headers).json()\n''',
)

# 3) 成绩认定：测试创建真实课程库目标，并提交 targetCourseId。
replace(
    "backend/tests/test_mobile_aa_student_v2.py",
    '''def _seed_student(student_no, real_name, grade="2026", major_id=None, class_id=None):\n    from app.db.session import get_sessionmaker\n    from app.models import StudentProfile\n    db = get_sessionmaker()()\n    db.add(StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,\n                          grade=grade, major_id=major_id, class_id=class_id,\n                          current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))\n    db.commit(); db.close()\n''',
    '''def _seed_student(student_no, real_name, grade="2026", major_id=None, class_id=None):\n    from app.db.session import get_sessionmaker\n    from app.models import StudentProfile\n    db = get_sessionmaker()()\n    db.add(StudentProfile(tenant_id=MAIN, student_no=student_no, real_name=real_name,\n                          grade=grade, major_id=major_id, class_id=class_id,\n                          current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE"))\n    db.commit(); db.close()\n\n\ndef _seed_target_course(client, admin):\n    response = client.post(f"{ADMIN_BASE}/courses", headers=admin, json={\n        "courseCode": "RG101", "courseName": "高等数学",\n        "category": "MAJOR_CORE", "nature": "REQUIRED", "credit": 4,\n        "hoursTotal": 64, "hoursTheory": 48, "hoursPractice": 16,\n        "examMode": "EXAM",\n    })\n    assert response.status_code == 200, response.text\n    return response.json()["data"]["courseId"]\n''',
)
replace(
    "backend/tests/test_mobile_aa_student_v2.py",
    '''def test_recognition_submit_and_visible_to_admin(client, db_mode):\n    _seed_student("RG0002", "认定乙")\n    hdr = _stu_token("认定乙", "RG0002")\n    # 低分拦截\n    bad = client.post(f"{BASE}/recognition/submit", headers=hdr,\n                      json={"sourceCourseName": "高数A", "sourceScore": 50, "targetCourseName": "高数"})\n    assert bad.status_code == 400, bad.text\n    # 正常提交\n    ok = client.post(f"{BASE}/recognition/submit", headers=hdr,\n                     json={"sourceCourseName": "高数A", "sourceScore": 82, "sourceCredit": 4,\n                           "sourceOrigin": "原电子专业", "targetCourseName": "高等数学", "reason": "转专业替代"})\n''',
    '''def test_recognition_submit_and_visible_to_admin(client, db_mode):\n    _seed_student("RG0002", "认定乙")\n    hdr = _stu_token("认定乙", "RG0002")\n    admin = _admin(client)\n    target_course_id = _seed_target_course(client, admin)\n    # 低分拦截（即使目标课程合法，低分仍必须被业务规则拒绝）\n    bad = client.post(f"{BASE}/recognition/submit", headers=hdr,\n                      json={"sourceCourseName": "高数A", "sourceScore": 50,\n                            "targetCourseId": str(target_course_id),\n                            "targetCourseName": "高等数学"})\n    assert bad.status_code == 400, bad.text\n    # 正常提交\n    ok = client.post(f"{BASE}/recognition/submit", headers=hdr,\n                     json={"sourceCourseName": "高数A", "sourceScore": 82, "sourceCredit": 4,\n                           "sourceOrigin": "原电子专业",\n                           "targetCourseId": str(target_course_id),\n                           "targetCourseName": "高等数学", "reason": "转专业替代"})\n''',
)

# 4) 课堂考勤：普通教师必须提交当前学期本人已确认教学任务ID。
replace(
    "backend/tests/test_mobile_attendance.py",
    '''def _seed_teaching_task(class_id, teacher_key, tenant_id=MAIN):\n    """新建考勤场次现要求调用者对该行政班确有教学任务归属（P0 越权修复），测试需先建好教学任务。"""\n    from app.db.session import get_sessionmaker\n    from app.models import AaTeachingTask\n    db = get_sessionmaker()()\n    try:\n        db.add(AaTeachingTask(tenant_id=tenant_id, batch_id=1, course_id=1, class_id=class_id,\n                              teacher_key=teacher_key, status="PENDING_ASSIGN"))\n        db.commit()\n    finally:\n        db.close()\n''',
    '''def _seed_teaching_task(class_id, teacher_key, tenant_id=MAIN):\n    """新建考勤场次要求当前学期本人已确认教学任务；返回真实 taskId。"""\n    from app.db.session import get_sessionmaker\n    from app.models import AaTeachingTask\n    db = get_sessionmaker()()\n    try:\n        task = AaTeachingTask(tenant_id=tenant_id, batch_id=1, course_id=1, class_id=class_id,\n                              course_name="测试课程", teacher_key=teacher_key,\n                              teacher_name=teacher_key, status="TEACHER_CONFIRMED")\n        db.add(task); db.flush()\n        task_id = task.id\n        db.commit()\n        return task_id\n    finally:\n        db.close()\n''',
)
replace(
    "backend/tests/test_mobile_attendance.py",
    '''    _seed_teaching_task(cid, "周老师")\n    hdr = _teacher_token("周老师")\n    r = client.post(f"{BASE}/sessions", headers=hdr,\n                    json={"classId": cid, "courseName": "高等数学", "sessionDate": "2026-07-15"}).json()\n''',
    '''    task_id = _seed_teaching_task(cid, "周老师")\n    hdr = _teacher_token("周老师")\n    r = client.post(f"{BASE}/sessions", headers=hdr,\n                    json={"teachingTaskId": task_id, "classId": cid,\n                          "courseName": "高等数学", "sessionDate": "2026-07-15"}).json()\n''',
)
replace(
    "backend/tests/test_mobile_attendance.py",
    '''    _seed_teaching_task(cid, "张老师")\n    owner_hdr = _teacher_token("张老师")\n    r = client.post(f"{BASE}/sessions", headers=owner_hdr,\n                    json={"classId": cid, "courseName": "英语", "sessionDate": "2026-07-15"}).json()\n''',
    '''    task_id = _seed_teaching_task(cid, "张老师")\n    owner_hdr = _teacher_token("张老师")\n    r = client.post(f"{BASE}/sessions", headers=owner_hdr,\n                    json={"teachingTaskId": task_id, "classId": cid,\n                          "courseName": "英语", "sessionDate": "2026-07-15"}).json()\n''',
)
replace(
    "backend/tests/test_mobile_attendance.py",
    '''    cid = _seed_class(n_students=3)\n    hdr = _teacher_token("孙老师")\n    PC = "/api/v1/academic-affairs/attendance"\n''',
    '''    cid = _seed_class(n_students=3)\n    task_id = _seed_teaching_task(cid, "孙老师")\n    hdr = _teacher_token("孙老师")\n    PC = "/api/v1/academic-affairs/attendance"\n''',
)
replace(
    "backend/tests/test_mobile_attendance.py",
    '''        "classId": cid, "courseName": "语文", "termCode": "2026-1", "sessionDate": "2026-07-14"}).json()["data"]\n''',
    '''        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",\n        "termCode": "2026-1", "sessionDate": "2026-07-14"}).json()["data"]\n''',
)
replace(
    "backend/tests/test_mobile_attendance.py",
    '''        "classId": cid, "courseName": "语文", "termCode": "2026-1", "sessionDate": "2026-07-15",\n        "sessionType": "实训"}).json()["data"]\n''',
    '''        "teachingTaskId": task_id, "classId": cid, "courseName": "语文",\n        "termCode": "2026-1", "sessionDate": "2026-07-15",\n        "sessionType": "实训"}).json()["data"]\n''',
)

# 5) 通知、谈话、改密：补齐真实范围、乐观锁和RBAC上下文。
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    from app.models import SchoolClass, StudentProfile\n''',
    '''    from app.models import SchoolClass, StudentProfile, TeacherStudentScope\n''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''        c = SchoolClass(tenant_id=tenant_id, major_id=1, class_name="通知测2601",\n                        grade="2026", counselor_id=counselor_id, status="ACTIVE")\n        db.add(c); db.flush()\n        cid = c.id\n''',
    '''        c = SchoolClass(tenant_id=tenant_id, major_id=1, class_name="通知测2601",\n                        grade="2026", counselor_id=counselor_id, status="ACTIVE")\n        db.add(c); db.flush()\n        cid = c.id\n        db.add(TeacherStudentScope(\n            tenant_id=tenant_id, teacher_key=str(counselor_id), teacher_name="王老师",\n            role_code="COUNSELOR", scope_type="CLASS", ref_value=c.class_name, status="ACTIVE"))\n''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''                           json={"content": "本次谈话了解了学生近期学习和生活状态，情况正常。",\n                                 "result": "无需特别跟进", "needFollow": False}).json()\n''',
    '''                           json={"content": "本次谈话了解了学生近期学习和生活状态，情况正常。",\n                                 "result": "无需特别跟进", "needFollow": False,\n                                 "expectedVersion": 1}).json()\n''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''def _seed_real_user(login_name, password, tenant_id=MAIN):\n    from app.core.security import hash_password\n    from app.db.session import get_sessionmaker\n    from app.models import User\n    db = get_sessionmaker()()\n    try:\n        u = User(tenant_id=tenant_id, login_name=login_name, real_name="改密测试师",\n                 password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE")\n        db.add(u); db.commit(); db.refresh(u)\n        return u.id\n    finally:\n        db.close()\n\n\ndef _db_token(uid):\n    from app.core.security import create_access_token\n    return {"Authorization": "Bearer " + create_access_token({\n        "userId": f"db-{uid}", "realName": "改密测试师", "userType": "TEACHER",\n        "tid": "demo", "tenantId": str(MAIN), "activeContextId": "ctx",\n        "currentRoleCode": "COUNSELOR", "clientType": "MP"})}\n''',
    '''def _seed_real_user(login_name, password, tenant_id=MAIN):\n    from app.core.security import hash_password\n    from app.db.session import get_sessionmaker\n    from app.models import Role, User, UserRole\n    db = get_sessionmaker()()\n    try:\n        u = User(tenant_id=tenant_id, login_name=login_name, real_name="改密测试师",\n                 password_hash=hash_password(password), user_type="TEACHER", status="ACTIVE")\n        db.add(u); db.flush()\n        role = Role(tenant_id=tenant_id, role_code="COUNSELOR", role_name="辅导员",\n                    role_type="SYSTEM", status="ACTIVE")\n        db.add(role); db.flush()\n        db.add(UserRole(tenant_id=tenant_id, user_id=u.id, role_id=role.id, status="ACTIVE"))\n        db.commit()\n        return u.id, role.id\n    finally:\n        db.close()\n\n\ndef _db_token(uid, role_id):\n    from app.core.security import create_access_token\n    return {"Authorization": "Bearer " + create_access_token({\n        "userId": f"db-{uid}", "realName": "改密测试师", "userType": "TEACHER",\n        "tid": "demo", "tenantId": str(MAIN), "activeContextId": f"role:{role_id}",\n        "currentRoleCode": "COUNSELOR", "clientType": "MP"})}\n''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    uid = _seed_real_user("cp_test01", "OldPass123")\n    hdr = _db_token(uid)\n''',
    '''    uid, role_id = _seed_real_user("cp_test01", "OldPass123")\n    hdr = _db_token(uid, role_id)\n''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    uid = _seed_real_user("cp_test02", "OldPass123")\n    hdr = _db_token(uid)\n''',
    '''    uid, role_id = _seed_real_user("cp_test02", "OldPass123")\n    hdr = _db_token(uid, role_id)\n''',
)

print("ABCD regression contract patch complete")
