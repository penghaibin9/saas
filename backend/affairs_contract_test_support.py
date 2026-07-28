"""学工测试显式合同助手。

本模块不会被 pytest 自动加载，也不会 monkey patch TestClient。
测试必须主动调用 post_versioned / ensure_workflow_assignees，源码中可直接看到
乐观锁版本和真实受理人准备过程。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import select


TID = 1000000000000000001

_VERSION_ROUTES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"/student-affairs/leave/(\d+)/(?:approve|reject)$"), "CsLeave"),
    (re.compile(r"/student-affairs/activities/(\d+)/(?:publish|transition|confirm|unconfirm|archive)$"), "AffairsActivity"),
    (re.compile(r"/student-affairs/volunteer/records/(\d+)/(?:confirm|reject)$"), "AffairsVolunteerRecord"),
    (re.compile(r"/student-affairs/second-class/appeals/(\d+)/review$"), "AffairsCreditAppeal"),
    (re.compile(r"/student-affairs/aid/applications/(\d+)/(?:review|publicity-confirm|resubmit|adjust|adjust-review)$"), "AidApply"),
    (re.compile(r"/student-affairs/aid/objections/(\d+)/review$"), "AidObjection"),
    (re.compile(r"/student-affairs/funding/applications/(\d+)/(?:review|publicity-confirm|disburse|appeal)$"), "FundingApplication"),
    (re.compile(r"/student-affairs/funding/appeals/(\d+)/review$"), "FundingAppeal"),
    (re.compile(r"/student-affairs/clubs/(\d+)/(?:review|disband)$"), "AffairsClub"),
    (re.compile(r"/student-affairs/counselor-eval/evals/(\d+)/(?:publish|appeal|appeal-review)$"), "CounselorEval"),
    (re.compile(r"/student-affairs/counselor-assessment/assessments/(\d+)/score$"), "AffairsCounselorAssessment"),
    (re.compile(r"/student-affairs/counselor-assessment/periods/(\d+)/publish$"), "AffairsCounselorAssessmentPeriod"),
    (re.compile(r"/student-affairs/discipline/cases/(\d+)/(?:submit|review|deliver|remove|remove-review)$"), "DisciplineCase"),
    (re.compile(r"/student-affairs/discipline/appeals/(\d+)/review$"), "DisciplineAppeal"),
    (re.compile(r"/student-affairs/dorm/transfers/(\d+)/review$"), "DormTransfer"),
    (re.compile(r"/student-affairs/dorm/exceptions/(\d+)/handle$"), "CsDormException"),
    (re.compile(r"/student-affairs/dorm/beds/(\d+)/checkout$"), "DormBed"),
    (re.compile(r"/student-affairs/risk/records/(\d+)/(?:assign|process|follow|transfer|escalate|takeover|close|reopen)$"), "AffairsRiskRecord"),
    (re.compile(r"/student-affairs/talks/(\d+)/(?:record|follow-up)$"), "TalkRecord"),
    (re.compile(r"/student-affairs/party-league/dev/(\d+)/(?:advance|terminate)$"), "AffairsLeagueDev"),
    (re.compile(r"/student-affairs/organizations/(\d+)/(?:review|disband)$"), "AffairsStudentOrg"),
    (re.compile(r"/student-affairs/organizations/positions/(\d+)/dismiss$"), "AffairsOrgPosition"),
    (re.compile(r"/student-affairs/work-study/posts/(\d+)/(?:publish|close)$"), "WorkStudyPost"),
    (re.compile(r"/student-affairs/work-study/records/(\d+)/action$"), "WorkStudyRecord"),
    (re.compile(r"/student-affairs/student-loans/(\d+)/(?:review|confirm)$"), "StudentLoan"),
    (re.compile(r"/student-affairs/loans/(\d+)/(?:review|confirm)$"), "StudentLoan"),
    (re.compile(r"/student-affairs/fee-reductions/(\d+)/(?:issue|review|confirm)$"), "FeeReduction"),
    (re.compile(r"/student-affairs/mental/referrals/(\d+)/(?:follow|escalate|close)$"), "PsyReferral"),
)

_NODE_ROLE = {
    "COUNSELOR_REVIEW": "COUNSELOR",
    "CLASS_REVIEW": "COUNSELOR",
    "COLLEGE_REVIEW": "COLLEGE_ADMIN",
    "STUDENT_AFFAIRS_REVIEW": "STUDENT_AFFAIRS_ADMIN",
    "SA_OFFICE_REVIEW": "STUDENT_AFFAIRS_ADMIN",
    "SA_OFFICE_FINAL": "STUDENT_AFFAIRS_ADMIN",
    "SCHOOL_REVIEW": "SCHOOL_ADMIN",
}

_ROLE_LOGIN = {
    "COUNSELOR": "counselor01",
    "COLLEGE_ADMIN": "college_admin01",
    "STUDENT_AFFAIRS_ADMIN": "sa_admin01",
    "SCHOOL_ADMIN": "school_admin01",
    "DORM_MANAGER": "dorm01",
}

_ROLE_NAME = {
    "COUNSELOR": "测试辅导员",
    "COLLEGE_ADMIN": "测试学院管理员",
    "STUDENT_AFFAIRS_ADMIN": "测试学工处管理员",
    "SCHOOL_ADMIN": "测试学校管理员",
    "DORM_MANAGER": "测试宿管",
}


def current_version(url: str) -> int:
    from app import models
    from app.db.session import get_sessionmaker

    path = str(url).split("?", 1)[0]
    for pattern, model_name in _VERSION_ROUTES:
        match = pattern.search(path)
        if not match:
            continue
        model = getattr(models, model_name, None)
        if model is None:
            raise AssertionError(f"测试版本模型不存在：{model_name}（{path}）")
        db = get_sessionmaker()()
        try:
            row = db.get(model, int(match.group(1)))
            assert row is not None and not getattr(row, "is_deleted", False), f"测试记录不存在：{path}"
            return int(getattr(row, "version", 0) or 0)
        finally:
            db.close()
    raise AssertionError(f"未登记的版本化测试路由：{path}")


def versioned_payload(url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(body or {})
    payload.setdefault("version", current_version(url))
    return payload


def post_versioned(client, url: str, *, headers=None, json=None, **kwargs):
    """显式模拟真实页面：读取当前详情版本后提交写操作。

    同时发送 JSON version 和 x-expected-version，覆盖无 Pydantic Body 的历史端点；
    生产接口仍必须显式校验版本，本助手不会重试或吞掉冲突。
    """
    payload = versioned_payload(url, json)
    request_headers = dict(headers or {})
    request_headers.setdefault("x-expected-version", str(payload["version"]))
    return client.post(url, headers=request_headers, json=payload, **kwargs)


def expire_publicity(model_name: str, entity_id: int, *, days: int = 2) -> None:
    """显式把测试公示记录推进到到期状态，不允许生产创建 0 天公示。"""
    from app import models
    from app.db.session import get_sessionmaker

    model = getattr(models, model_name)
    db = get_sessionmaker()()
    try:
        row = db.get(model, int(entity_id))
        assert row is not None and not getattr(row, "is_deleted", False), (
            f"测试公示记录不存在：{model_name}#{entity_id}"
        )
        assert hasattr(row, "publicity_at"), f"模型没有 publicity_at：{model_name}"
        row.publicity_at = datetime.utcnow() - timedelta(days=max(1, int(days)))
        db.commit()
    finally:
        db.close()


def _ensure_role_user(db, role_code: str, login_name: str | None = None, real_name: str | None = None):
    from app.models import Role, User, UserRole

    role = db.scalars(select(Role).where(
        Role.tenant_id == TID,
        Role.role_code == role_code,
        Role.is_deleted.is_(False),
    )).first()
    if role is None:
        role = Role(
            tenant_id=TID, role_code=role_code,
            role_name=_ROLE_NAME.get(role_code, f"测试{role_code}"),
            role_type="SYSTEM", status="ACTIVE",
        )
        db.add(role)
        db.flush()
    else:
        role.status = "ACTIVE"
        role.is_deleted = False

    login = login_name or _ROLE_LOGIN.get(role_code, f"pytest_{role_code.lower()}")
    user = db.scalars(select(User).where(
        User.tenant_id == TID,
        User.login_name == login,
    )).first()
    if user is None:
        user = User(
            tenant_id=TID, login_name=login,
            real_name=real_name or _ROLE_NAME.get(role_code, f"测试{role_code}"),
            password_hash="test-only", user_type="TEACHER", status="ACTIVE",
        )
        db.add(user)
        db.flush()
    else:
        user.real_name = real_name or user.real_name or _ROLE_NAME.get(role_code, f"测试{role_code}")
        user.status = "ACTIVE"
        user.is_deleted = False

    link = db.scalars(select(UserRole).where(
        UserRole.tenant_id == TID,
        UserRole.user_id == user.id,
        UserRole.role_id == role.id,
    )).first()
    if link is None:
        db.add(UserRole(
            tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE",
        ))
    else:
        link.status = "ACTIVE"
        link.is_deleted = False
    return user


def ensure_role_user(role_code: str, login_name: str | None = None, real_name: str | None = None) -> int:
    """建立可核验的真实数据库角色用户，返回 User.id。"""
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        user = _ensure_role_user(db, role_code, login_name=login_name, real_name=real_name)
        db.commit()
        return int(user.id)
    finally:
        db.close()


def role_headers(role_code: str, login_name: str | None = None, real_name: str | None = None) -> dict[str, str]:
    """签发测试专用真实角色令牌；userId 使用 db-<User.id>，可命中真实待办受理人。"""
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        user = _ensure_role_user(db, role_code, login_name=login_name, real_name=real_name)
        db.commit()
        uid = int(user.id)
        login = str(user.login_name)
        name = str(user.real_name or login)
    finally:
        db.close()
    token = create_access_token({
        "userId": f"db-{uid}", "loginName": login, "realName": name,
        "userType": "TEACHER", "tid": "test-school", "tenantId": str(TID),
        "activeContextId": f"ctx_{login}", "currentRoleCode": role_code,
        "clientType": "PC",
    })
    return {"Authorization": f"Bearer {token}"}


def ensure_workflow_assignees(
    student_ids: int | Iterable[int],
    nodes: Iterable[str] = (
        "COUNSELOR_REVIEW", "COLLEGE_REVIEW", "STUDENT_AFFAIRS_REVIEW",
        "SA_OFFICE_REVIEW", "SA_OFFICE_FINAL", "SCHOOL_REVIEW",
    ),
) -> dict[str, int]:
    """为测试学生显式建立真实用户、角色、辅导员责任和学院范围。"""
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, SchoolClass, StudentProfile,
        TeacherStudentScope,
    )

    ids = [int(student_ids)] if isinstance(student_ids, int) else [int(value) for value in student_ids]
    db = get_sessionmaker()()
    try:
        requested_nodes = {node for node in nodes if node in _NODE_ROLE}
        role_users = {
            role_code: _ensure_role_user(db, role_code)
            for role_code in {_NODE_ROLE[node] for node in requested_nodes}
        }
        users = {node: role_users[_NODE_ROLE[node]] for node in requested_nodes}
        for student_id in ids:
            student = db.get(StudentProfile, student_id)
            assert student is not None and not student.is_deleted, f"测试学生不存在：{student_id}"
            school_class = db.get(SchoolClass, int(student.class_id)) if student.class_id else None
            if any(node in {"COUNSELOR_REVIEW", "CLASS_REVIEW"} for node in nodes):
                assert school_class is not None, f"测试学生未配置班级：{student_id}"
                counselor = users.get("COUNSELOR_REVIEW") or users.get("CLASS_REVIEW")
                school_class.counselor_id = counselor.id
                assignment = db.scalars(select(AffairsCounselorAssignment).where(
                    AffairsCounselorAssignment.tenant_id == TID,
                    AffairsCounselorAssignment.class_id == school_class.id,
                    AffairsCounselorAssignment.user_id == counselor.id,
                    AffairsCounselorAssignment.status == "ACTIVE",
                    AffairsCounselorAssignment.is_deleted.is_(False),
                )).first()
                if assignment is None:
                    db.add(AffairsCounselorAssignment(
                        tenant_id=TID, class_id=school_class.id, user_id=counselor.id,
                        duty_type="PRIMARY", status="ACTIVE",
                        effective_from=datetime.utcnow() - timedelta(days=1),
                    ))

            if "COLLEGE_REVIEW" in nodes:
                college = db.get(College, int(student.college_id)) if student.college_id else None
                if college is None:
                    college = College(
                        tenant_id=TID,
                        college_name=f"测试学院-{student_id}",
                        code=f"TEST-COL-{student_id}",
                        status="ACTIVE",
                    )
                    db.add(college)
                    db.flush()
                    student.college_id = college.id
                reviewer = users["COLLEGE_REVIEW"]
                scope = db.scalars(select(TeacherStudentScope).where(
                    TeacherStudentScope.tenant_id == TID,
                    TeacherStudentScope.teacher_key == reviewer.login_name,
                    TeacherStudentScope.scope_type == "COLLEGE",
                    TeacherStudentScope.ref_value == college.college_name,
                    TeacherStudentScope.status == "ACTIVE",
                    TeacherStudentScope.is_deleted.is_(False),
                )).first()
                if scope is None:
                    db.add(TeacherStudentScope(
                        tenant_id=TID, teacher_key=reviewer.login_name,
                        teacher_name=reviewer.real_name, role_code="COLLEGE_ADMIN",
                        scope_type="COLLEGE", ref_value=college.college_name,
                        status="ACTIVE",
                    ))
        db.commit()
        return {role_code: int(user.id) for role_code, user in role_users.items()}
    finally:
        db.close()


def ensure_owner_scope(login_name: str, student_id: int, role_code: str = "COUNSELOR") -> None:
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope

    db = get_sessionmaker()()
    try:
        student = db.get(StudentProfile, int(student_id))
        assert student is not None and student.class_id, f"测试学生班级不存在：{student_id}"
        school_class = db.get(SchoolClass, int(student.class_id))
        assert school_class is not None
        exists = db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == TID,
            TeacherStudentScope.teacher_key == login_name,
            TeacherStudentScope.scope_type == "CLASS",
            TeacherStudentScope.ref_value == school_class.class_name,
            TeacherStudentScope.status == "ACTIVE",
            TeacherStudentScope.is_deleted.is_(False),
        )).first()
        if exists is None:
            db.add(TeacherStudentScope(
                tenant_id=TID, teacher_key=login_name, teacher_name=login_name,
                role_code=role_code, scope_type="CLASS",
                ref_value=school_class.class_name, status="ACTIVE",
            ))
        db.commit()
    finally:
        db.close()
