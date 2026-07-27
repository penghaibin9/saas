from __future__ import annotations

from pathlib import Path
import re


def replace_top_level_function(text: str, name: str, replacement: str) -> str:
    pattern = re.compile(rf"^def {re.escape(name)}\(.*?(?=^def |\Z)", re.M | re.S)
    updated, count = pattern.subn(replacement.rstrip() + "\n\n", text, count=1)
    if count != 1:
        raise RuntimeError(f"failed to replace function: {name}")
    return updated


ASSIGNEE_FIXTURE = '''def _seed(db_mode):
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, Major, Role, SchoolClass,
        StudentProfile, TeacherStudentScope, User, UserRole,
    )
    db = get_sessionmaker()()

    def ensure_user(login_name, real_name):
        row = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
        if row is None:
            row = User(
                tenant_id=TID, login_name=login_name, real_name=real_name,
                password_hash="test-hash", user_type="TEACHER", status="ACTIVE",
            )
            db.add(row)
            db.flush()
        else:
            row.status = "ACTIVE"
            row.is_deleted = False
        return row

    def ensure_role(role_code, role_name):
        row = db.query(Role).filter_by(tenant_id=TID, role_code=role_code).first()
        if row is None:
            row = Role(
                tenant_id=TID, role_code=role_code, role_name=role_name,
                role_type="SYSTEM", status="ACTIVE",
            )
            db.add(row)
            db.flush()
        else:
            row.status = "ACTIVE"
            row.is_deleted = False
        return row

    def bind(user, role):
        row = db.query(UserRole).filter_by(
            tenant_id=TID, user_id=user.id, role_id=role.id,
        ).first()
        if row is None:
            db.add(UserRole(
                tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE",
            ))
        else:
            row.status = "ACTIVE"
            row.is_deleted = False

    counselor = ensure_user("counselor01", "王莉")
    college_reviewer = ensure_user("leave_college01", "学院学工受理人")
    sa_reviewer = ensure_user("leave_sa01", "学工处受理人")
    bind(counselor, ensure_role("COUNSELOR", "辅导员"))
    bind(college_reviewer, ensure_role("COLLEGE_ADMIN", "学院管理员"))
    bind(sa_reviewer, ensure_role("STUDENT_AFFAIRS_ADMIN", "学工处管理员"))

    college = College(
        tenant_id=TID, college_name="请假测试学院", code="LEAVE-COLLEGE", status="ACTIVE",
    )
    db.add(college)
    db.flush()
    major = Major(
        tenant_id=TID, college_id=college.id, major_name="请假测试专业",
        code="LEAVE-MAJOR", status="ACTIVE",
    )
    db.add(major)
    db.flush()
    a = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name="A班", grade="2024",
        counselor_id=counselor.id, status="ACTIVE",
    )
    b = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name="B班", grade="2024",
        counselor_id=counselor.id, status="ACTIVE",
    )
    db.add_all([a, b])
    db.flush()
    sa = StudentProfile(
        tenant_id=TID, student_no="A001", real_name="甲一", class_id=a.id,
        college_id=college.id, gender="M", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    sb = StudentProfile(
        tenant_id=TID, student_no="B001", real_name="乙一", class_id=b.id,
        college_id=college.id, gender="F", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    db.add_all([sa, sb])
    db.flush()
    effective = datetime.utcnow() - timedelta(days=1)
    db.add_all([
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=a.id, user_id=counselor.id,
            duty_type="PRIMARY", status="ACTIVE", effective_from=effective,
        ),
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=b.id, user_id=counselor.id,
            duty_type="PRIMARY", status="ACTIVE", effective_from=effective,
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
            role_code="COUNSELOR", scope_type="CLASS", ref_value="A班", status="ACTIVE",
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key=college_reviewer.login_name,
            teacher_name=college_reviewer.real_name, role_code="COLLEGE_ADMIN",
            scope_type="COLLEGE", ref_value=college.college_name, status="ACTIVE",
        ),
    ])
    db.commit()
    ids = {"a": a.id, "b": b.id, "sa": sa.id, "sb": sb.id}
    db.close()
    return ids
'''


HARDENING_SEED = '''def _seed_students(db_mode, *, prefix="FE4"):
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, Major, Role, SchoolClass,
        StudentProfile, TeacherStudentScope, User, UserRole,
    )
    db = get_sessionmaker()()

    def ensure_user(login_name, real_name, role_code, role_name):
        user = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
        if user is None:
            user = User(
                tenant_id=TID, login_name=login_name, real_name=real_name,
                password_hash="test-hash", user_type="TEACHER", status="ACTIVE",
            )
            db.add(user)
            db.flush()
        role = db.query(Role).filter_by(tenant_id=TID, role_code=role_code).first()
        if role is None:
            role = Role(
                tenant_id=TID, role_code=role_code, role_name=role_name,
                role_type="SYSTEM", status="ACTIVE",
            )
            db.add(role)
            db.flush()
        if db.query(UserRole).filter_by(
            tenant_id=TID, user_id=user.id, role_id=role.id,
        ).first() is None:
            db.add(UserRole(
                tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE",
            ))
        return user

    counselor = ensure_user("counselor01", "王莉", "COUNSELOR", "辅导员")
    college_reviewer = ensure_user("fe_college01", "学院受理人", "COLLEGE_ADMIN", "学院管理员")
    ensure_user("fe_sa01", "学工处受理人", "STUDENT_AFFAIRS_ADMIN", "学工处管理员")
    college = College(
        tenant_id=TID, college_name=f"{prefix}学院", code=f"{prefix}-COL", status="ACTIVE",
    )
    db.add(college)
    db.flush()
    major = Major(
        tenant_id=TID, college_id=college.id, major_name=f"{prefix}专业",
        code=f"{prefix}-MAJ", status="ACTIVE",
    )
    db.add(major)
    db.flush()
    cls = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name=f"{prefix}软件2401",
        grade="2024", counselor_id=counselor.id, status="ACTIVE",
    )
    db.add(cls)
    db.flush()
    one = StudentProfile(
        tenant_id=TID, student_no=f"{prefix}001", real_name="四端学生甲",
        class_id=cls.id, college_id=college.id, gender="M", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    two = StudentProfile(
        tenant_id=TID, student_no=f"{prefix}002", real_name="四端学生乙",
        class_id=cls.id, college_id=college.id, gender="M", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    db.add_all([one, two])
    db.flush()
    db.add_all([
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=cls.id, user_id=counselor.id,
            duty_type="PRIMARY", status="ACTIVE",
            effective_from=datetime.utcnow() - timedelta(days=1),
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
            role_code="COUNSELOR", scope_type="CLASS", ref_value=cls.class_name,
            status="ACTIVE",
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key=college_reviewer.login_name,
            teacher_name=college_reviewer.real_name, role_code="COLLEGE_ADMIN",
            scope_type="COLLEGE", ref_value=college.college_name, status="ACTIVE",
        ),
    ])
    ids = {
        "class": cls.id, "one": one.id, "two": two.id,
        "oneNo": one.student_no, "twoNo": two.student_no,
    }
    db.commit()
    db.close()
    return ids
'''


DASHBOARD_SEED = '''def _seed_classes(db_mode):
    """在 db_mode 之上补种 2 班 + 5 生，并返回真实学生主键。"""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2102", grade="2021", status="ACTIVE")
    db.add_all([a, b])
    db.flush()
    students_a = []
    students_b = []
    for i in range(3):
        row = StudentProfile(
            tenant_id=TID, student_no=f"A{i:03d}", real_name=f"甲{i}",
            class_id=a.id, current_stage="ORIENTATION",
            student_status="NORMAL", status="ACTIVE",
        )
        db.add(row)
        students_a.append(row)
    for i in range(2):
        row = StudentProfile(
            tenant_id=TID, student_no=f"B{i:03d}", real_name=f"乙{i}",
            class_id=b.id, current_stage="ORIENTATION",
            student_status="NORMAL", status="ACTIVE",
        )
        db.add(row)
        students_b.append(row)
    db.flush()
    db.add(TeacherStudentScope(
        tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
        role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2101",
        status="ACTIVE",
    ))
    db.commit()
    ids = {
        "A": a.id, "B": b.id,
        "A_STUDENT": students_a[0].id, "B_STUDENT": students_b[0].id,
    }
    db.close()
    return ids
'''


ROUTE_MATRIX = '''def _route_matrix(app) -> set[tuple[str, str]]:
    rows: set[tuple[str, str]] = set()
    for path, operations in app.openapi().get("paths", {}).items():
        for method in operations:
            verb = str(method).upper()
            if verb not in {"HEAD", "OPTIONS", "PARAMETERS"}:
                rows.add((verb, str(path)))
    return rows
'''


def repair_leave_fixture() -> None:
    path = Path("backend/tests/test_affairs_leave.py")
    text = replace_top_level_function(path.read_text(encoding="utf-8"), "_seed", ASSIGNEE_FIXTURE)
    path.write_text(text, encoding="utf-8")


def repair_hardening_tests() -> None:
    path = Path("backend/tests/test_affairs_four_end_hardening.py")
    text = path.read_text(encoding="utf-8")
    text = replace_top_level_function(text, "_seed_students", HARDENING_SEED)
    text = text.replace(
        '    paths = {route.path for route in client.app.routes}\n',
        '    paths = set(client.app.openapi().get("paths", {}))\n',
    )
    text = re.sub(
        r'\n    def boom\(\*_args, \*\*_kwargs\):\n        raise RuntimeError\("audit db unavailable"\)\n\n    monkeypatch\.setattr\(audit_log, "audit_insert", boom\)',
        '\n    monkeypatch.setattr(audit_log, "record", lambda *_args, **_kwargs: None)',
        text,
        count=1,
    )
    text = text.replace('school_year="2026-2027"', 'year_code="2026-2027"')
    path.write_text(text, encoding="utf-8")


def repair_route_matrix() -> None:
    path = Path("backend/tests/test_affairs_four_end_core_flow_matrix.py")
    text = replace_top_level_function(path.read_text(encoding="utf-8"), "_route_matrix", ROUTE_MATRIX)
    path.write_text(text, encoding="utf-8")


def repair_dashboard_tests() -> None:
    path = Path("backend/tests/test_affairs_dashboard.py")
    text = replace_top_level_function(path.read_text(encoding="utf-8"), "_seed_classes", DASHBOARD_SEED)
    text = text.replace('body = {"studentId": "1", "position": "MONITOR", "termCode": "2026-1"}',
                        'body = {"studentId": str(ids["A_STUDENT"]), "position": "MONITOR", "termCode": "2026-1"}')
    text = text.replace('assert r["data"]["studentName"] == "赵一凡" and r["data"]["studentNo"] == "2023115001"',
                        'assert r["data"]["studentName"] == "甲0" and r["data"]["studentNo"] == "A000"')
    text = text.replace('assert r2["data"]["items"][0]["studentName"] == "赵一凡"',
                        'assert r2["data"]["items"][0]["studentName"] == "甲0"')
    text = text.replace('assert r2["data"]["items"][0]["studentNo"] == "2023115001"',
                        'assert r2["data"]["items"][0]["studentNo"] == "A000"')
    text = text.replace('json={"studentId": "9", "position": "STUDY"}',
                        'json={"studentId": str(ids["B_STUDENT"]), "position": "STUDY"}')
    path.write_text(text, encoding="utf-8")


def retire_leave_from_legacy_student_detail() -> None:
    path = Path("backend/app/services/affairs_student_ledger_guard.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "from app.models import CsAuditTrail, CsDiscipline, CsGrant, CsLeave, CsServiceStudent, CsWorkOrder",
        "from app.models import CsAuditTrail, CsDiscipline, CsGrant, CsServiceStudent, CsWorkOrder",
    )
    text = re.sub(
        r'\n            leaves = db\.scalars\(select\(CsLeave\).*?\.all\(\)',
        '',
        text,
        count=1,
        flags=re.S,
    )
    text = text.replace('                "leaves": [service._leave_row(item, row) for item in leaves],\n', '')
    if "service._leave_row" in text or "select(CsLeave)" in text:
        raise RuntimeError("legacy student detail still renders leave records")
    path.write_text(text, encoding="utf-8")


def repair_campus_service_tests() -> None:
    path = Path("backend/tests/test_campus_service.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'assert det["code"] == 0 and len(det["data"]["leaves"]) == 1 and len(det["data"]["workOrders"]) == 1',
        'assert det["code"] == 0 and "leaves" not in det["data"] and len(det["data"]["workOrders"]) == 1',
    )
    text = text.replace(
        '    bad = client.post(f"/api/v1/campus-service/students/{ids[\'student\']}/void", headers=auth_headers,\n                      json={"reason": "x"}).json()\n',
        '    detail = client.get(f"/api/v1/campus-service/students/{ids[\'student\']}", headers=auth_headers).json()["data"]\n    version = detail["student"]["version"]\n    bad = client.post(f"/api/v1/campus-service/students/{ids[\'student\']}/void", headers=auth_headers,\n                      json={"reason": "x", "version": version}).json()\n',
    )
    text = text.replace('json={"reason": "重复台账予以作废"}).json()',
                        'json={"reason": "重复台账予以作废", "version": version}).json()')
    text = text.replace('    did = d.id\n', '    did, dver = d.id, int(d.version or 0)\n', 1)
    text = text.replace('json={"reason": "处分决定撤销"}).json()',
                        'json={"reason": "处分决定撤销", "version": dver}).json()')
    text = text.replace(
        '    h = client.post(f"/api/v1/campus-service/work-orders/{ids[\'wo\']}/handle", headers=auth_headers,\n                    json={"note": "已开具证明并交付学生", "close": True, "version": 0}).json()\n',
        '    detail = client.get(f"/api/v1/campus-service/work-orders/{ids[\'wo\']}", headers=auth_headers).json()["data"]\n    version = detail["order"]["version"]\n    h = client.post(f"/api/v1/campus-service/work-orders/{ids[\'wo\']}/handle", headers=auth_headers,\n                    json={"note": "已开具证明并交付学生", "close": True, "version": version}).json()\n',
    )
    path.write_text(text, encoding="utf-8")


def audit() -> None:
    leave = Path("backend/tests/test_affairs_leave.py").read_text(encoding="utf-8")
    hardening = Path("backend/tests/test_affairs_four_end_hardening.py").read_text(encoding="utf-8")
    ledger = Path("backend/app/services/affairs_student_ledger_guard.py").read_text(encoding="utf-8")
    required = (
        "AffairsCounselorAssignment" in leave,
        "leave_college01" in leave,
        "AffairsCounselorAssignment" in hardening,
        'set(client.app.openapi().get("paths", {}))' in hardening,
        'monkeypatch.setattr(audit_log, "record"' in hardening,
        'year_code="2026-2027"' in hardening,
        "service._leave_row" not in ledger,
    )
    if not all(required):
        raise RuntimeError("round2 affairs validation repair incomplete")


def main() -> None:
    repair_leave_fixture()
    repair_hardening_tests()
    repair_route_matrix()
    repair_dashboard_tests()
    retire_leave_from_legacy_student_detail()
    repair_campus_service_tests()
    audit()
    print("student affairs validation round2 repaired")


if __name__ == "__main__":
    main()
