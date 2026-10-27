from datetime import datetime, timedelta

BASE = "/api/v1/student-affairs/counselor-eval"


def actors(client, db_mode):
    from sqlalchemy import select
    from affairs_contract_test_support import ensure_role_user
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, SchoolClass, User, UserRole
    from test_affairs_security import TID, _base
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    ids = _base(db_mode)
    specs = {"school": ("ORG_PERSONNEL", "SCHOOL", 0), "reviewer": ("ORG_PERSONNEL", "SCHOOL", 0),
             "college": ("ORG_PERSONNEL", "COLLEGE", ids["col1"]),
             "a": ("COUNSELOR", "CLASS", ids["cA"]), "b": ("COUNSELOR", "CLASS", ids["cC"])}
    users = {key: ensure_role_user(code, login_name="eval_" + key, real_name="考评验收" + key)
             for key, (code, _, _) in specs.items()}
    ensure_role_user("ORG_PERSONNEL", login_name="eval_a", real_name="考评验收a")
    role_ids = {}
    with get_sessionmaker()() as db:
        for key, (code, kind, scope_id) in specs.items():
            role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == code))
            member = db.scalar(select(UserRole).where(UserRole.user_id == users[key], UserRole.role_id == role.id))
            db.add(RoleAssignmentScope(tenant_id=TID, user_id=users[key], user_role_id=member.id,
                role_code=code, scope_type=kind, scope_id=scope_id, status="ACTIVE",
                effective_at=datetime.utcnow() - timedelta(days=1)))
            db.get(User, users[key]).password_hash = hash_password(TEST_LOGIN_PASSWORD)
            db.get(User, users[key]).must_change_password = False
            role_ids[key] = role.id
        role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "ORG_PERSONNEL"))
        member = db.scalar(select(UserRole).where(UserRole.user_id == users["a"], UserRole.role_id == role.id))
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=users["a"], user_role_id=member.id,
            role_code="ORG_PERSONNEL", scope_type="SCHOOL", scope_id=0, status="ACTIVE",
            effective_at=datetime.utcnow() - timedelta(days=1)))
        db.get(SchoolClass, ids["cA"]).counselor_id = users["a"]
        db.get(SchoolClass, ids["cC"]).counselor_id = users["b"]
        db.commit(); own_role = role.id

    def login(key, own_management=False):
        header = _real_hdr(client, "eval_" + key)
        role_id = own_role if own_management else role_ids[key]
        response = client.post("/api/v1/auth/switch-role", headers=header,
            json={"contextId": f"role:{role_id}", "clientType": "PC"})
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["data"]["accessToken"]}
    return {key: login(key) for key in specs}, users, login


def create(client, header, key="eval_a", **extra):
    return client.post(BASE + "/evals", headers=header, json={
        "periodCode": "2026-2027-1", "counselorKey": key, "scores": {"x": 80}, **extra})


def test_eval_current_college_scope_and_self_recusal(client, db_mode):
    headers, ids, login = actors(client, db_mode)
    a = create(client, headers["school"]).json()["data"]
    b = create(client, headers["school"], "eval_b").json()["data"]
    response = client.get(BASE + "/evals", headers=headers["college"])
    assert response.status_code == 200
    assert {r["evalId"] for r in response.json()["data"]["items"]} == {a["evalId"]}
    assert create(client, headers["college"], "eval_b", version=b["version"]).status_code == 403
    assert client.post(BASE + f"/evals/{a['evalId']}/publish", headers=headers["college"],
                       json={"version": a["version"]}).status_code == 403
    own = login("a", own_management=True)
    for key in ("eval_a", str(ids["a"]), "db-" + str(ids["a"])):
        assert create(client, own, key, version=a["version"]).status_code == 403
    assert client.post(BASE + f"/evals/{a['evalId']}/publish", headers=own,
                       json={"version": a["version"]}).status_code == 403
    # 普通评分与发布允许同一人，学校终审不是一律换人。
    published = client.post(BASE + f"/evals/{a['evalId']}/publish", headers=headers["school"],
                            json={"version": a["version"]})
    assert published.status_code == 200, published.text
    assert client.post(BASE + f"/evals/{a['evalId']}/appeal", headers=headers["b"],
                       json={"reason": "不能对另一位老师考评申诉", "version": published.json()["data"]["version"]}).status_code == 403
    assert client.post(BASE + f"/evals/{a['evalId']}/appeal", headers=headers["school"],
                       json={"reason": "不能代替本人提交申诉", "version": published.json()["data"]["version"]}).status_code == 403
    from affairs_contract_test_support import ensure_role_user
    from app.db.session import get_sessionmaker
    from app.models import CounselorEval
    ensure_role_user("COUNSELOR", login_name=str(ids["a"]), real_name="数字登录名对照账号")
    with get_sessionmaker()() as db:
        legacy = CounselorEval(tenant_id=1000000000000000001, period_code="2026-ambiguous",
            counselor_key=str(ids["a"]), counselor_name="历史归属待核实", scores_json={"x": 60}, total_score=60, status="DRAFT")
        db.add(legacy); db.commit(); legacy_id = legacy.id
    blocked = create(client, headers["college"], periodCode="2026-ambiguous", version=0)
    assert blocked.status_code == 409, blocked.text
    with get_sessionmaker()() as db:
        legacy = db.get(CounselorEval, legacy_id)
        assert legacy.total_score == 60 and legacy.version == 0
    listing = client.get(BASE + "/evals", headers=headers["college"], params={"periodCode": "2026-ambiguous"})
    assert listing.status_code == 200 and listing.json()["data"]["total"] == 0


def test_eval_appeal_excludes_actual_scorer_and_keeps_missing_history(client, db_mode):
    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import AffairsAuditTrail
    headers, ids, login = actors(client, db_mode)
    a = create(client, headers["school"]).json()["data"]
    published = client.post(BASE + f"/evals/{a['evalId']}/publish", headers=headers["school"],
                            json={"version": a["version"]})
    assert published.status_code == 200, published.text
    from concurrent.futures import ThreadPoolExecutor
    def submit(number):
        return client.post(BASE + f"/evals/{a['evalId']}/appeal", headers=headers["a"],
            json={"reason": f"对现有考评结果申请正式复核{number}", "version": published.json()["data"]["version"]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, [1, 2]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    appeal = next(response for response in responses if response.status_code == 200)
    version = appeal.json()["data"]["version"]
    body = {"version": version, "result": "UPHELD", "opinion": "根据原始评分依据正式复核"}
    assert client.post(BASE + f"/evals/{a['evalId']}/appeal-review", headers=headers["school"], json=body).status_code == 403
    assert client.post(BASE + f"/evals/{a['evalId']}/appeal-review", headers=login("a", True), json=body).status_code == 403
    reviewed = client.post(BASE + f"/evals/{a['evalId']}/appeal-review", headers=headers["reviewer"], json=body)
    assert reviewed.status_code == 200, reviewed.text
    appeal = client.post(BASE + f"/evals/{a['evalId']}/appeal", headers=headers["a"],
                         json={"reason": "对保留结果继续申请正式复核", "version": reviewed.json()["data"]["version"]})
    assert appeal.status_code == 200, appeal.text
    body["version"] = appeal.json()["data"]["version"]
    # 历史没有可靠数字实际评分人时不按姓名/当前受理人猜测，也不改历史为成功。
    with get_sessionmaker()() as db:
        row = db.scalar(select(AffairsAuditTrail).where(AffairsAuditTrail.biz_type == "COUNSELOR_EVAL",
            AffairsAuditTrail.biz_id == int(a["evalId"]), AffairsAuditTrail.action == "EVAL_UPSERT"))
        row.created_by = None; db.commit()
    assert client.post(BASE + f"/evals/{a['evalId']}/appeal-review", headers=headers["reviewer"], json=body).status_code == 409
