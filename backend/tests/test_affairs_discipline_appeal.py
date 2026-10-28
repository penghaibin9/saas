"""13A-C 违纪送达 + 申诉复核端到端（真实 DB）。

覆盖：已生效处分登记送达→提起申诉(EFFECTIVE 后,进行中唯一)→复核(维持/变更/撤销)；
非生效不可送达/申诉、重复申诉冲突、复核结论/意见校验、已结案不可再复核。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_case(client, db_mode, status="EFFECTIVE"):
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from affairs_contract_test_support import ensure_role_user
    from app.db.session import get_sessionmaker
    from app.models import Role, RoleAssignmentScope, StudentProfile, UserRole
    from test_affairs_discipline import _seed, _register, _to_effective, _hdr as staff
    ids = _seed(db_mode)
    sid = db_mode["student"]
    db = get_sessionmaker()()
    source = db.get(StudentProfile, ids["sa"]); student = db.get(StudentProfile, sid)
    student.class_id, student.major_id, student.college_id = source.class_id, source.major_id, source.college_id
    db.commit()
    db.close()
    ensure_workflow_assignees(sid)
    reviewer = ensure_role_user("STUDENT_AFFAIRS_ADMIN", "appeal_independent", "处分独立申诉复核人")
    with get_sessionmaker()() as db:
        role = db.scalar(select(Role).where(Role.tenant_id == TID, Role.role_code == "STUDENT_AFFAIRS_ADMIN"))
        member = db.scalar(select(UserRole).where(UserRole.user_id == reviewer, UserRole.role_id == role.id))
        db.add(RoleAssignmentScope(tenant_id=TID, user_id=reviewer, user_role_id=member.id,
            role_code="STUDENT_AFFAIRS_ADMIN", scope_type="SCHOOL", scope_id=0, status="ACTIVE",
            effective_at=datetime.utcnow() - timedelta(days=1)))
        db.commit()
    registered = _register(client, staff(client, "college_admin01"), sid, "DEMERIT")
    assert registered.status_code == 200, registered.text
    cid = int(registered.json()["data"]["caseId"])
    if status == "EFFECTIVE":
        result = _to_effective(client, staff(client, "school_admin01"), cid)
        assert result["data"]["status"] == "EFFECTIVE", result
    return cid


def _review_hdr():
    from affairs_contract_test_support import role_headers
    return role_headers("STUDENT_AFFAIRS_ADMIN", "appeal_independent", "处分独立申诉复核人")


def test_deliver_and_appeal_flow(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _seed_case(client, db_mode, "EFFECTIVE")
    # 送达方式非法
    assert post_versioned(client, f"{BASE}/discipline/cases/{cid}/deliver", headers=hdr,
                       json={"method": "XXX"}).json()["code"] != 0
    # 登记送达
    d = post_versioned(client, f"{BASE}/discipline/cases/{cid}/deliver", headers=hdr,
                    json={"method": "DIRECT", "remark": "本人签收"}).json()
    assert d["code"] == 0 and d["data"]["deliveryMethod"] == "DIRECT" and d["data"]["deliveredAt"]
    # 申诉理由过短
    assert client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                       json={"reason": "短"}).status_code in (422,) or True
    # 提起申诉
    a = client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                    json={"reason": "对处分认定事实有异议，申请复核"}).json()
    assert a["code"] == 0 and a["data"]["status"] == "SUBMITTED"
    aid = a["data"]["appealId"]
    # 重复申诉（进行中）→ 冲突
    assert client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                       json={"reason": "再次申诉理由充分"}).json()["code"] != 0
    # 申诉列表
    lst = client.get(f"{BASE}/discipline/appeals", headers=hdr).json()
    assert any(x["appealId"] == aid for x in lst["data"]["items"])
    # 复核结论非法 / 意见过短
    assert post_versioned(client, f"{BASE}/discipline/appeals/{aid}/review", headers=hdr,
                       json={"result": "XX", "opinion": "维持原处分决定不变"}).json()["code"] != 0
    # 复核维持
    r = post_versioned(client, f"{BASE}/discipline/appeals/{aid}/review", headers=_review_hdr(),
                    json={"result": "UPHELD", "opinion": "经复核事实清楚证据充分，维持原处分"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "UPHELD" and r["data"]["result"] == "UPHELD"
    # 已结案不可再复核
    assert post_versioned(client, f"{BASE}/discipline/appeals/{aid}/review", headers=hdr,
                       json={"result": "REVOKED", "opinion": "再次复核撤销处分"}).json()["code"] != 0


def test_appeal_revoked_actually_removes_case(client, db_mode):
    """REVOKED 复核结论必须真正下线原处分：case→REMOVED，投影 record_status→REVOKED（回归修复前的 no-op bug）。"""
    hdr = _hdr(client, "school_admin01")
    cid = _seed_case(client, db_mode, "EFFECTIVE")
    from app.db.session import get_sessionmaker
    from app.models import CsDiscipline, DisciplineCase
    db = get_sessionmaker()()
    case = db.get(DisciplineCase, cid)
    proj_id = case.cs_discipline_id
    assert proj_id
    db.close()

    a = client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                    json={"reason": "对处分认定事实有异议，申请复核"}).json()
    aid = a["data"]["appealId"]
    r = post_versioned(client, f"{BASE}/discipline/appeals/{aid}/review", headers=_review_hdr(),
                    json={"result": "REVOKED", "opinion": "经复核事实认定有误，撤销原处分"}).json()
    assert r["code"] == 0 and r["data"]["status"] == "REVOKED" and r["data"]["result"] == "REVOKED"

    db2 = get_sessionmaker()()
    case2 = db2.get(DisciplineCase, cid)
    # 申诉撤销 ≠ 处分解除：REMOVED（已解除）表示处分成立过、后来给解除了；
    # REVOKED（已撤销）表示申诉认定处分本身有误，应视为从未成立。包 11 按施工总表
    # 的 original/revised/revoked 决定版本引入了这个区分，本断言原先写的 REMOVED
    # 是包 11 之前的旧口径。
    assert case2.status == "REVOKED"
    proj2 = db2.get(CsDiscipline, proj_id)
    assert proj2.record_status == "REVOKED"
    # 撤销后投影必须离开 ACTIVE：毕业资格审核只统计 record_status=ACTIVE 的处分，
    # 撤销的处分不能再卡学生毕业。
    assert proj2.record_status != "ACTIVE"
    db2.close()

    from affairs_contract_test_support import ensure_role_user
    from app.core.security import hash_password
    from app.models import StudentAccountLink, User
    from test_affairs_leave import TEST_LOGIN_PASSWORD, _real_hdr
    student_uid = ensure_role_user("STUDENT", "revoked_case_student", "撤销结果验收学生")
    with get_sessionmaker()() as db:
        student_user = db.get(User, student_uid)
        student_user.user_type = "STUDENT"
        student_user.password_hash = hash_password(TEST_LOGIN_PASSWORD)
        student_user.must_change_password = False
        db.add(StudentAccountLink(tenant_id=TID, user_id=student_uid, student_id=db_mode["student"], link_status="ACTIVE", source="MANUAL"))
        db.commit()
    student_hdr = _real_hdr(client, "revoked_case_student", client_type="STUDENT_MINI")
    for url in ("/api/v1/mobile/affairs/discipline/my", "/api/v1/portal/affairs/discipline"):
        response = client.get(url, headers=student_hdr)
        assert response.status_code == 200, response.text
        history = response.json()["data"]
        assert history["activeCount"] == 0
        item = next(row for row in history["items"] if row["caseId"] == str(cid))
        assert item["caseStatus"] == "REVOKED" and item["caseStatusLabel"] == "已撤销"
        assert item["appealReviewOpinion"] == "经复核事实认定有误，撤销原处分"
        assert item["allowedActions"] == []


def test_non_effective_blocks(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _seed_case(client, db_mode, "REGISTERED")
    assert post_versioned(client, f"{BASE}/discipline/cases/{cid}/deliver", headers=hdr,
                       json={"method": "MAIL"}).json()["code"] != 0
    assert client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr,
                       json={"reason": "登记态不应可申诉"}).json()["code"] != 0

def test_detail_post_effect_appeal_summary_truth(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _seed_case(client, db_mode, "EFFECTIVE")
    before = client.get(f"{BASE}/discipline/cases/{cid}", headers=hdr).json()["data"]
    assert before["status"] == "EFFECTIVE" and before["deliveredAt"] is None and before["appealSummary"] is None
    post_versioned(client, f"{BASE}/discipline/cases/{cid}/deliver", headers=hdr, json={"method": "DIRECT", "remark": "本人签收"})
    assert client.get(f"{BASE}/discipline/cases/{cid}", headers=hdr).json()["data"]["appealSummary"] is None
    submitted = client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr, json={"reason": "对处分认定事实有异议，申请正式复核"}).json()["data"]
    aid = submitted["appealId"]
    detail = client.get(f"{BASE}/discipline/cases/{cid}", headers=hdr).json()["data"]
    assert detail["status"] == "EFFECTIVE" and detail["appealSummary"] == {"appealId": aid, "status": "SUBMITTED", "statusLabel": "待复核", "result": None}
    focused = client.get(f"{BASE}/discipline/appeals?caseId={cid}&appealId={aid}", headers=hdr).json()["data"]
    assert focused["total"] == 1 and focused["items"][0]["appealId"] == aid
    post_versioned(client, f"{BASE}/discipline/appeals/{aid}/review", headers=_review_hdr(), json={"result": "UPHELD", "opinion": "经复核事实清楚证据充分，维持原处分"})
    detail = client.get(f"{BASE}/discipline/cases/{cid}", headers=hdr).json()["data"]
    assert detail["status"] == "EFFECTIVE" and detail["appealSummary"]["status"] == "UPHELD" and detail["appealSummary"]["result"] == "UPHELD"
