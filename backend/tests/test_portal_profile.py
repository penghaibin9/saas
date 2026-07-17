"""学生 PC 门户 · 我的档案测试（MySQL 真库 via db_mode）：

学籍只读（脱敏 + 组织名）/ 敏感明文授权查看（填原因→明文+水印；缺原因/非法字段拒绝）/ 非学生拒绝。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/profile"
TID = 1000000000000000001
IDCARD = "110101200203150011"


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


def _seed(no, name, id_card=IDCARD):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="F",
                       grade="2022", id_card_encrypted=id_card,
                       current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
    db.add(s)
    db.commit()
    db.close()


def test_enrollment_masked(client, db_mode):
    _seed("PRF-001", "档案一")
    h = _stu_token("档案一", "PRF-001")
    r = client.get(f"{PORTAL}/enrollment", headers=h).json()
    assert r["code"] == 0 and r["data"]["hasData"] is True
    d = r["data"]
    assert d["studentNo"] == "PRF-001" and d["name"] == "档案一"
    assert d["idCardMasked"] and d["idCardMasked"] != IDCARD          # 默认脱敏
    assert "idCard" in d["sensitiveViewable"]


def test_sensitive_view_plaintext_with_reason(client, db_mode):
    _seed("PRF-002", "档案二")
    h = _stu_token("档案二", "PRF-002")
    ok = client.post(f"{PORTAL}/sensitive", headers=h,
                     json={"field": "idCard", "reason": "办理助学贷款需核对"}).json()
    assert ok["code"] == 0
    assert ok["data"]["value"] == IDCARD and ok["data"]["watermark"] == "档案二"


def test_sensitive_view_guards(client, db_mode):
    _seed("PRF-003", "档案三")
    h = _stu_token("档案三", "PRF-003")
    assert client.post(f"{PORTAL}/sensitive", headers=h,
                       json={"field": "idCard"}).json()["code"] != 0          # 缺原因
    assert client.post(f"{PORTAL}/sensitive", headers=h,
                       json={"field": "homeAddr", "reason": "x1"}).json()["code"] != 0  # 非法字段


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(f"{PORTAL}/enrollment", headers=admin).json()["code"] == 403001
