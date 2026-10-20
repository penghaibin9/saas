"""Student profile material gaps reuse the canonical four-end material workflow."""
from __future__ import annotations

from test_affairs_material_biz_context_entry_contract import TID, _hdr, _seed
from test_aid_mobile_queue import _login


def _data(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("code") == 0, body
    return body["data"]


def test_profile_material_return_resubmit_and_accept(client, db_mode):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import Role, StudentAccountLink, User, UserRole

    ids = _seed(db_mode)
    with get_sessionmaker()() as db:
        role = db.query(Role).filter_by(tenant_id=TID, role_code="STUDENT").first()
        if role is None:
            role = Role(
                tenant_id=TID, role_code="STUDENT", role_name="学生",
                role_type="SYSTEM", status="ACTIVE",
            )
            db.add(role)
            db.flush()
        student_user = User(
            tenant_id=TID, login_name="profile_material_student", real_name="李四",
            user_type="STUDENT", password_hash=hash_password("Profile-Material-2026!"),
            status="ACTIVE", must_change_password=False,
        )
        db.add(student_user)
        db.flush()
        db.add_all([
            UserRole(
                tenant_id=TID, user_id=student_user.id, role_id=role.id,
                status="ACTIVE",
            ),
            StudentAccountLink(
                tenant_id=TID, user_id=student_user.id, student_id=ids["student"],
                link_status="ACTIVE", source="MANUAL",
            ),
        ])
        db.commit()

    teacher_pc = _hdr(client, "school_admin01")
    # Use the production login path so the token carries userType=STUDENT.
    # The mock-login helper intentionally represents a staff client.
    student = _login(client, "profile_material_student", "PC")
    context = {"bizType": "PROFILE", "bizId": ids["student"]}

    resolved = _data(client.get(
        "/api/v1/student-affairs/material-center/biz-context",
        headers=teacher_pc, params=context,
    ))
    assert resolved["studentId"] == str(ids["student"])
    assert resolved["businessContext"]["bizDisplayTitle"] == "学生个人档案"

    requirement = _data(client.post(
        "/api/v1/student-affairs/material-requirements", headers=teacher_pc,
        json={
            **context,
            "itemCode": "PROFILE_PHOTO",
            "itemName": "个人档案照片",
            "requirementReason": "请补交清晰的近期个人档案照片",
        },
    ))
    requirement_id = requirement["requirementId"]
    submit_url = f"/api/v1/mobile/affairs/material-requirements/{requirement_id}/submissions"
    review_url = f"/api/v1/student-affairs/material-requirements/{requirement_id}/review"

    mine = _data(client.get(
        "/api/v1/mobile/affairs/material-requirements", headers=student,
        params=context,
    ))
    assert mine["total"] == 1
    assert mine["items"][0]["allowedActions"] == ["SUBMIT_MATERIAL"]

    def upload(text):
        result = _data(client.post(
            "/api/v1/files", headers=student,
            data={"bizType": "MATERIAL_SUPPLEMENT"},
            files={"file": ("profile-photo.txt", text.encode("utf-8"), "text/plain")},
        ))
        return result["fileId"]

    first = _data(client.post(
        submit_url, headers=student,
        json={
            "fileId": upload("first profile material version"),
            "note": "第一版档案照片说明",
            "version": requirement["version"],
        },
    ))
    returned = _data(client.post(
        review_url, headers=teacher_pc,
        json={
            "action": "RETURN",
            "reason": "照片边缘缺失，请重新上传完整页面",
            "version": first["version"],
        },
    ))
    second = _data(client.post(
        submit_url, headers=student,
        json={
            "fileId": upload("complete profile material version"),
            "note": "已补充完整页面",
            "version": returned["version"],
        },
    ))
    accepted = _data(client.post(
        review_url, headers=teacher_pc,
        json={"action": "ACCEPT", "version": second["version"]},
    ))

    assert accepted["status"] == "ACCEPTED"
    assert len(accepted["versions"]) == 2
    final = _data(client.get(
        "/api/v1/mobile/affairs/material-requirements", headers=student,
        params=context,
    ))["items"][0]
    assert final["status"] == "ACCEPTED"
    assert final["allowedActions"] == []
    assert final["businessContext"]["bizDisplayTitle"] == "学生个人档案"
