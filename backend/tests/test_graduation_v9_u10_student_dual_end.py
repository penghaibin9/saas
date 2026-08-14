from __future__ import annotations

from app.student_portal.services import graduation_service as portal


def test_u10_pc_reads_delegate_to_authoritative_student_services(monkeypatch):
    user = {"userType": "STUDENT", "userId": "db-1001"}
    fixtures = {
        "graduation_taskbook": {"hasData": True, "taskbookVersion": 3},
        "graduation_proposal": {"hasData": True, "canSubmit": True},
        "graduation_midterm": {"hasData": True, "status": "RECTIFYING"},
        "graduation_final": {"hasData": True, "canSubmitDraft": True},
        "graduation_grade": {"hasData": True, "status": "PUBLISHED", "canAppeal": True},
    }
    for name, expected in fixtures.items():
        monkeypatch.setattr(portal.stu, name, lambda _user, value=expected: value)

    assert portal.taskbook(user) == fixtures["graduation_taskbook"]
    assert portal.proposal(user) == fixtures["graduation_proposal"]
    assert portal.midterm(user) == fixtures["graduation_midterm"]
    assert portal.final(user) == fixtures["graduation_final"]
    assert portal.grade(user) == fixtures["graduation_grade"]


def test_u10_pc_taskbook_confirmation_forwards_rendered_version_to_canonical_service(monkeypatch):
    from app.modules.graduation.services import graduation_taskbook_confirmation_service as confirmation

    user = {"userType": "STUDENT", "userId": "db-1001"}
    captured = {}

    def fake_confirm(actor, *, expected_version, confirm):
        captured.update(actor=actor, expected_version=expected_version, confirm=confirm)
        return {"status": "CONFIRMED", "taskbookVersion": expected_version}

    monkeypatch.setattr(confirmation, "confirm_with_evidence", fake_confirm)
    result = portal.taskbook_sign(user, {"confirm": True, "taskbookVersion": 7})

    assert result == {"status": "CONFIRMED", "taskbookVersion": 7}
    assert captured == {"actor": user, "expected_version": 7, "confirm": True}


def test_u10_pc_proposal_and_final_keep_material_expected_version(monkeypatch):
    user = {"userType": "STUDENT", "userId": "db-1001"}
    captured = {}

    def fake_proposal(actor, payload):
        captured["proposal"] = (actor, payload)
        return {"id": "proposal-1", "status": "PENDING_REVIEW"}

    def fake_final(actor, payload):
        captured["final"] = (actor, payload)
        return {"id": "final-1", "status": "PENDING_REVIEW"}

    monkeypatch.setattr(portal.stu, "graduation_submit_proposal", fake_proposal)
    monkeypatch.setattr(portal.stu, "graduation_submit_final", fake_final)

    portal.submit_proposal(user, {
        "background": "真实选题背景",
        "plan": "真实研究计划",
        "outcome": "预期成果",
        "attachments": ["101"],
        "expectedVersion": 4,
    })
    portal.submit_final(user, {
        "finalType": "定稿",
        "attachments": ["202"],
        "expectedVersion": 9,
    })

    assert captured["proposal"][0] is user
    assert captured["proposal"][1]["expectedVersion"] == 4
    assert captured["proposal"][1]["attachments"] == ["101"]
    assert captured["final"][0] is user
    assert captured["final"][1] == {
        "finalType": "定稿",
        "attachments": ["202"],
        "expectedVersion": 9,
    }


def test_u10_pc_midterm_and_grade_appeal_delegate_without_second_write_truth(monkeypatch):
    user = {"userType": "STUDENT", "userId": "db-1001"}
    captured = {}

    monkeypatch.setattr(
        portal.stu,
        "graduation_midterm_rectify",
        lambda actor, content: captured.setdefault("midterm", (actor, content)) or {"status": "RECTIFIED"},
    )
    monkeypatch.setattr(
        portal.stu,
        "graduation_grade_appeal",
        lambda actor, reason: captured.setdefault("appeal", (actor, reason)) or {"status": "PENDING"},
    )

    portal.midterm_rectify(user, {"content": "已按导师意见完成整改"})
    portal.grade_appeal(user, {"reason": "成绩构成与已发布材料不一致"})

    assert captured["midterm"] == (user, "已按导师意见完成整改")
    assert captured["appeal"] == (user, "成绩构成与已发布材料不一致")
