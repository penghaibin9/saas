"""只向显式本机测试库新增学工页面验收前置条件，不创建审批结果。"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def seed():
    from sqlalchemy import select
    from sqlalchemy.engine import make_url
    from app.core.config import settings
    from app.core.context import set_tenant
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import (AffairsCounselorAssignment, College, DormBed, DormBuilding, DormRoom,
        Major, Role, RoleAssignmentScope, SchoolClass, StudentAccountLink, StudentProfile, Tenant, User, UserRole)
    from app.services.saas_role_service import ensure_builtin_roles
    from app.services.platform_service import put_config_json

    url = make_url(settings.effective_database_url)
    if settings.APP_ENV != "test" or url.host not in {"127.0.0.1", "localhost"} or "test" not in str(url.database):
        raise RuntimeError("仅允许显式本机测试库")
    password = os.environ["AFFAIRS_ACCEPTANCE_PASSWORD"]
    if len(password) < 16:
        raise RuntimeError("验收密码长度不足")
    tid = 1000000000000000818
    set_tenant(tid)
    with get_sessionmaker()() as db:
        if db.get(Tenant, tid):
            raise RuntimeError("验收学校已存在，保留现有场景；请使用已有回执")
        db.add(Tenant(id=tid, tenant_code="affairs-role-e2e", school_name="学工岗位隔离验收学校",
                      short_name="学工验收", status="ACTIVE", deploy_mode="SAAS", db_mode="SHARED"))
        ensure_builtin_roles(db, tid)
        roles = {r.role_code: r for r in db.scalars(select(Role).where(Role.tenant_id == tid)).all()}
        colleges, classes, students = {}, {}, {}
        for key, name in (("A", "验收软件学院"), ("B", "验收机械学院")):
            college = College(tenant_id=tid, college_name=name, status="ACTIVE")
            db.add(college); db.flush(); colleges[key] = college
            major = Major(tenant_id=tid, college_id=college.id, major_name=name + "专业", status="ACTIVE")
            db.add(major); db.flush()
            school_class = SchoolClass(tenant_id=tid, major_id=major.id, class_name="验收" + key + "班",
                                      grade="2026", class_status="NORMAL", status="ACTIVE")
            db.add(school_class); db.flush(); classes[key] = school_class
            student = StudentProfile(tenant_id=tid, student_no="ACCEPT_" + key, real_name="验收学生" + key,
                gender="M", college_id=college.id, major_id=major.id, class_id=school_class.id,
                current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
            db.add(student); db.flush(); students[key] = student
        specs = {
            "multi": ("兼岗验收老师", [("COUNSELOR", "CLASS", classes["A"].id),
                ("STUDENT_AFFAIRS_COLLEGE", "COLLEGE", colleges["A"].id),
                ("FUNDING_TEACHER", "COLLEGE", colleges["B"].id),
                ("PSYCHOLOGY_TEACHER", "STUDENT", students["B"].id), ("DORM_MANAGER", None, None)]),
            "fund_college": ("学院资助验收老师", [("FUNDING_TEACHER", "COLLEGE", colleges["A"].id)]),
            "fund_school": ("校级资助验收老师", [("FUNDING_TEACHER", "SCHOOL", 0)]),
            "school": ("校学工验收老师", [("STUDENT_AFFAIRS_ADMIN", "SCHOOL", 0)]),
            "school_review": ("独立校学工审核人", [("STUDENT_AFFAIRS_ADMIN", "SCHOOL", 0)]),
            "dorm": ("独立宿管验收老师", [("DORM_MANAGER", None, None)]),
            "next_counselor": ("接任辅导员", [("COUNSELOR", None, None)]),
            "youth": ("团学专项验收老师", [("YOUTH_LEAGUE", "COLLEGE", colleges["A"].id)]),
            "evaluation": ("考评专项验收老师", [("ORG_PERSONNEL", "COLLEGE", colleges["A"].id)]),
            "evaluation_school": ("校级考评验收老师", [("ORG_PERSONNEL", "SCHOOL", 0)]),
            "student_a": ("验收学生A", [("STUDENT", None, None)]),
            "student_b": ("验收学生B", [("STUDENT", None, None)]),
        }
        users = {}; contexts = {}; hashed = hash_password(password)
        for key, (name, assignments) in specs.items():
            user = User(tenant_id=tid, login_name="accept_" + key, real_name=name,
                user_type="STUDENT" if key.startswith("student_") else "TEACHER",
                password_hash=hashed, status="ACTIVE", must_change_password=False)
            db.add(user); db.flush(); users[key] = user; contexts[key] = {}
            for code, scope_type, scope_id in assignments:
                role = roles[code]; contexts[key][code] = f"role:{role.id}"
                member = UserRole(tenant_id=tid, user_id=user.id, role_id=role.id, status="ACTIVE")
                db.add(member); db.flush()
                if scope_type:
                    db.add(RoleAssignmentScope(tenant_id=tid, user_id=user.id, user_role_id=member.id,
                        role_code=code, scope_type=scope_type, scope_id=scope_id, status="ACTIVE",
                        effective_at=datetime.utcnow() - timedelta(days=1)))
        classes["A"].counselor_id = users["multi"].id
        db.add(AffairsCounselorAssignment(tenant_id=tid, class_id=classes["A"].id, user_id=users["multi"].id,
            duty_type="PRIMARY", status="ACTIVE", effective_from=datetime.utcnow() - timedelta(days=1)))
        for key in ("A", "B"):
            db.add(StudentAccountLink(tenant_id=tid, user_id=users["student_" + key.lower()].id,
                student_id=students[key].id, link_status="ACTIVE", source="MANUAL"))
        beds = {}
        for key, manager in (("normal", "dorm"), ("same", "multi")):
            building = DormBuilding(tenant_id=tid, building_name="验收" + key + "楼", building_code="ACCEPT_" + key,
                gender_limit="MALE", manager_teacher_key=users[manager].login_name, status="ENABLED")
            db.add(building); db.flush()
            room = DormRoom(tenant_id=tid, building_id=building.id, floor_no=1, room_no="101", capacity=4, status="ENABLED")
            db.add(room); db.flush()
            beds[key] = []
            for number in range(1, 5):
                bed = DormBed(tenant_id=tid, building_id=building.id, room_id=room.id, bed_no=str(number), status="VACANT")
                db.add(bed); db.flush(); beds[key].append(str(bed.id))
        db.commit()
        result = {"tenant": "affairs-role-e2e", "tenantId": str(tid), "contexts": contexts,
            "users": {k: {"id": str(v.id), "login": v.login_name} for k, v in users.items()},
            "students": {k: str(v.id) for k, v in students.items()}, "beds": beds}
    now = datetime.utcnow()
    put_config_json(tid, "TENANT_META", "-", {"status": "trial", "packageCode": "trial",
        "environment": "test", "trialStartAt": now.isoformat(), "expireAt": (now + timedelta(days=30)).isoformat()})
    return result


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve()
    if target.exists():
        raise RuntimeError("回执已存在，禁止覆盖")
    target.write_text(json.dumps(seed(), ensure_ascii=False, indent=2), encoding="utf-8")
    print("学工验收前置条件已新增；未创建请假、资助、调宿审批结果")
