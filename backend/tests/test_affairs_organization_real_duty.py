from datetime import datetime, timedelta


def test_normal_youth_accounts_keep_organization_and_student_scopes_separate(client, db_mode):
    from sqlalchemy import select
    from affairs_contract_test_support import ensure_role_user
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, User, UserRole
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    from test_affairs_security import TID, _base
    ids = _base(db_mode)
    users = {}
    for key, college in (("a", ids["col1"]), ("b", ids["col2"])):
        users[key] = ensure_role_user("YOUTH_LEAGUE", "youth_scope_" + key, "团学范围验收" + key)
        with get_sessionmaker()() as db:
            role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "YOUTH_LEAGUE"))
            member = db.scalar(select(UserRole).where(UserRole.user_id == users[key], UserRole.role_id == role.id))
            db.add(RoleAssignmentScope(tenant_id=TID, user_id=users[key], user_role_id=member.id,
                role_code="YOUTH_LEAGUE", scope_type="COLLEGE", scope_id=college, status="ACTIVE",
                effective_at=datetime.utcnow() - timedelta(days=1)))
            user = db.get(User, users[key]); user.password_hash = hash_password(TEST_LOGIN_PASSWORD); user.must_change_password = False
            db.commit()
    headers = {key: _real_hdr(client, "youth_scope_" + key) for key in users}
    base = "/api/v1/student-affairs"
    clubs = {}
    orgs = {}
    for key, college, student in (("a", ids["col1"], ids["A"]), ("b", ids["col2"], ids["C"])):
        response = client.post(base + "/clubs", headers=headers[key], json={"clubName": "本院社团" + key, "collegeId": college})
        assert response.status_code == 200, response.text
        clubs[key] = response.json()["data"]["clubId"]
        approved = client.post(f"{base}/clubs/{clubs[key]}/review", headers=headers[key],
            json={"action": "APPROVE", "version": response.json()["data"]["version"]})
        assert approved.status_code == 200, approved.text
        response = client.post(base + "/organizations", headers=headers[key], json={"orgName": "本院组织" + key, "level": "COLLEGE", "collegeId": college})
        assert response.status_code == 200, response.text
        orgs[key] = response.json()["data"]["orgId"]
        member = client.post(f"{base}/clubs/{clubs[key]}/members", headers=headers[key], json={"studentId": student})
        assert member.status_code == 200, member.text
        position = client.post(f"{base}/organizations/{orgs[key]}/positions", headers=headers[key], json={"studentId": student, "position": "成员"})
        assert position.status_code == 200, position.text
        development = client.post(base + "/party-league/dev", headers=headers[key], json={"studentId": student, "devType": "PARTY"})
        assert development.status_code == 200, development.text
    assert client.get(f"{base}/clubs/{clubs['b']}/members", headers=headers["a"]).status_code == 403
    assert client.post(f"{base}/clubs/{clubs['b']}/members", headers=headers["a"], json={"studentId": ids["A"]}).status_code == 403
    assert client.post(f"{base}/clubs/{clubs['a']}/members", headers=headers["a"], json={"studentId": ids["C"]}).status_code == 403
    assert client.post(f"{base}/organizations/{orgs['b']}/positions", headers=headers["a"], json={"studentId": ids["A"], "position": "成员"}).status_code == 403
    assert client.post(f"{base}/organizations/{orgs['a']}/positions", headers=headers["a"], json={"studentId": ids["C"], "position": "成员"}).status_code == 403
    assert client.post(base + "/party-league/dev", headers=headers["a"], json={"studentId": ids["C"], "devType": "PARTY"}).status_code == 403
    foreign_create = client.post(base + "/organizations", headers=headers["a"], json={"orgName": "不应创建的他院组织", "level": "COLLEGE", "collegeId": ids["col2"]})
    assert foreign_create.status_code == 403, foreign_create.text


def test_normal_college_affairs_orientation_commands_use_linked_profile_scope(client, db_mode):
    from sqlalchemy import select
    from affairs_contract_test_support import ensure_role_user
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent, Role, RoleAssignmentScope, StudentProfile, User, UserRole
    from app.services.orientation_flow_service import ensure_student_steps
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    from test_affairs_security import TID, _base
    from test_orientation_o3_self_service import _seed_o3
    school = _base(db_mode); incoming = _seed_o3(db_mode)
    uid = ensure_role_user("STUDENT_AFFAIRS_COLLEGE", "orientation_college_scope", "学院迎新验收人")
    with get_sessionmaker()() as db:
        for target_id, source_id in ((incoming["profileId"], school["A"]), (incoming["otherProfileId"], school["C"])):
            target = db.get(StudentProfile, target_id); source = db.get(StudentProfile, source_id)
            target.class_id, target.major_id, target.college_id = source.class_id, source.major_id, source.college_id
        own = db.get(OrientationStudent, incoming["orientationId"])
        own.blocked_step = "INFO"
        foreign = OrientationStudent(tenant_id=TID, batch_id=own.batch_id, student_id=incoming["otherProfileId"],
            name="他院迎新测试生", admission_no="REAL-SCOPE-FOREIGN", source_type="MANUAL", source_record_id="REAL-SCOPE-FOREIGN",
            identity_status="LINKED", record_status="ACTIVE", blocked_step="INFO", blocked_reason="原有他院核验事项")
        db.add(foreign); db.flush(); ensure_student_steps(db, foreign, status_source="PROCESS_FACT")
        foreign_id = foreign.id; batch_id = own.batch_id
        role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "STUDENT_AFFAIRS_COLLEGE"))
        member = db.scalar(select(UserRole).where(UserRole.user_id == uid, UserRole.role_id == role.id))
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=uid, user_role_id=member.id,
            role_code="STUDENT_AFFAIRS_COLLEGE", scope_type="COLLEGE", scope_id=school["col1"], status="ACTIVE",
            effective_at=datetime.utcnow() - timedelta(days=1)))
        account = db.get(User, uid); account.password_hash = hash_password(TEST_LOGIN_PASSWORD); account.must_change_password = False
        db.commit()
    header = _real_hdr(client, "orientation_college_scope")
    root = "/api/v1/orientation"
    listing = client.get(root + "/progress", headers=header, params={"batchId": batch_id, "pageSize": 1})
    assert listing.status_code == 200, listing.text
    assert listing.json()["data"]["total"] == 1
    assert listing.json()["data"]["items"][0]["id"] == str(incoming["orientationId"])
    for method, url, body in (("post", f"/students/{foreign_id}/void", {"reason": "越院作废应被拒绝"}),
            ("put", f"/progress/{foreign_id}/blocked", {"blockedStep": "INFO", "blockedReason": "越院改阻断应被拒绝"}),
            ("post", f"/progress/{foreign_id}/resolve", {"note": "越院解除阻断应被拒绝"})):
        rejected = getattr(client, method)(root + url, headers=header, json=body)
        assert rejected.status_code == 403, rejected.text
    accepted = client.put(root + f"/progress/{incoming['orientationId']}/blocked", headers=header,
        json={"blockedStep": "INFO", "blockedReason": "本院正常核验事项"})
    assert accepted.status_code == 200, accepted.text
    with get_sessionmaker()() as db:
        foreign = db.get(OrientationStudent, foreign_id)
        assert not foreign.is_deleted and foreign.blocked_reason == "原有他院核验事项"
