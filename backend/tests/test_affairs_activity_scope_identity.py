from datetime import datetime, timedelta

from sqlalchemy import select
import pytest

from test_affairs_security import TID, _base
from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr

BASE = "/api/v1/student-affairs/activities"


def _actors(db_mode):
    from affairs_contract_test_support import ensure_role_user
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, StudentAccountLink, User, UserRole
    ids = _base(db_mode, counselor_scope=False, college_scope=False)
    for key, role_code, college, student in (("a", "YOUTH_LEAGUE", ids["col1"], None),
            ("b", "YOUTH_LEAGUE", ids["col2"], None), ("sa", "STUDENT", None, ids["A"]),
            ("sb", "STUDENT", None, ids["C"])):
        uid = ensure_role_user(role_code, "activity_scope_" + key, "活动范围验收" + key)
        with get_sessionmaker()() as db:
            user = db.get(User, uid)
            user.password_hash = hash_password(TEST_LOGIN_PASSWORD)
            user.must_change_password = False
            if student:
                user.user_type = "STUDENT"
                db.add(StudentAccountLink(tenant_id=TID, user_id=uid, student_id=student, link_status="ACTIVE", source="MANUAL"))
            else:
                role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == role_code))
                member = db.scalar(select(UserRole).where(UserRole.tenant_id == TID, UserRole.user_id == uid, UserRole.role_id == role.id))
                db.add(RoleAssignmentScope(tenant_id=TID, user_id=uid, user_role_id=member.id,
                    role_code=role_code, scope_type="COLLEGE", scope_id=college, status="ACTIVE",
                    effective_at=datetime.utcnow() - timedelta(days=1)))
            db.commit()
    return ids


def test_activity_scope_uses_stable_identity_for_create_update_list_and_enroll(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College
    ids = _actors(db_mode)
    with get_sessionmaker()() as db:
        first, other = db.get(College, ids["col1"]), db.get(College, ids["col2"])
        first.college_name = other.college_name = "同名学院"
        other.code = str(first.id)
        db.commit()
    a = _real_hdr(client, "activity_scope_a")
    b = _real_hdr(client, "activity_scope_b")
    sa = _real_hdr(client, "activity_scope_sa", client_type="STUDENT_MINI")
    sb = _real_hdr(client, "activity_scope_sb", client_type="STUDENT_MINI")
    ambiguous = client.post(BASE, headers=a, json={"activityName": "歧义范围不能创建", "scopeType": "COLLEGE", "scopeRef": "同名学院"})
    assert ambiguous.status_code in (400, 403), ambiguous.text
    created = client.post(BASE, headers=a, json={"activityName": "本院活动稳定编号", "creditValue": 1})
    assert created.status_code == 200, created.text
    row = created.json()["data"]
    for scope_type, ref in (("SCHOOL", ""), ("COLLEGE", f"id:{ids['col2']}")):
        changed = client.put(f"{BASE}/{row['activityId']}", headers=a,
            json={"activityName": "本院活动稳定编号", "scopeType": scope_type, "scopeRef": ref, "version": row["version"]})
        assert changed.status_code == 403, changed.text
    published = client.post(f"{BASE}/{row['activityId']}/publish", headers=a,
        json={"action": "PUBLISH", "version": row["version"]})
    assert published.status_code == 200, published.text
    listed = client.get(BASE, headers=b).json()["data"]["items"]
    assert row["activityId"] not in {item["activityId"] for item in listed}
    for headers, expected in ((sa, 200), (sb, 403)):
        enrolled = client.post(f"/api/v1/portal/affairs/activities/{row['activityId']}/enroll", headers=headers)
        assert enrolled.status_code == expected, enrolled.text


def test_ambiguous_legacy_activity_references_never_expand_to_matching_aliases(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivity, College
    ids = _actors(db_mode)
    with get_sessionmaker()() as db:
        first, other = db.get(College, ids["col1"]), db.get(College, ids["col2"])
        first.college_name = other.college_name = "历史同名学院"
        other.code = str(first.id)
        first.short_name = ""
        db.add_all([AffairsActivity(tenant_id=TID, activity_name="历史歧义活动", activity_type="ACTIVITY",
            scope_type="COLLEGE", scope_ref=ref, status="PUBLISHED") for ref in ("历史同名学院", str(first.id), "")])
        db.commit()
    for key in ("a", "b"):
        headers = _real_hdr(client, "activity_scope_" + key)
        response = client.get(BASE, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["items"] == []


def test_student_activity_history_and_more_pages_survive_after_signup_closes(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivity, AffairsActivitySignup
    ids = _actors(db_mode)
    with get_sessionmaker()() as db:
        for index in range(21):
            activity = AffairsActivity(tenant_id=TID, activity_name=f"已报名活动{index}", activity_type="ACTIVITY", scope_type="SCHOOL", status="ONGOING")
            db.add(activity); db.flush()
            db.add(AffairsActivitySignup(tenant_id=TID, activity_id=activity.id, student_id=ids["A"], signup_status="ENROLLED"))
        deleted = AffairsActivity(tenant_id=TID, activity_name="已删除活动不计入分页", activity_type="ACTIVITY", scope_type="SCHOOL", status="ONGOING", is_deleted=True)
        db.add(deleted); db.flush()
        db.add(AffairsActivitySignup(tenant_id=TID, activity_id=deleted.id, student_id=ids["A"], signup_status="ENROLLED"))
        db.commit()
    headers = _real_hdr(client, "activity_scope_sa", client_type="STUDENT_MINI")
    response = client.get("/api/v1/portal/affairs/activities/my", headers=headers, params={"page": 2, "pageSize": 20})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert len(data["mine"]) == 1 and data["mineTotal"] == 21 and data["mineHasMore"] is False
    assert data["available"] == []


def test_original_publisher_loses_school_activity_code_after_scope_shrinks(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import RoleAssignmentScope, User
    ids = _actors(db_mode)
    with get_sessionmaker()() as db:
        uid = db.scalar(select(User.id).where(User.tenant_id == TID, User.login_name == "activity_scope_a"))
        scope = db.scalar(select(RoleAssignmentScope).where(RoleAssignmentScope.tenant_id == TID, RoleAssignmentScope.user_id == uid))
        scope.scope_type, scope.scope_id = "SCHOOL", 0
        scope_id = scope.id
        db.commit()
    headers = _real_hdr(client, "activity_scope_a")
    response = client.post(BASE, headers=headers, json={"activityName": "原全校发布活动"})
    assert response.status_code == 200, response.text
    row = response.json()["data"]
    for command, action in (("publish", "PUBLISH"), ("transition", "ENROLL_CLOSE"), ("transition", "START")):
        result = client.post(f"{BASE}/{row['activityId']}/{command}", headers=headers, json={"action": action, "version": row["version"]})
        assert result.status_code == 200, result.text
        row = result.json()["data"]
    endpoint = f"/api/v1/mobile/teacher/affairs/activities/{row['activityId']}/checkin-token"
    assert client.get(endpoint, headers=headers).status_code == 200
    with get_sessionmaker()() as db:
        scope = db.get(RoleAssignmentScope, scope_id)
        scope.scope_type, scope.scope_id = "COLLEGE", ids["col1"]
        scope.version += 1
        db.commit()
    headers = _real_hdr(client, "activity_scope_a")
    assert client.get(endpoint, headers=headers).status_code == 403


@pytest.mark.parametrize("deleted_duplicate", [False, True])
def test_class_alias_collisions_keep_canonical_student_access_only(client, db_mode, deleted_duplicate):
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivity, SchoolClass
    ids = _actors(db_mode)
    with get_sessionmaker()() as db:
        first, other = db.get(SchoolClass, ids["cA"]), db.get(SchoolClass, ids["cC"])
        first.class_name = other.class_name = "同名班级"
        other.class_code = str(first.id)
        other.is_deleted = deleted_duplicate
        canonical = AffairsActivity(tenant_id=TID, activity_name="明确本班编号", activity_type="ACTIVITY",
            scope_type="CLASS", scope_ref=f"id:{first.id}", status="PUBLISHED")
        db.add(canonical)
        db.add_all([AffairsActivity(tenant_id=TID, activity_name="歧义历史班级", activity_type="ACTIVITY",
            scope_type="CLASS", scope_ref=ref, status="PUBLISHED") for ref in (str(first.id), first.class_name)])
        db.flush(); activity_id = str(canonical.id)
        db.commit()
    for key, expected in (("sa", {activity_id}), ("sb", set())):
        headers = _real_hdr(client, "activity_scope_" + key, client_type="STUDENT_MINI")
        response = client.get("/api/v1/portal/affairs/activities/my", headers=headers)
        assert response.status_code == 200, response.text
        assert {item["activityId"] for item in response.json()["data"]["available"]} == expected
