"""Organization ownership and student membership are separate authorization boundaries."""
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from test_affairs_security import TID, _base


@pytest.fixture(autouse=True)
def _request_tenant(db_mode):
    from app.core.context import get_tenant, set_tenant
    previous = get_tenant()
    set_tenant(TID)
    try:
        yield
    finally:
        set_tenant(previous)


def _seed(db_mode, monkeypatch):
    from app.core import affairs_security as security
    from app.db.session import get_sessionmaker
    from app.models import (AffairsClub, AffairsClubMember, AffairsStudentOrg, AffairsOrgPosition,
                            AffairsLeagueDev, StudentProfile)
    ids = _base(db_mode)
    ctx = security.StudentAffairsSecurityContext(
        user_id="701", login_name="college-scope", tenant_id=TID,
        role_codes={"COLLEGE_ADMIN"}, permission_codes=set(), sensitive_permissions=set(),
        scope_type="COLLEGE", college_ids={ids["col1"]}, is_scope_configured=True,
    )
    monkeypatch.setattr(security, "build_affairs_context", lambda user, db=None: ctx)
    with get_sessionmaker()() as db:
        clubs = [AffairsClub(tenant_id=TID, club_name=name, club_type="INTEREST", college_id=col,
                             status="ACTIVE", member_count=1) for name, col in
                 [("本院社团", ids["col1"]), ("他院社团", ids["col2"]), ("校级社团", None)]]
        orgs = [AffairsStudentOrg(tenant_id=TID, org_name=name, org_type="STUDENT_UNION",
                                 level=level, college_id=col, status="ACTIVE") for name, level, col in
                [("本院组织", "COLLEGE", ids["col1"]), ("他院组织", "COLLEGE", ids["col2"]),
                 ("校级组织", "SCHOOL", None)]]
        db.add_all(clubs + orgs); db.flush()
        foreign_member = AffairsClubMember(tenant_id=TID, club_id=clubs[1].id, student_id=ids["A"],
                                          role="MEMBER", status="ACTIVE")
        foreign_position = AffairsOrgPosition(tenant_id=TID, org_id=orgs[1].id, student_id=ids["A"],
                                             position="成员", status="ACTIVE")
        development = AffairsLeagueDev(tenant_id=TID, student_id=ids["C"], dev_type="PARTY",
                                        current_stage="APPLICANT", status="ONGOING")
        classmate = StudentProfile(tenant_id=TID, student_no="SCOPE-CLASSMATE", real_name="同班未授权学生",
                                   class_id=ids["cA"], college_id=ids["col1"], current_stage="CAMPUS",
                                   student_status="NORMAL", status="ACTIVE")
        db.add(classmate); db.flush()
        classmate_dev = AffairsLeagueDev(tenant_id=TID, student_id=classmate.id, dev_type="PARTY",
                                         current_stage="APPLICANT", status="ONGOING")
        own_members = [AffairsClubMember(tenant_id=TID, club_id=clubs[0].id, student_id=sid,
                                         role="MEMBER", status="ACTIVE") for sid in [ids["A"], ids["C"]]]
        db.add_all([foreign_member, foreign_position, development, classmate_dev, *own_members]); db.flush()
        ids.update(clubs=[r.id for r in clubs], orgs=[r.id for r in orgs],
                   member=foreign_member.id, position=foreign_position.id, development=development.id,
                   classmate_dev=classmate_dev.id)
        db.commit()
    return ids, ctx


def test_college_can_manage_own_organization_but_not_foreign_or_school(db_mode, monkeypatch):
    from app.services import affairs_club_service as club, affairs_org_service as org
    ids, ctx = _seed(db_mode, monkeypatch)
    user = {"userId": "701", "currentRoleCode": "COLLEGE_ADMIN"}
    assert {r["clubId"] for r in club.list_clubs(user)[0]} == {str(ids["clubs"][0])}
    assert {r["orgId"] for r in org.list_orgs(user)[0]} == {str(ids["orgs"][0])}
    assert {r["studentId"] for r in club.list_members(ids["clubs"][0], user)} == {str(ids["A"])}
    for entity_id in ids["clubs"][1:]:
        with pytest.raises(AppException):
            club.list_members(entity_id, user)
    for entity_id in ids["orgs"][1:]:
        with pytest.raises(AppException):
            org.list_positions(entity_id, user)
    with pytest.raises(AppException):
        club.remove_member(ids["member"], user)
    with pytest.raises(AppException):
        org.dismiss(ids["position"], user, expected_version=0)
    allowed = org.appoint(ids["orgs"][0], SimpleNamespace(studentId=ids["A"], position="负责人"), user)
    assert allowed["studentId"] == str(ids["A"])
    with pytest.raises(AppException):
        org.appoint(ids["orgs"][0], SimpleNamespace(studentId=ids["C"], position="负责人"), user)
    ctx.scope_type = "TENANT_ALL"
    assert len(club.list_clubs(user)[0]) == 3
    assert len(org.list_orgs(user)[0]) == 3


def test_organization_creation_validates_ownership_and_student_ids(db_mode, monkeypatch):
    from app.services import affairs_club_service as club, affairs_org_service as org
    ids, ctx = _seed(db_mode, monkeypatch)
    user = {"userId": "701", "currentRoleCode": "COLLEGE_ADMIN"}
    with pytest.raises(AppException):
        club.create_club(SimpleNamespace(clubName="跨院新社团", collegeId=ids["col2"]), user)
    with pytest.raises(AppException):
        club.create_club(SimpleNamespace(clubName="本院错误负责人", collegeId=ids["col1"],
                                         presidentStudentId=ids["C"]), user)
    with pytest.raises(AppException):
        org.create_org(SimpleNamespace(orgName="伪装院级组织", level="SCHOOL", collegeId=ids["col1"]), user)
    own = club.create_club(SimpleNamespace(clubName="本院新社团", collegeId=ids["col1"],
                                          presidentStudentId=ids["A"]), user)
    assert own["collegeId"] == str(ids["col1"])


def test_league_writes_and_resume_do_not_expand_named_student_to_class(db_mode, monkeypatch):
    from app.services import affairs_league_service as league, affairs_org_service as org
    ids, ctx = _seed(db_mode, monkeypatch)
    user = {"userId": "701", "currentRoleCode": "COLLEGE_ADMIN"}
    with pytest.raises(AppException):
        league.list_stages(ids["development"], user)
    with pytest.raises(AppException):
        league.create_dev(SimpleNamespace(studentId=ids["C"], devType="PARTY"), user)
    with pytest.raises(AppException):
        org.student_resume(ids["C"], user)
    own = league.create_dev(SimpleNamespace(studentId=ids["A"], devType="PARTY"), user)
    assert own["studentId"] == str(ids["A"])
    ctx.scope_type = "STUDENT"
    ctx.college_ids.clear()
    ctx.student_ids = {ids["A"]}
    rows, total = league.list_dev(user)
    assert total == 1 and rows[0]["devId"] == own["devId"]
    with pytest.raises(AppException):
        league.list_stages(ids["classmate_dev"], user)
