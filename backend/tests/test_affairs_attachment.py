"""13A 增强(c) · 统一业务附件授权下载 + 敏感审计（真实 MySQL）。

上传复用 /api/v1/files/upload（真实落盘 t_file_object）；关联/列表/下载走 /student-affairs/attachments，
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
    r = client.post("/api/v1/files/upload", headers=hdr,
                    files={"file": ("stage.pdf", b"%PDF-1.4 league material bytes", "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()["data"]["fileId"]


def test_attachment_authorized_flow_and_audit(client, db_mode):
    """学工处：上传→关联党团材料→列表→授权下载 200，并写 SENSITIVE_EXPORT 审计。"""
    from app.db.session import get_sessionmaker
    from app.models import SecurityAuditLog
    hdr = _hdr(client, "sa_admin01")
    fid = _upload(client, hdr)
    # 关联（LEAGUE 需 league.manage；学工处 studentAffairs.* 命中）
    a = client.post(f"{BASE}/attachments", headers=hdr,
                    json={"bizType": "LEAGUE", "bizId": 1, "fileId": fid, "note": "阶段材料"}).json()
    assert a["code"] == 0, a
    att_id = a["data"]["attachmentId"]
    # 列表（脱敏：只回名称+id，无路径）
    lst = client.get(f"{BASE}/attachments?bizType=LEAGUE&bizId=1", headers=hdr).json()["data"]["items"]
    assert any(x["attachmentId"] == att_id for x in lst)
    assert "fileKey" not in (lst[0] if lst else {}) and "path" not in (lst[0] if lst else {})
    # 授权下载 200
    dl = client.get(f"{BASE}/attachments/{att_id}/download", headers=hdr)
    assert dl.status_code == 200, dl.text
    # 审计落库：SENSITIVE_EXPORT / affairs_attachment:LEAGUE
    db = get_sessionmaker()()
    try:
        n = db.query(SecurityAuditLog).filter_by(
            action="SENSITIVE_EXPORT", resource="affairs_attachment:LEAGUE").count()
    finally:
        db.close()
    assert n >= 1, "授权下载业务材料必须写 SENSITIVE_EXPORT 安全审计"


def test_attachment_link_denied_for_wrong_role(client, db_mode):
    """越权关联：辅导员无 league.manage → 关联党团材料 403。"""
    hdr_admin = _hdr(client, "sa_admin01")
    fid = _upload(client, hdr_admin)
    r = client.post(f"{BASE}/attachments", headers=_hdr(client, "counselor01"),
                    json={"bizType": "LEAGUE", "bizId": 2, "fileId": fid})
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_PERMISSION"


def test_attachment_download_denied_for_wrong_role(client, db_mode):
    """越权下载：宿管无 league.view → 下载党团材料 403（且不泄露文件）。"""
    hdr_admin = _hdr(client, "sa_admin01")
    fid = _upload(client, hdr_admin)
    att_id = client.post(f"{BASE}/attachments", headers=hdr_admin,
                         json={"bizType": "LEAGUE", "bizId": 3, "fileId": fid}).json()["data"]["attachmentId"]
    r = client.get(f"{BASE}/attachments/{att_id}/download", headers=_hdr(client, "dorm01"))
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_PERMISSION"
