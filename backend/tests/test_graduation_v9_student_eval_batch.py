"""V9.2 M2：导师过程评价必须显式 batchId，列表与写链均跨批 fail-closed。"""
from __future__ import annotations

import uuid

from conftest import make_org_class

GD_BATCH = "/api/v1/graduation/batches"
GD_STU = "/api/v1/graduation/gd-students"
GD_EVAL = "/api/v1/graduation/gd-student-evals"
STU = "/api/v1/students"


def _batch(client, h):
    suffix = uuid.uuid4().hex[:8]
    body = {
        "batchName": f"V9.2评价批次-{suffix}",
        "batchNo": f"V92-EVAL-{suffix}",
        "gradeYear": "2026届",
        "plannedCount": 10,
    }
    r = client.post(GD_BATCH, headers=h, json=body).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _record(client, h, batch_id, label):
    suffix = uuid.uuid4().hex[:8]
    sr = client.post(STU, headers=h, json={
        "studentNo": f"V92{suffix}", "realName": label, "classId": make_org_class(),
    }).json()
    assert sr["code"] == 0, sr
    gr = client.post(GD_STU, headers=h, json={
        "studentId": sr["data"]["id"], "batchId": batch_id,
    }).json()
    assert gr["code"] == 0, gr
    return gr["data"]["id"]


def _eval_body(status="SUBMITTED"):
    return {"period": "中期", "score": 86, "level": "良好", "content": "V9.2 batch truth", "status": status}


def _is_validation_or_conflict(response):
    body = response.json() if "application/json" in (response.headers.get("content-type") or "") else {}
    return response.status_code in (400, 409, 422) or body.get("bizCode") in {"DATA_CONFLICT", "VALIDATION_ERROR"} or body.get("code") in {409001, 422001, 400, 409, 422}


def test_student_eval_requires_batch_and_list_is_batch_isolated(graduation_client, auth_headers, db_mode):
    h = auth_headers
    b1, b2 = _batch(graduation_client, h), _batch(graduation_client, h)
    g1 = _record(graduation_client, h, b1, "评价批次甲")
    g2 = _record(graduation_client, h, b2, "评价批次乙")

    e1 = graduation_client.post(f"{GD_EVAL}/{g1}", headers=h, params={"batchId": b1}, json=_eval_body()).json()
    e2 = graduation_client.post(f"{GD_EVAL}/{g2}", headers=h, params={"batchId": b2}, json=_eval_body()).json()
    assert e1["code"] == 0 and e2["code"] == 0

    l1 = graduation_client.get(GD_EVAL, headers=h, params={"batchId": b1, "pageSize": 100}).json()
    l2 = graduation_client.get(GD_EVAL, headers=h, params={"batchId": b2, "pageSize": 100}).json()
    assert l1["code"] == 0 and l2["code"] == 0
    ids1 = {row["id"] for row in l1["data"]["items"]}
    ids2 = {row["id"] for row in l2["data"]["items"]}
    assert e1["data"]["id"] in ids1 and e2["data"]["id"] not in ids1
    assert e2["data"]["id"] in ids2 and e1["data"]["id"] not in ids2

    missing = graduation_client.get(GD_EVAL, headers=h)
    missing_body = missing.json()
    assert missing.status_code == 400, missing.text
    assert missing_body["code"] == 422001, missing_body
    assert missing_body["bizCode"] == "VALIDATION_ERROR", missing_body
    assert any(
        item.get("field") == "batchId" and item.get("msg") == "Field required"
        for item in missing_body.get("details") or []
    ), missing_body


def test_student_eval_create_and_submit_fail_closed_on_wrong_batch(graduation_client, auth_headers, db_mode):
    h = auth_headers
    b1, b2 = _batch(graduation_client, h), _batch(graduation_client, h)
    gid = _record(graduation_client, h, b1, "评价跨批学生")

    wrong_create = graduation_client.post(f"{GD_EVAL}/{gid}", headers=h, params={"batchId": b2}, json=_eval_body("DRAFT"))
    assert _is_validation_or_conflict(wrong_create), wrong_create.text

    draft = graduation_client.post(f"{GD_EVAL}/{gid}", headers=h, params={"batchId": b1}, json=_eval_body("DRAFT"))
    assert draft.json()["code"] == 0, draft.text
    eval_id = draft.json()["data"]["id"]

    wrong_submit = graduation_client.post(f"{GD_EVAL}/records/{eval_id}/submit", headers=h, params={"batchId": b2})
    assert _is_validation_or_conflict(wrong_submit), wrong_submit.text

    correct = graduation_client.post(f"{GD_EVAL}/records/{eval_id}/submit", headers=h, params={"batchId": b1})
    assert correct.json()["code"] == 0, correct.text
    assert correct.json()["data"]["status"] == "SUBMITTED"
