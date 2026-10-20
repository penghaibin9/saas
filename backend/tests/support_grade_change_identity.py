"""Helpers for legacy grade-change tests against the current optimistic-lock contract."""

def change_request_payload(client, base, headers, task_id, record_id, **changes):
    response = client.get(
        f"{base}/grade-tasks/{task_id}/records/{record_id}/change-source",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    source = response.json()["data"]
    payload = {
        "expectedAuthorityHash": source["authorityEvidenceHash"],
        "expectedGradeVersion": int(source["recordVersion"]),
        "expectedCurrentGradeId": int(source["currentGradeId"]),
    }
    payload.update(changes)
    return payload


def review_payload(client, base, headers, request_id, action, reason=""):
    response = client.get(
        f"{base}/grade-changes/{request_id}/detail",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    detail = response.json()["data"]
    return {
        "action": action,
        "reason": reason,
        "changeRequestId": int(detail["changeRequestId"]),
        "expectedRequestVersion": int(detail["requestVersion"]),
        "currentTaskId": int(detail["currentTaskId"]),
        "expectedTaskVersion": int(detail["currentTaskVersion"]),
    }


def college_approve_grade_task(client, base, task_id, headers):
    evidence = client.get(
        f"{base}/grade-tasks/{task_id}/review-evidence",
        headers=headers,
    )
    assert evidence.status_code == 200, evidence.text
    return client.post(
        f"{base}/grade-tasks/{task_id}/college-review",
        headers=headers,
        json={
            "action": "APPROVE",
            "expectedEvidenceHash": evidence.json()["data"]["evidenceHash"],
        },
    )
