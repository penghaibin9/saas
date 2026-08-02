"""13A 增强(c) · 统一业务附件授权下载 + 敏感审计（真实 MySQL）。

上传复用 /api/v1/files（真实落盘 t_file_object）；关联/列表/下载走 /student-affairs/attachments，
按 biz 细粒度权限门禁；每次授权下载写 t_security_audit_log(SENSITIVE_EXPORT)。
覆盖：授权关联+列表+下载 200 且审计落库；越权关联 403；越权下载 403。
"""
from __future__ import annotations

BASE = "/api/v1/student-affairs"


def _hdr(client, login):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _upload(client, hdr) -> str:
    response = client.post(
        "/api/v1/files",
        headers=hdr,
        files={"file": ("stage.pdf", b"%PDF-1.4 league material bytes", "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["fileId"]


def _seed_league_dev(db_mode) -> int:
    from app.db.session import get_sessionmaker
    from app.models import AffairsLeagueDev

    db = get_sessionmaker()()
    row = AffairsLeagueDev(
        tenant_id=1000000000000000001,
        student_id=int(db_mode["student"]),
        dev_type="PARTY",
        current_stage="APPLICANT",
        branch_name="测试党支部",
        status="ONGOING",
    )
    db.add(row); db.commit(); db.refresh(row)
    row_id = int(row.id)
    db.close()
    return row_id


def _link(client, hdr, biz_id, file_id, note=""):
    response = client.post(
        f"{BASE}/attachments",
        headers=hdr,
        json={"bizType": "LEAGUE", "bizId": biz_id, "fileId": file_id, "note": note},
    ).json()
    return response


def test_attachment_authorized_flow_and_audit(client, db_mode):
    """学工处：上传→关联真实党团材料→列表→授权下载 200，并写 SENSITIVE_EXPORT 审计。"""
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog

    hdr = _hdr(client, "sa_admin01")
    biz_id = _seed_league_dev(db_mode)
    file_id = _upload(client, hdr)
    linked = _link(client, hdr, biz_id, file_id, "阶段材料")
    assert linked["code"] == 0, linked
    attachment_id = linked["data"]["attachmentId"]

    items = client.get(
        f"{BASE}/attachments?bizType=LEAGUE&bizId={biz_id}", headers=hdr,
    ).json()["data"]["items"]
    assert any(item["attachmentId"] == attachment_id for item in items)
    assert "fileKey" not in (items[0] if items else {})
    assert "path" not in (items[0] if items else {})

    download = client.get(f"{BASE}/attachments/{attachment_id}/download", headers=hdr)
    assert download.status_code == 200, download.text

    db = get_sessionmaker()()
    try:
        count = db.query(SecurityAuditLog).filter_by(
            action="SENSITIVE_EXPORT", resource="affairs_attachment:LEAGUE",
        ).count()
    finally:
        db.close()
    assert count >= 1, "授权下载业务材料必须写 SENSITIVE_EXPORT 安全审计"


def test_attachment_link_denied_for_wrong_role(client, db_mode):
    """越权关联：真实业务对象存在，但辅导员无 league.manage，仍返回403。"""
    admin = _hdr(client, "sa_admin01")
    biz_id = _seed_league_dev(db_mode)
    file_id = _upload(client, admin)
    response = client.post(
        f"{BASE}/attachments",
        headers=_hdr(client, "counselor01"),
        json={"bizType": "LEAGUE", "bizId": biz_id, "fileId": file_id},
    )
    assert response.status_code == 403
    assert response.json()["bizCode"] == "NO_PERMISSION"


def test_attachment_download_denied_for_wrong_role(client, db_mode):
    """越权下载：真实党团材料已关联，宿管被对象级数据范围门拦截且不泄露文件。"""
    admin = _hdr(client, "sa_admin01")
    biz_id = _seed_league_dev(db_mode)
    file_id = _upload(client, admin)
    linked = _link(client, admin, biz_id, file_id)
    assert linked["code"] == 0, linked
    attachment_id = linked["data"]["attachmentId"]

    response = client.get(
        f"{BASE}/attachments/{attachment_id}/download",
        headers=_hdr(client, "dorm01"),
    )
    assert response.status_code == 403
    assert response.json()["bizCode"] == "NO_DATA_SCOPE"
