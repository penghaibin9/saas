"""困难认定/奖助申请并发串行化门测试。"""
from __future__ import annotations


TID = 1000000000000000001


def test_locked_self_student_uses_mysql_for_update(db_mode):
    from sqlalchemy import event
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    from app.services.affairs_student_application_lock import _locked_self_student

    db = get_sessionmaker()()
    cls = SchoolClass(
        tenant_id=TID, major_id=1, class_name="申请并发锁测试班",
        grade="2026", status="ACTIVE",
    )
    db.add(cls)
    db.flush()
    student = StudentProfile(
        tenant_id=TID, student_no="APPLOCK001", real_name="申请并发学生",
        class_id=cls.id, gender="F", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    db.add(student)
    db.commit()

    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(str(statement).upper())

    user = {
        "userId": "u-APPLOCK001", "studentNo": "APPLOCK001",
        "realName": "申请并发学生", "userType": "STUDENT",
        "currentRoleCode": "STUDENT", "tenantId": str(TID),
    }
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    event.listen(db.bind, "before_cursor_execute", capture)
    try:
        locked = _locked_self_student(db, user)
        assert int(locked.id) == int(student.id)
        assert any("FOR UPDATE" in sql for sql in statements)
    finally:
        event.remove(db.bind, "before_cursor_execute", capture)
        db.rollback()
        db.close()
        set_current_user(None)
        set_tenant(None)
