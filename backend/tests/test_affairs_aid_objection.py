"""13A-C 困难认定公示异议端到端（真实 DB）。

覆盖：对公示中申请提异议→复核成立(驳回申请)/不成立(维持)；非公示不可提异议、
理由/意见校验、已复核不可再核。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _ensure_school_reviewer(db):
    """异议提交前必须存在真实 SCHOOL_REVIEW 受理人。"""
    from sqlalchemy import select
    from app.models import Role, User, UserRole

    user = db.scalars(select(User).where(
        User.tenant_id == TID, User.login_name == "school_admin01",
        User.is_deleted.is_(False),
    )).first()
    if not user:
        user = User(
            tenant_id=TID, login_name="school_admin01", real_name="学校管理员",
            password_hash="test-only", user_type="SCHOOL_ADMIN", status="ACTIVE",
        )
        db.add(user); db.flush()
    role = db.scalars(select(Role).where(
        Role.tenant_id == TID, Role.role_code == "SCHOOL_ADMIN",
        Role.is_deleted.is_(False),
    )).first()
    if not role:
        role = Role(
            tenant_id=TID, role_code="SCHOOL_ADMIN", role_name="学校管理员",
            role_type="SYSTEM", status="ACTIVE",
        )
        db.add(role); db.flush()
    link = db.scalars(select(UserRole).where(
        UserRole.tenant_id == TID, UserRole.user_id == user.id,
        UserRole.role_id == role.id, UserRole.is_deleted.is_(False),
    )).first()
    if not link:
        db.add(UserRole(
            tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE",
        ))


def _seed_apply(sid, status="PUBLICITY"):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, AidBatch
    db = get_sessionmaker()()
    _ensure_school_reviewer(db)
    b = AidBatch(
        tenant_id=TID, batch_name="2026困难认定", year_code="2025-2026",
        status="PUBLICITY", publicity_days=1,
    )
    db.add(b); db.flush()
    x = AidApply(
        tenant_id=TID, batch_id=b.id, student_id=sid, apply_level="DIFFICULT",
        final_level="DIFFICULT", status=status,
    )
    db.add(x); db.commit(); db.refresh(x)
    data = {"applyId": x.id, "version": x.version}
    db.close()
    return data


def _submit(client, hdr, apply_id, reason, objector_name=""):
    body = {"reason": reason}
    if objector_name:
        body["objectorName"] = objector_name
    result = client.post(f"{BASE}/aid/applications/{apply_id}/objection", headers=hdr, json=body).json()
    assert result["code"] == 0, result
    return result["data"]


def _review(client, hdr, objection, result, opinion):
    response = client.post(
        f"{BASE}/aid/objections/{objection['objectionId']}/review",
        headers=hdr,
        json={"result": result, "opinion": opinion, "version": objection["version"]},
    ).json()
    assert response["code"] == 0, response
    return response["data"]


def test_objection_sustained_rejects_apply(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    seeded = _seed_apply(db_mode["student"], "PUBLICITY")
    apply_id = seeded["applyId"]
    r0 = client.post(f"{BASE}/aid/applications/{apply_id}/objection", headers=hdr, json={"reason": "短"})
    assert r0.status_code == 422 or r0.json().get("code") not in (0, None)

    objection = _submit(client, hdr, apply_id, "该生家庭经济情况与申报不符", "同班同学")
    assert objection["status"] == "SUBMITTED" and objection["version"] >= 1
    oid = objection["objectionId"]
    assert any(x["objectionId"] == oid and "version" in x
               for x in client.get(f"{BASE}/aid/objections", headers=hdr).json()["data"]["items"])

    reviewed = _review(client, hdr, objection, "SUSTAINED", "核实异议属实，取消其困难认定资格")
    assert reviewed["result"] == "SUSTAINED"
    detail = client.get(f"{BASE}/aid/applications/{apply_id}", headers=hdr).json()["data"]
    assert detail["status"] == "REJECTED"

    repeated = client.post(
        f"{BASE}/aid/objections/{oid}/review",
        headers=hdr,
        json={"result": "OVERRULED", "opinion": "再次复核维持原状", "version": reviewed["version"]},
    ).json()
    assert repeated["code"] != 0


def test_objection_blocks_publicity_confirm(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    seeded = _seed_apply(db_mode["student"], "PUBLICITY")
    apply_id = seeded["applyId"]
    from app.db.session import get_sessionmaker
    from app.models import AidApply
    from datetime import datetime, timedelta
    db = get_sessionmaker()()
    x = db.get(AidApply, apply_id)
    x.publicity_at = datetime.utcnow() - timedelta(days=2)
    db.commit(); db.refresh(x)
    current_version = x.version
    db.close()

    _submit(client, hdr, apply_id, "该生家庭经济情况与申报不符")
    blocked = client.post(
        f"{BASE}/aid/applications/{apply_id}/publicity-confirm",
        headers=hdr,
        json={"version": current_version},
    ).json()
    assert blocked["code"] != 0 and "异议" in blocked["message"]
    detail = client.get(f"{BASE}/aid/applications/{apply_id}", headers=hdr).json()["data"]
    assert detail["status"] == "PUBLICITY"
    assert detail.get("hasPendingObjection") is True


def test_objection_overruled_and_non_publicity(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    seeded = _seed_apply(db_mode["student"], "PUBLICITY")
    apply_id = seeded["applyId"]
    objection = _submit(client, hdr, apply_id, "对认定结果有疑问请复核")
    reviewed = _review(client, hdr, objection, "OVERRULED", "经复核认定无误，异议不成立维持")
    assert reviewed["result"] == "OVERRULED"
    detail = client.get(f"{BASE}/aid/applications/{apply_id}", headers=hdr).json()["data"]
    assert detail["status"] == "PUBLICITY"

    ap2 = _seed_apply(db_mode["student"], "CLASS_REVIEW")["applyId"]
    assert client.post(f"{BASE}/aid/applications/{ap2}/objection", headers=hdr,
                       json={"reason": "评议阶段不应可提异议"}).json()["code"] != 0
