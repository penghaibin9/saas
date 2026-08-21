"""PR190 W3/P1：就业去向登记 PDF 的教职工访问必须同时满足 permission + dataScope。

历史 resolver 只看 `employment.student.view`，导致就业老师即使只授权 A 班，也能凭 fileId
读取 B 班学生登记表。这里用真实 MySQL 的 TeacherStudentScope + StudentProfile 当前班级
验证 resolver 与正式就业详情 `_assert_emp_student` 使用同一范围事实。
"""
from __future__ import annotations

from types import SimpleNamespace

from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.modules.employment.services import employment_destination_document_service as docs

TID = 1000000000000000001


def _seed_scope_fixture():
    from app.models import (
        College, EmpStudent, Major, SchoolClass, StudentProfile, TeacherStudentScope,
    )

    db = get_sessionmaker()()
    try:
        college = College(tenant_id=TID, college_name="W3软件学院", status="ACTIVE")
        db.add(college)
        db.flush()
        major = Major(
            tenant_id=TID, college_id=college.id, major_name="W3软件技术", status="ACTIVE"
        )
        db.add(major)
        db.flush()
        class_a = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name="W3就业A班",
            grade="2021",
            status="ACTIVE",
        )
        class_b = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name="W3就业B班",
            grade="2021",
            status="ACTIVE",
        )
        db.add_all([class_a, class_b])
        db.flush()

        stu_a = StudentProfile(
            tenant_id=TID,
            student_no="W3-A-001",
            real_name="范围内学生",
            class_id=class_a.id,
            gender="F",
            grade="2021",
            current_stage="EMPLOYMENT",
            student_status="NORMAL",
            status="ACTIVE",
        )
        stu_b = StudentProfile(
            tenant_id=TID,
            student_no="W3-B-001",
            real_name="范围外学生",
            class_id=class_b.id,
            gender="M",
            grade="2021",
            current_stage="EMPLOYMENT",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([stu_a, stu_b])
        db.flush()

        emp_a = EmpStudent(
            tenant_id=TID,
            student_id=stu_a.id,
            student_no=stu_a.student_no,
            name=stu_a.real_name,
            destination_type="SIGNED",
            company_name="范围内单位",
            verify_status="PENDING_VERIFY",
            record_status="ACTIVE",
        )
        emp_b = EmpStudent(
            tenant_id=TID,
            student_id=stu_b.id,
            student_no=stu_b.student_no,
            name=stu_b.real_name,
            destination_type="SIGNED",
            company_name="范围外单位",
            verify_status="PENDING_VERIFY",
            record_status="ACTIVE",
        )
        db.add_all([emp_a, emp_b])
        db.flush()

        db.add(TeacherStudentScope(
            tenant_id=TID,
            teacher_key="employment_scope01",
            teacher_name="就业范围老师",
            role_code="EMPLOYMENT_TEACHER",
            scope_type="CLASS",
            ref_value="W3就业A班",
            status="ACTIVE",
        ))
        db.commit()
        return int(emp_a.id), int(emp_b.id)
    finally:
        db.close()


def _teacher_user() -> dict:
    # 不伪造 TENANT_ALL。EMPLOYMENT_TEACHER 有 employment.* capability，具体学生范围
    # 必须由上面的 TeacherStudentScope 决定。
    return {
        "userId": "u_employment_scope01",
        "loginName": "employment_scope01",
        "realName": "就业范围老师",
        "userType": "TEACHER",
        "currentRoleCode": "EMPLOYMENT_TEACHER",
        "tenantId": str(TID),
        "activeContextId": "ctx_employment_scope01",
    }


def _file(emp_id: int):
    return SimpleNamespace(tenant_id=TID)


def _binding(emp_id: int):
    return SimpleNamespace(
        is_deleted=False,
        status="ACTIVE",
        is_current=True,
        biz_type=docs.DOC_BIZ_TYPE,
        biz_id=str(emp_id),
    )


def test_staff_with_view_permission_can_read_only_in_scope_destination_pdf(db_mode):
    """同一个有 employment.student.view 的老师：A 班允许，B 班必须 fail-closed。"""
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    emp_a, emp_b = _seed_scope_fixture()
    user = _teacher_user()

    db = get_sessionmaker()()
    try:
        assert docs._employment_destination_document_resolver(  # noqa: SLF001
            db, _file(emp_a), [_binding(emp_a)], user, "download"
        ) is True
        assert docs._employment_destination_document_resolver(  # noqa: SLF001
            db, _file(emp_b), [_binding(emp_b)], user, "download"
        ) is False
    finally:
        db.close()


def test_staff_with_view_permission_but_no_scope_is_denied(db_mode):
    """有就业模块权限但未配置任何 scope，不得退化成全校可读。"""
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    emp_a, _ = _seed_scope_fixture()
    user = _teacher_user()
    user["loginName"] = "employment_unscoped01"
    user["userId"] = "u_employment_unscoped01"

    db = get_sessionmaker()()
    try:
        assert docs._employment_destination_document_resolver(  # noqa: SLF001
            db, _file(emp_a), [_binding(emp_a)], user, "download"
        ) is False
    finally:
        db.close()
