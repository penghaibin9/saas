"""教务中心 Bug 修复回归：学分小数 / 期中回显 / 成绩任务去重 / 发布后成绩单一致。

本文件使用当前正式合同：成绩任务必须绑定 AaCourse 具体版本与权威 AaTerm；
普通发布链必须来自真实教学任务和正式名单版本，管理员特殊补录不得伪装普通教学任务发布。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"
COLLEGE_REVIEW_PERM = "academicAffairs.grade.collegeReview"
ACADEMIC_PUBLISH_PERM = "academicAffairs.grade.publish"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _ensure_grade_policy(db):
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    row = db.query(AaEffectiveGradePolicy).filter(
        AaEffectiveGradePolicy.tenant_id == TID,
        AaEffectiveGradePolicy.status == "ACTIVE",
        AaEffectiveGradePolicy.is_deleted.is_(False),
    ).first()
    if row:
        return row
    row = AaEffectiveGradePolicy(
        tenant_id=TID,
        policy_code="BUGFIX_TEST_POLICY",
        policy_version=1,
        active_scope_key="BASE",
        attempt_strategy="LATEST_ATTEMPT",
        makeup_strategy="CAP_AND_OVERRIDE",
        makeup_cap=60,
        retake_strategy="REPLACE_IF_PASSED",
        recognition_priority=75,
        effective_from_term_id=None,
        status="ACTIVE",
    )
    db.add(row)
    db.flush()
    return row


def _grant_review_permission(db, login_name, real_name, permission_code):
    """为回归链创建真实启用受理人及专属权限角色。"""
    from app.models import Permission, Role, RolePermission, User, UserRole

    user = db.query(User).filter(User.tenant_id == TID, User.login_name == login_name).first()
    if user is None:
        user = User(
            tenant_id=TID,
            login_name=login_name,
            real_name=real_name,
            password_hash="x",
            user_type="ADMIN",
            status="ACTIVE",
        )
        db.add(user)
        db.flush()

    permission = db.query(Permission).filter(Permission.permission_code == permission_code).first()
    if permission is None:
        permission = Permission(
            permission_code=permission_code,
            permission_name=permission_code,
            module_code="academicAffairs",
            action="REVIEW",
        )
        db.add(permission)
        db.flush()

    role_code = (
        "BUGFIX_COLLEGE_REVIEW"
        if permission_code == COLLEGE_REVIEW_PERM
        else "BUGFIX_ACADEMIC_PUBLISH"
    )
    role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == role_code).first()
    if role is None:
        role = Role(
            tenant_id=TID,
            role_code=role_code,
            role_name=role_code,
            status="ACTIVE",
        )
        db.add(role)
        db.flush()

    if db.query(UserRole).filter(
        UserRole.tenant_id == TID,
        UserRole.user_id == user.id,
        UserRole.role_id == role.id,
    ).first() is None:
        db.add(UserRole(
            tenant_id=TID,
            user_id=user.id,
            role_id=role.id,
            status="ACTIVE",
        ))
    if db.query(RolePermission).filter(
        RolePermission.tenant_id == TID,
        RolePermission.role_id == role.id,
        RolePermission.permission_id == permission.id,
    ).first() is None:
        db.add(RolePermission(
            tenant_id=TID,
            role_id=role.id,
            permission_id=permission.id,
            status="ACTIVE",
        ))
    db.flush()
    return user


def _seed_grade_context(*, course_code, course_name, class_id=None, with_task=False, credit=3):
    """创建真实课程版本 + 权威学期；需要时再创建真实教学任务。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm

    db = get_sessionmaker()()
    term = AaTerm(
        tenant_id=TID,
        year_code=f"2090-{course_code[-2:]}" if course_code[-2:].isdigit() else "2090-2091",
        term_no=1,
        term_name=f"{course_name}测试学期",
        start_date=datetime(2090, 9, 1),
        end_date=datetime(2091, 1, 15),
        status="PUBLISHED",
        is_current=False,
    )
    db.add(term); db.flush()
    course = AaCourse(
        tenant_id=TID,
        course_code=course_code,
        course_name=course_name,
        credit=credit,
        version=1,
        status="ENABLED",
    )
    db.add(course); db.flush()
    _ensure_grade_policy(db)

    task = None
    batch = None
    if with_task:
        batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name=f"{course_name}教学任务批次",
            status="APPROVED",
        )
        db.add(batch); db.flush()
        task = AaTeachingTask(
            tenant_id=TID,
            batch_id=batch.id,
            course_id=course.id,
            course_code=course.course_code,
            course_name=course.course_name,
            class_id=class_id,
            teacher_key="school_admin01",
            status="READY",
        )
        db.add(task); db.flush()

    result = {
        "term_id": term.id,
        "term_code": f"{term.year_code}-{term.term_no}",
        "course_id": course.id,
        "teaching_task_id": task.id if task else None,
        "batch_id": batch.id if batch else None,
    }
    db.commit()
    db.close()
    return result


def _seed_students(n=1):
    """创建真实学院→专业→班级→学生，并配置成绩审批真实受理人。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, TeacherStudentScope

    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name="软件BUG学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(
        tenant_id=TID,
        college_id=college.id,
        major_name="软件BUG专业",
        status="ACTIVE",
    )
    db.add(major); db.flush()

    college_user = _grant_review_permission(
        db, "college_admin01", "张晓明", COLLEGE_REVIEW_PERM,
    )
    _grant_review_permission(
        db, "school_admin01", "陈校", ACADEMIC_PUBLISH_PERM,
    )
    college.secretary_id = int(college_user.id)
    db.add(TeacherStudentScope(
        tenant_id=TID,
        teacher_key="college_admin01",
        teacher_name="张晓明",
        role_code="COLLEGE_ADMIN",
        scope_type="COLLEGE",
        ref_value=college.college_name,
        status="ACTIVE",
    ))

    a = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name="软件BUG01",
        grade="2026",
        status="ACTIVE",
    )
    db.add(a); db.flush()
    sids = []
    for i in range(n):
        s = StudentProfile(
            tenant_id=TID,
            student_no=f"BUG{i:03d}",
            real_name=f"修{i}",
            class_id=a.id,
            college_id=college.id,
            major_id=major.id,
            current_stage="ON_CAMPUS",
            student_status="REGISTERED",
            status="ACTIVE",
        )
        db.add(s); db.flush(); sids.append(s.id)
    db.commit(); cid = a.id; db.close()
    return sids, cid


def test_bf1_program_half_credit_persists(client, db_mode):
    """培养方案总学分/课程学分快照支持 1.5、2.5、3.5，刷新后不取整。"""
    hdr = _hdr(client, "school_admin01")
    created = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "半学分方案", "gradeYear": "2026", "totalCredits": 120.5}).json()
    assert created["code"] == 0, created
    pid = created["data"]["programId"]
    assert float(created["data"]["totalCredits"]) == 120.5
    add = client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "半学分课", "credit": 1.5, "openTermNo": 1, "module": "专业核心"}).json()
    assert add["code"] == 0, add
    detail = client.get(f"{BASE}/programs/{pid}", headers=hdr).json()["data"]
    assert float(detail["totalCredits"]) == 120.5
    courses = detail.get("courses") or detail.get("courseItems") or []
    hit = next((c for c in courses if c.get("courseName") == "半学分课"), None)
    assert hit is not None
    credit = hit.get("credit") if hit.get("credit") is not None else hit.get("creditSnapshot")
    assert float(credit) == 1.5
    # 再加 2.5
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "二点五学分课", "credit": 2.5, "openTermNo": 2})
    detail2 = client.get(f"{BASE}/programs/{pid}", headers=hdr).json()["data"]
    courses2 = detail2.get("courses") or detail2.get("courseItems") or []
    assert any(float(c.get("credit") if c.get("credit") is not None else c.get("creditSnapshot")) == 2.5
               for c in courses2 if c.get("courseName") == "二点五学分课")


def test_bf2_midterm_persists_on_list_records(client, db_mode):
    """期中分保存后 GET records 必须回读 midtermScore（PC 刷新映射依赖此字段）。"""
    sids, cid = _seed_students(1)
    ctx = _seed_grade_context(course_code="BUG-BF2", course_name="期中回显课", class_id=cid)
    hdr = _hdr(client, "school_admin01")
    created = client.post(f"{BASE}/grade-tasks/identity", headers=hdr, json={
        "courseId": str(ctx["course_id"]), "termId": str(ctx["term_id"]), "classId": str(cid),
        "courseName": "期中回显课",
        "usualRatio": 30, "midtermRatio": 30, "finalRatio": 40,
        "adminSupplementReason": "测试管理员补录成绩任务"})
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["gradeTaskId"]
    r = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=hdr, json={
        "studentId": str(sids[0]), "usualScore": 80, "midtermScore": 90, "finalScore": 70}).json()
    assert r["data"]["midtermScore"] == 90
    assert r["data"]["totalScore"] == 79  # 24+27+28
    items = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"]
    assert items[0]["midtermScore"] == 90
    assert items[0]["usualScore"] == 80
    assert items[0]["finalScore"] == 70


def test_bf3_duplicate_grade_task_same_teaching_task_409(client, db_mode):
    """同一真实教学任务不可产生多条有效成绩任务。"""
    ctx = _seed_grade_context(course_code="BUG-BF3", course_name="去重课", with_task=True)
    hdr = _hdr(client, "school_admin01")
    r1 = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(ctx["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70})
    assert r1.status_code == 200, r1.text
    r2 = client.post(f"{BASE}/grade-tasks", headers=hdr, json={
        "teachingTaskId": str(ctx["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70})
    assert r2.status_code == 409, r2.text


def test_bf4_teacher_must_bind_teaching_task(client, db_mode):
    """普通教师脱离教学任务创建成绩任务必须拒绝。"""
    teacher_hdr = _hdr(client, "academic01")
    r = client.post(f"{BASE}/grade-tasks", headers=teacher_hdr, json={
        "courseName": "脱离教学任务", "usualRatio": 30, "finalRatio": 70})
    assert r.status_code in (400, 422)


def test_bf5_publish_then_transcript_consistent(client, db_mode):
    """真实教学任务发布后成绩单与录入总评一致；重复发布幂等冲突。"""
    sids, cid = _seed_students(1)
    ctx = _seed_grade_context(
        course_code="BUG-BF5", course_name="发布一致课", class_id=cid, with_task=True, credit=3.5,
    )
    school_hdr = _hdr(client, "school_admin01")
    college_hdr = _hdr(client, "college_admin01")
    created = client.post(f"{BASE}/grade-tasks", headers=school_hdr, json={
        "teachingTaskId": str(ctx["teaching_task_id"]), "usualRatio": 30, "finalRatio": 70})
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["gradeTaskId"]
    score = client.post(f"{BASE}/grade-tasks/{tid}/scores", headers=school_hdr, json={
        "studentId": str(sids[0]), "usualScore": 80, "finalScore": 90})
    assert score.status_code == 200, score.text
    submit = client.post(f"{BASE}/grade-tasks/{tid}/submit", headers=school_hdr)
    assert submit.status_code == 200, submit.text
    review = client.post(
        f"{BASE}/grade-tasks/{tid}/college-review",
        headers=college_hdr,
        json={"action": "APPROVE"},
    )
    assert review.status_code == 200, review.text
    pub_resp = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=school_hdr)
    assert pub_resp.status_code == 200, pub_resp.text
    pub = pub_resp.json()
    assert pub["data"]["status"] == "PUBLISHED"
    assert pub["data"].get("warningScanOk") is True
    tr = client.get(f"{BASE}/students/{sids[0]}/transcript", headers=school_hdr).json()["data"]
    assert any(g["courseName"] == "发布一致课" and g["score"] == 87 and g["source"] == "PUBLISH"
               for g in tr["items"])
    # 重复发布
    again = client.post(f"{BASE}/grade-tasks/{tid}/publish", headers=school_hdr)
    assert again.status_code in (409, 400)


def test_bf6_import_midterm_and_class_guard(client, db_mode):
    """Excel 导入支持期中；非本班学生整批拒绝。"""
    _sids, cid = _seed_students(1)
    ctx = _seed_grade_context(course_code="BUG-BF6", course_name="导入期中课", class_id=cid)
    hdr = _hdr(client, "school_admin01")
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    other = StudentProfile(tenant_id=TID, student_no="OTHERBUG", real_name="外班", class_id=cid + 99999,
                           current_stage="ON_CAMPUS", student_status="REGISTERED", status="ACTIVE")
    db.add(other); db.commit(); db.close()
    created = client.post(f"{BASE}/grade-tasks/identity", headers=hdr, json={
        "courseId": str(ctx["course_id"]), "termId": str(ctx["term_id"]), "classId": str(cid),
        "courseName": "导入期中课",
        "usualRatio": 30, "midtermRatio": 30, "finalRatio": 40,
        "adminSupplementReason": "测试管理员补录成绩任务"})
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["gradeTaskId"]
    # 外班学生 → 整批 409
    bad = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "OTHERBUG", "usualScore": 80, "midtermScore": 80, "finalScore": 80}]})
    assert bad.status_code == 409
    # 缺期中 → 409
    miss = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "BUG000", "usualScore": 80, "finalScore": 80}]})
    assert miss.status_code == 409
    ok = client.post(f"{BASE}/grade-tasks/{tid}/import/confirm", headers=hdr, json={
        "rows": [{"studentNo": "BUG000", "usualScore": 80, "midtermScore": 90, "finalScore": 70}]})
    assert ok.status_code == 200, ok.text
    items = client.get(f"{BASE}/grade-tasks/{tid}/records", headers=hdr).json()["data"]["items"]
    assert items[0]["midtermScore"] == 90
