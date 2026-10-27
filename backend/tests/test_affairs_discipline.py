"""13A-P4 违纪处分闭环 · 端到端（真实 DB 模式）。

D1 登记+提交建流；D2 一般处分全链→EFFECTIVE+投影+360+对账；D3 严重处分走校级；
D4 驳回原因校验+生效不可再审；D5 解除全链→REMOVED+投影record_status+对账；
未生效发起解除409；越权跨班403。
"""
from __future__ import annotations

from affairs_contract_test_support import ensure_owner_scope, ensure_workflow_assignees, post_versioned

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    from test_aid_mobile_queue import _login
    return _login(client, login_name, "PC")


def _seed(db_mode):
    from test_affairs_aid import _seed as seed_school_relations
    ids = seed_school_relations(db_mode)
    ensure_workflow_assignees([ids["sa"], ids["sb"]])
    return ids


def _register(client, hdr, sid, disc_type="WARNING"):
    return client.post(f"{BASE}/discipline/cases", headers=hdr, json={
        "studentId": str(sid), "discType": disc_type, "reason": "考试违纪，情节较轻，予以处分"})


def _to_effective(client, hdr, cid, severe=False):
    post_versioned(client, f"{BASE}/discipline/cases/{cid}/submit", headers=hdr)
    first = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=_hdr(client, "college_admin01"), json={"action": "APPROVE"})
    assert first.status_code == 200, first.text
    r = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=_hdr(client, "sa_admin01"), json={"action": "APPROVE"})
    assert r.status_code == 200, r.text
    if severe:
        r = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=_hdr(client, "school_admin01"), json={"action": "APPROVE"})
    return r.json()


def test_d1_register_submit_creates_workflow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"]).json()["data"]["caseId"]
    r = post_versioned(client, f"{BASE}/discipline/cases/{cid}/submit", headers=hdr).json()
    assert r["data"]["status"] == "COLLEGE_REVIEW"
    from app.db.session import get_sessionmaker
    from app.models import WorkflowInstance
    db = get_sessionmaker()()
    assert db.query(WorkflowInstance).filter_by(source_biz_id=int(cid), source_biz_type="DISCIPLINE").count() == 1
    db.close()


def test_d2_normal_to_effective_projection_360(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"], "WARNING").json()["data"]["caseId"]
    r = _to_effective(client, hdr, cid, severe=False)
    assert r["data"]["status"] == "EFFECTIVE"
    assert r["data"]["csDisciplineId"]  # 投影行已建
    # 投影 + 360 + 对账
    from app.db.session import get_sessionmaker
    from app.models import CsDiscipline, StudentStageEvent
    db = get_sessionmaker()()
    proj = db.query(CsDiscipline).filter_by(source_case_id=int(cid), record_status="ACTIVE").count()
    ev = db.query(StudentStageEvent).filter_by(student_id=ids["sa"], to_stage="DISCIPLINE_EFFECTIVE").count()
    db.close()
    assert proj == 1 and ev == 1
    rec = client.get(f"{BASE}/discipline/reconcile", headers=hdr).json()["data"]
    assert rec["consistent"] is True and rec["effectiveCases"] == 1 and rec["activeProjections"] == 1


def test_school_visibility_cannot_take_college_review(client, db_mode):
    ids = _seed(db_mode)
    school = _hdr(client, "school_admin01")
    case_id = _register(client, school, ids["sa"]).json()["data"]["caseId"]
    submitted = post_versioned(client, f"{BASE}/discipline/cases/{case_id}/submit", headers=school)
    assert submitted.status_code == 200, submitted.text
    queue = client.get('/api/v1/mobile/teacher/affairs/discipline/pending', headers=school)
    assert queue.status_code == 200, queue.text
    assert queue.json()["data"]["total"] == 0
    denied = post_versioned(client, f"{BASE}/discipline/cases/{case_id}/review", headers=school,
                            json={"action": "APPROVE"})
    assert denied.status_code == 403, denied.text
    after = client.get(f"{BASE}/discipline/cases/{case_id}", headers=school).json()["data"]
    assert after["version"] == submitted.json()["data"]["version"]
    allowed = post_versioned(client, f"{BASE}/discipline/cases/{case_id}/review",
                             headers=_hdr(client, "college_admin01"), json={"action": "APPROVE"})
    assert allowed.status_code == 200, allowed.text


def test_d3_severe_goes_school_review(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, _hdr(client, "college_admin01"), ids["sa"], "EXPEL").json()["data"]["caseId"]
    post_versioned(client, f"{BASE}/discipline/cases/{cid}/submit", headers=hdr)
    post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=_hdr(client, "college_admin01"), json={"action": "APPROVE"})
    r = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=_hdr(client, "sa_admin01"), json={"action": "APPROVE"}).json()
    assert r["data"]["status"] == "SCHOOL_REVIEW"  # 严重处分转校级
    r2 = post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=hdr, json={"action": "APPROVE"}).json()
    assert r2["data"]["status"] == "EFFECTIVE"


def test_d4_reject_and_effective_immutable(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"]).json()["data"]["caseId"]
    post_versioned(client, f"{BASE}/discipline/cases/{cid}/submit", headers=hdr)
    # 原因<5字 → 400
    assert post_versioned(client, f"{BASE}/discipline/cases/{cid}/review", headers=_hdr(client, "college_admin01"),
                       json={"action": "REJECT", "reason": "不"}).status_code == 400
    # 生效后再审 → 409
    _to_effective(client, hdr, _register(client, hdr, ids["sa"]).json()["data"]["caseId"])
    cid2 = _register(client, hdr, ids["sb"] if False else ids["sa"]).json()["data"]["caseId"]  # 另一单
    _to_effective(client, hdr, cid2)
    assert post_versioned(client, f"{BASE}/discipline/cases/{cid2}/review", headers=hdr,
                       json={"action": "APPROVE"}).status_code == 409


def test_d5_remove_flow(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"]).json()["data"]["caseId"]
    _to_effective(client, hdr, cid)
    # 发起解除 → REMOVE_REVIEW
    r = post_versioned(client, f"{BASE}/discipline/cases/{cid}/remove", headers=hdr,
                    json={"reason": "表现良好，申请解除处分"}).json()
    assert r["data"]["status"] == "REMOVE_REVIEW"
    # 辅→院→处 三级审批
    for reviewer in ("counselor01", "college_admin01", "sa_admin01"):
        reviewer_headers = _hdr(client, reviewer)
        queue = client.get('/api/v1/mobile/teacher/affairs/discipline/pending', headers=reviewer_headers,
                           params={"kind": "DISCIPLINE_REMOVE"})
        assert queue.status_code == 200, queue.text
        assert [item["caseId"] for item in queue.json()["data"]["list"]] == [cid]
        r = post_versioned(client, f"{BASE}/discipline/cases/{cid}/remove-review", headers=reviewer_headers,
                        json={"action": "APPROVE"}).json()
    assert r["data"]["status"] == "REMOVED"
    # 投影 record_status 更新 + 对账（生效数=0，投影ACTIVE=0）
    from app.db.session import get_sessionmaker
    from app.models import CsDiscipline
    db = get_sessionmaker()()
    revoked = db.query(CsDiscipline).filter_by(source_case_id=int(cid), record_status="REVOKED").count()
    db.close()
    assert revoked == 1
    rec = client.get(f"{BASE}/discipline/reconcile", headers=hdr).json()["data"]
    assert rec["consistent"] is True


def test_d6_remove_before_effective_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    cid = _register(client, hdr, ids["sa"]).json()["data"]["caseId"]
    assert post_versioned(client, f"{BASE}/discipline/cases/{cid}/remove", headers=hdr,
                       json={"reason": "尚未生效就申请解除"}).status_code == 409


def test_d7_cross_class_403(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    cid = _register(client, admin, ids["sb"]).json()["data"]["caseId"]
    r = client.get(f"{BASE}/discipline/cases/{cid}", headers=_hdr(client, "counselor01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_DATA_SCOPE"


def test_d_register_non_digit_student_400_not_500(client, db_mode):
    """历史欠账收口：登记违纪 studentId 非数字此前 int() 抛 500，现应 400 VALIDATION_ERROR。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/discipline/cases", headers=hdr, json={
        "studentId": "abc", "discType": "WARNING", "reason": "考试违纪，情节较轻，予以处分"})
    assert r.status_code == 400 and r.json()["bizCode"] == "VALIDATION_ERROR"


def test_discipline_queue_filters_before_paging_and_uses_latest_task(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import DisciplineCase, User, WorkflowInstance, WorkflowTask
    ids = _seed(db_mode)
    college = _hdr(client, "college_admin01")
    expected = set()
    with get_sessionmaker()() as db:
        owner = db.query(User).filter_by(tenant_id=TID, login_name="college_admin01").one()
        other = db.query(User).filter_by(tenant_id=TID, login_name="school_admin01").one()
        for index in range(107):
            row = DisciplineCase(tenant_id=TID, student_id=ids["sa"], disc_type="WARNING",
                                 reason="隔离测试处分", status="COLLEGE_REVIEW", created_by=other.id)
            db.add(row); db.flush()
            if index < 101:
                expected.add(str(row.id))
            if index == 101:
                continue
            flow = WorkflowInstance(tenant_id=TID, workflow_code="AFFAIRS_DISCIPLINE",
                source_module="student-affairs", source_biz_type="DISCIPLINE", source_biz_id=row.id,
                applicant_id=owner.id, title="隔离测试任务", status="RUNNING", current_node="COLLEGE_REVIEW")
            db.add(flow); db.flush()
            row.workflow_instance_id = flow.id
            if index == 102:
                continue
            task = WorkflowTask(tenant_id=TID, instance_id=flow.id, node_code="COLLEGE_REVIEW",
                                assignee_id=0 if index == 103 else other.id if index == 104 else owner.id,
                                status="PENDING")
            db.add(task); db.flush()
            if index == 105:
                db.add(WorkflowTask(tenant_id=TID, instance_id=flow.id, node_code="COLLEGE_REVIEW",
                                    assignee_id=other.id, status="PENDING"))
            if index == 106:
                row.status = "EFFECTIVE"
        db.commit()
    seen = []
    for page in range(1, 7):
        response = client.get('/api/v1/mobile/teacher/affairs/discipline/pending', headers=college,
                              params={"page": page, "pageSize": 20, "kind": "DISCIPLINE_APPROVAL"})
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["total"] == 101
        seen.extend(row["caseId"] for row in result["list"])
    assert len(seen) == len(set(seen)) == 101
    assert set(seen) == expected
