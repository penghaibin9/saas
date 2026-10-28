"""阶段 1：同一认定在教师 PC、教师移动和学生双端交接（独立 MySQL）。"""
from app.db.session import get_sessionmaker
from app.models import InternshipBatch, InternshipRecord
from tests.test_internship_student import IST, _record, _student
from tests.test_internship_student_context_writes import _student_headers


def test_qualification_handoff_privacy_conflict_and_readonly(client, auth_headers, db_mode):
    student_no = "PREPARATION-OWN-001"
    sid = _student(client, auth_headers, student_no)
    rid = _record(client, auth_headers, sid)
    before = client.get(f"{IST}/{rid}", headers=auth_headers).json()["data"]
    bid = before["batchId"]
    assert before["batchName"] and before["className"] != "-"
    own = _student_headers(student_no)

    def result(path, selected_batch=bid):
        # The portal request wrapper sends the selected batch in a header;
        # the mobile dashboard also exposes an explicit query parameter.
        headers = {**own, "X-Internship-Batch-Id": str(selected_batch)} if path.startswith("/api/v1/portal/") else own
        params = {} if path.startswith("/api/v1/portal/") else {"batchId": selected_batch}
        response = client.get(path, headers=headers, params=params)
        assert response.status_code == 200, response.json()
        return response.json()["data"]

    # Existing internal notes must not be retroactively disclosed to students.
    internal = client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={
        "status": "UNQUALIFIED", "reason": "历史内部核对意见", "expectedVersion": before["version"],
    })
    assert internal.status_code == 200, internal.json()
    for path in ("/api/v1/portal/internship/my", "/api/v1/mobile/internship/context/my"):
        data = result(path)
        assert data["eligibilityReview"]["status"] == "UNQUALIFIED"
        assert data["eligibilityReview"]["reason"] == ""
        assert "auditTrail" not in data

    # Explicitly public new notes are shared across both student clients.
    version = internal.json()["data"]["version"]
    public = client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={
        "status": "PENDING", "reason": "请联系指导教师补充本批次资格材料",
        "expectedVersion": version, "publishReason": True,
    })
    assert public.status_code == 200, public.json()
    pc = result("/api/v1/portal/internship/my")
    mobile = result("/api/v1/mobile/internship/context/my")
    assert pc["recordId"] == mobile["recordId"] == rid
    assert pc["eligibilityReview"] == mobile["eligibilityReview"]
    assert pc["eligibilityReview"]["reason"] == "请联系指导教师补充本批次资格材料"
    conflict = client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={
        "status": "QUALIFIED", "expectedVersion": version,
    })
    assert conflict.status_code == 409
    assert result("/api/v1/mobile/internship/context/my")["eligibilityReview"]["status"] == "PENDING"

    # A student's own token cannot invoke the teacher qualification write.
    denied = client.post(f"{IST}/{rid}/eligibility", headers=own, json={
        "status": "QUALIFIED", "expectedVersion": version + 1,
    })
    assert denied.status_code == 403
    qualified = client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={
        "status": "QUALIFIED", "expectedVersion": version + 1, "publishReason": True,
        "reason": "学校已核对本批次资格",
    })
    assert qualified.status_code == 200, qualified.json()
    assert result("/api/v1/mobile/internship/context/my")["eligibilityReview"]["status"] == "QUALIFIED"

    second_rid = _record(client, auth_headers, sid)
    second = client.get(f"{IST}/{second_rid}", headers=auth_headers).json()["data"]
    for path in ("/api/v1/portal/internship/my", "/api/v1/mobile/internship/context/my"):
        assert client.get(path, headers=own).json()["data"]["needSelect"] is True
        selected = result(path)
        assert {item["batchId"] for item in selected["candidates"]} == {bid, second["batchId"]}
        assert selected["recordId"] == rid
        other_batch = result(path, second["batchId"])
        assert other_batch["recordId"] == second_rid
        assert other_batch["eligibilityReview"]["status"] == "PENDING"
        assert other_batch["eligibilityReview"]["reason"] == ""

    other_sid = _student(client, auth_headers, "PREPARATION-OTHER-002")
    other_rid = _record(client, auth_headers, other_sid)
    other = client.get(f"{IST}/{other_rid}", headers=auth_headers).json()["data"]
    assert client.get("/api/v1/mobile/internship/context/my", headers=own,
                      params={"batchId": other["batchId"]}).status_code == 404

    for status in ("CLOSED", "ARCHIVED", "VOIDED"):
        with get_sessionmaker()() as db:
            db.get(InternshipBatch, int(bid)).status = status
            db.commit()
        response = client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={
            "status": "UNQUALIFIED", "expectedVersion": qualified.json()["data"]["version"],
        })
        assert response.status_code == 409, status
    with get_sessionmaker()() as db:
        db.get(InternshipBatch, int(bid)).status = "RUNNING"
        db.get(InternshipRecord, int(rid)).status = "ARCHIVED"
        db.commit()
    assert client.post(f"{IST}/{rid}/eligibility", headers=auth_headers, json={
        "status": "PENDING", "expectedVersion": qualified.json()["data"]["version"],
    }).status_code == 409
