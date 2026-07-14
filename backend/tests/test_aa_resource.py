"""13B-R4 教学资源 · 教室字典 端到端（真实 DB 模式）。

T1 建教室→列表→详情；T2 同楼栋同编号重复409；T3 编辑（含改唯一键去重）；
T4 状态机切换+幂等+options 仅返回可用；T5 逻辑删除后不可见；
T6 容量/类型非法422；T7 越权：学生令牌403、辅导员令牌403（无 academicAffairs.*）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _mk(client, hdr, building_code="A", room_code="101", **kw):
    body = {"buildingCode": building_code, "buildingName": kw.get("buildingName", "教学A楼"),
            "roomCode": room_code, "capacity": kw.get("capacity", 60),
            "roomType": kw.get("roomType", "MULTIMEDIA")}
    body.update({k: v for k, v in kw.items() if k in ("roomName", "campusCode", "remark")})
    return client.post(f"{BASE}/classrooms", headers=hdr, json=body)


def test_t1_create_list_detail(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    r = _mk(client, hdr, "A", "101").json()["data"]
    assert r["status"] == "AVAILABLE" and r["capacity"] == 60 and r["roomTypeLabel"] == "多媒体教室"
    cid = r["classroomId"]
    lst = client.get(f"{BASE}/classrooms", headers=hdr, params={"buildingCode": "A"}).json()["data"]
    assert lst["total"] >= 1 and any(x["classroomId"] == cid for x in lst["items"])
    det = client.get(f"{BASE}/classrooms/{cid}", headers=hdr).json()["data"]
    assert det["roomCode"] == "101" and det["roomName"] == "教学A楼101"


def test_t2_duplicate_409(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    _mk(client, hdr, "B", "201")
    assert _mk(client, hdr, "B", "201").status_code == 409


def test_t3_update_and_unique_recheck(client, db_mode):
    hdr = _hdr(client, "academic01")  # ACADEMIC_TEACHER 有 academicAffairs.*
    c1 = _mk(client, hdr, "C", "301").json()["data"]["classroomId"]
    c2 = _mk(client, hdr, "C", "302").json()["data"]["classroomId"]
    # 正常改容量/类型
    r = client.put(f"{BASE}/classrooms/{c1}", headers=hdr,
                   json={"capacity": 120, "roomType": "COMPUTER"}).json()["data"]
    assert r["capacity"] == 120 and r["roomType"] == "COMPUTER" and r["version"] >= 1
    # 把 c2 改成与 c1 相同 building+room → 409
    assert client.put(f"{BASE}/classrooms/{c2}", headers=hdr,
                      json={"roomCode": "301"}).status_code == 409


def test_t4_status_and_options(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _mk(client, hdr, "D", "401").json()["data"]["classroomId"]
    # 切到维修中
    r = client.post(f"{BASE}/classrooms/{cid}/status", headers=hdr,
                    json={"status": "MAINTENANCE", "reason": "空调检修"}).json()["data"]
    assert r["status"] == "MAINTENANCE"
    # 幂等重复切
    r2 = client.post(f"{BASE}/classrooms/{cid}/status", headers=hdr, json={"status": "MAINTENANCE"})
    assert r2.status_code == 200
    # options 只返回 AVAILABLE，故此教室不在其中
    opts = client.get(f"{BASE}/classrooms/options", headers=hdr).json()["data"]["items"]
    assert all(o["classroomId"] != cid for o in opts)
    # 切回可用后进入 options
    client.post(f"{BASE}/classrooms/{cid}/status", headers=hdr, json={"status": "AVAILABLE"})
    opts2 = client.get(f"{BASE}/classrooms/options", headers=hdr).json()["data"]["items"]
    assert any(o["classroomId"] == cid and o["capacity"] == 60 for o in opts2)


def test_t5_soft_delete(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    cid = _mk(client, hdr, "E", "501").json()["data"]["classroomId"]
    assert client.delete(f"{BASE}/classrooms/{cid}", headers=hdr).status_code == 200
    assert client.get(f"{BASE}/classrooms/{cid}", headers=hdr).status_code == 404
    lst = client.get(f"{BASE}/classrooms", headers=hdr, params={"buildingCode": "E"}).json()["data"]
    assert all(x["classroomId"] != cid for x in lst["items"])
    # 删后可重新建同编号（唯一键仅约束未删记录）
    assert _mk(client, hdr, "E", "501").status_code == 200


def test_t6_validation_400(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 容量超限（服务层 VALIDATION_ERROR → 400）
    assert _mk(client, hdr, "F", "601", capacity=99999).status_code == 400
    # 类型非法
    assert _mk(client, hdr, "F", "602", roomType="BOGUS").status_code == 400
    # 缺必填（楼栋名称空）
    assert client.post(f"{BASE}/classrooms", headers=hdr,
                       json={"buildingCode": "F", "buildingName": "", "roomCode": "603"}).status_code == 400


def test_t7_authz_denied(client, db_mode):
    admin = _hdr(client, "school_admin01")
    cid = _mk(client, admin, "G", "701").json()["data"]["classroomId"]
    # 学生：空权限集 → 403
    stu = _hdr(client, "student01")
    assert client.get(f"{BASE}/classrooms", headers=stu).status_code == 403
    assert _mk(client, stu, "G", "702").status_code == 403
    # 辅导员：无 academicAffairs.* → 403（写与删均拒）
    cnt = _hdr(client, "counselor01")
    assert client.post(f"{BASE}/classrooms/{cid}/status", headers=cnt,
                       json={"status": "DISABLED"}).status_code == 403
    assert client.delete(f"{BASE}/classrooms/{cid}", headers=cnt).status_code == 403


def test_t8_classroom_booking_and_conflict(client, db_mode):
    """教室预约：申请PENDING→审核APPROVED；同教室同时段再审批冲突409。"""
    hdr = _hdr(client, "school_admin01")
    cid = _mk(client, hdr, room_code="801").json()["data"]["classroomId"]
    b1 = client.post(f"{BASE}/classrooms/bookings", headers=hdr,
                     json={"classroomId": str(cid), "bookingDate": "2027-06-20", "slotNo": 1, "purpose": "社团活动"}).json()
    assert b1["code"] == 0 and b1["data"]["status"] == "PENDING"
    bid1 = b1["data"]["bookingId"]
    # 审核通过
    assert client.post(f"{BASE}/classrooms/bookings/{bid1}/review", headers=hdr,
                       json={"action": "APPROVE"}).json()["data"]["status"] == "APPROVED"
    # 同教室同日同节次再申请 → 409（已占用）
    assert client.post(f"{BASE}/classrooms/bookings", headers=hdr,
                       json={"classroomId": str(cid), "bookingDate": "2027-06-20", "slotNo": 1}).status_code == 409
    # 不同节次可申请
    b3 = client.post(f"{BASE}/classrooms/bookings", headers=hdr,
                     json={"classroomId": str(cid), "bookingDate": "2027-06-20", "slotNo": 3}).json()
    assert b3["code"] == 0
    # 驳回原因过短 400
    assert client.post(f"{BASE}/classrooms/bookings/{b3['data']['bookingId']}/review", headers=hdr,
                       json={"action": "REJECT", "reason": "x"}).status_code == 400
