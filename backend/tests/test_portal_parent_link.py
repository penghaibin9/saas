"""学生 PC 门户 · 家长授权代理（proxy）学生侧测试（MySQL 真库 via db_mode）：

覆盖：绑定成功+列表脱敏 / 校验（姓名·手机号·范围）/ 重复手机号冲突 / 撤销状态机 /
跨学生越权(403002) / 非学生令牌拒绝(403001)。全程严格「本人」数据范围。
"""
from __future__ import annotations

PORTAL = "/api/v1/portal/parent/guardians"
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


def _seed_student(no, name):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    s = StudentProfile(tenant_id=TID, student_no=no, real_name=name, gender="M",
                       current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
    db.add(s)
    db.commit()
    sid = s.id
    db.close()
    return sid


def _bind(client, hdr, name="张父", phone="13800138000", relation="FATHER",
          scopes=("ACADEMIC_GRADE", "CAREER_PROGRESS")):
    return client.post(PORTAL, headers=hdr, json={
        "guardianName": name, "guardianPhone": phone, "relation": relation,
        "visibleScopes": list(scopes)}).json()


def test_bind_and_list_masked(client, db_mode):
    _seed_student("SPL-001", "选一")
    h = _stu_token("选一", "SPL-001")
    r = _bind(client, h)
    assert r["code"] == 0 and r["data"]["status"] == "ACTIVE"
    lst = client.get(PORTAL, headers=h).json()
    assert lst["code"] == 0 and lst["data"]["hasData"] is True
    item = lst["data"]["items"][0]
    assert item["guardianName"] == "张父" and item["relation"] == "FATHER"
    assert set(item["visibleScopes"]) == {"ACADEMIC_GRADE", "CAREER_PROGRESS"}
    # 手机号必须脱敏，不得回明文
    assert item["guardianPhone"] and item["guardianPhone"] != "13800138000"


def test_bind_validation(client, db_mode):
    _seed_student("SPL-002", "选二")
    h = _stu_token("选二", "SPL-002")
    assert _bind(client, h, name="")["code"] != 0                      # 姓名必填
    assert _bind(client, h, phone="139")["code"] != 0                  # 手机号非法
    assert _bind(client, h, scopes=())["code"] != 0                    # 至少一项范围
    # 非授权范围（如心理关注）被过滤 → 视为空范围 → 拒绝
    assert client.post(PORTAL, headers=h, json={
        "guardianName": "张母", "guardianPhone": "13800138001",
        "visibleScopes": ["MENTAL_HEALTH"]}).json()["code"] != 0


def test_duplicate_phone_conflict(client, db_mode):
    _seed_student("SPL-003", "选三")
    h = _stu_token("选三", "SPL-003")
    assert _bind(client, h, phone="13900139000")["code"] == 0
    dup = _bind(client, h, phone="13900139000")
    assert dup["code"] == 409001


def test_revoke_state_machine(client, db_mode):
    _seed_student("SPL-004", "选四")
    h = _stu_token("选四", "SPL-004")
    lid = _bind(client, h, phone="13700137000")["data"]["id"]
    rv = client.post(f"{PORTAL}/{lid}/revoke", headers=h).json()
    assert rv["code"] == 0 and rv["data"]["status"] == "REVOKED"
    item = client.get(PORTAL, headers=h).json()["data"]["items"][0]
    assert item["status"] == "REVOKED"
    # 撤销后同一手机号可重新授权（旧行已非 ACTIVE）
    assert _bind(client, h, phone="13700137000")["code"] == 0


def test_cross_student_scope_forbidden(client, db_mode):
    _seed_student("SPL-005", "甲")
    _seed_student("SPL-006", "乙")
    ha = _stu_token("甲", "SPL-005")
    hb = _stu_token("乙", "SPL-006")
    lid = _bind(client, ha, phone="13600136000")["data"]["id"]
    # 乙 不能撤销 甲 的授权 → 数据范围越权 403002
    assert client.post(f"{PORTAL}/{lid}/revoke", headers=hb).json()["code"] == 403002
    # 乙 的列表看不到 甲 的授权
    assert client.get(PORTAL, headers=hb).json()["data"]["hasData"] is False


def test_non_student_rejected(client, db_mode):
    admin = _admin(client)
    assert client.get(PORTAL, headers=admin).json()["code"] == 403001
    assert client.post(PORTAL, headers=admin, json={
        "guardianName": "x", "guardianPhone": "13800138000",
        "visibleScopes": ["ACADEMIC_GRADE"]}).json()["code"] == 403001
