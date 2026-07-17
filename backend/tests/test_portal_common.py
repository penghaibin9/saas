"""学生 PC 门户 · PC 重活公共底座测试（MySQL 真库 via db_mode）：

电子签(内容哈希快照+确认校验+provider可插拔:法律级未采购拒绝) / 打印留痕 / 导出留痕 / 非学生拒绝。
"""
from __future__ import annotations

import hashlib

PORTAL = "/api/v1/portal/common"
TID = 1000000000000000001


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC"})}


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    db.add(StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M",
                          current_stage="GRADUATION", student_status="NORMAL", status="ACTIVE"))
    db.commit()
    db.close()


def test_sign_reliable_log(client, db_mode):
    _seed("SGN-001", "签一")
    h = _stu_token("签一", "SGN-001")
    content = "本人已阅读并确认毕业设计任务书全部内容。"
    r = client.post(f"{PORTAL}/sign", headers=h, json={
        "bizType": "GRADUATION_TASKBOOK", "bizId": "TB-1",
        "content": content, "confirm": True}).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["contentHash"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert d["provider"] == "reliable_log" and d["legalEffect"] is False
    assert d["signerName"] == "签一" and d["signedAt"]


def test_sign_guards(client, db_mode):
    _seed("SGN-002", "签二")
    h = _stu_token("签二", "SGN-002")
    base = {"bizType": "GRADUATION_TASKBOOK", "content": "x", "confirm": True}
    assert client.post(f"{PORTAL}/sign", headers=h, json={**base, "confirm": False}).json()["code"] != 0  # 未确认
    assert client.post(f"{PORTAL}/sign", headers=h, json={**base, "content": ""}).json()["code"] != 0       # 空内容
    assert client.post(f"{PORTAL}/sign", headers=h, json={**base, "bizType": ""}).json()["code"] != 0        # 缺bizType
    # 法律级 provider 未采购 → 拒绝
    assert client.post(f"{PORTAL}/sign", headers=h,
                       json={**base, "provider": "fadada"}).json()["code"] != 0


def test_print_and_export_log(client, db_mode):
    _seed("SGN-003", "签三")
    h = _stu_token("签三", "SGN-003")
    p = client.post(f"{PORTAL}/print-log", headers=h,
                    json={"bizType": "TRANSCRIPT", "bizId": "T1", "docName": "成绩单"}).json()
    assert p["code"] == 0 and p["data"]["watermark"] == "签三"
    e = client.post(f"{PORTAL}/export-log", headers=h,
                    json={"bizType": "TRANSCRIPT", "docName": "成绩单.pdf"}).json()
    assert e["code"] == 0 and e["data"]["watermark"] == "签三"


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.post(f"{PORTAL}/sign", headers=admin,
                       json={"bizType": "X", "content": "y", "confirm": True}).json()["code"] == 403001
