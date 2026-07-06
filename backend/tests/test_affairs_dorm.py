"""13A-P6 宿舍房源台账 · 端到端（真实 DB 模式）。

M1 建楼+铺床(生成器)；M2 选床级联+入住回写t_cs_dorm_record；M3 占用/性别冲突409；
M4 调宿审批执行(原床释放/新床占用)；M5 检查异常→回写异常表+生成风险(DORM)；M6 一步到位建楼。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="软件2101", grade="2021", status="ACTIVE")
    db.add(a); db.flush()
    sm = StudentProfile(tenant_id=TID, student_no="M001", real_name="男生甲", class_id=a.id, gender="M",
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    sf = StudentProfile(tenant_id=TID, student_no="F001", real_name="女生乙", class_id=a.id, gender="F",
                        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    db.add(sm); db.add(sf); db.flush()
    ids = {"A": a.id, "sm": sm.id, "sf": sf.id}
    db.commit()
    db.close()
    return ids


def _make_building(client, hdr, gender="MALE"):
    bid = client.post(f"{BASE}/dorm/buildings", headers=hdr, json={
        "buildingName": "紫荆1号楼", "buildingCode": "ZJ01", "genderLimit": gender}).json()["data"]["buildingId"]
    client.post(f"{BASE}/dorm/buildings/{bid}/generate", headers=hdr,
                json={"floors": 2, "roomsPerFloor": 3, "bedsPerRoom": 4})
    return bid


def _first_bed(client, hdr, bid, floor=1, room_idx=0):
    rooms = client.get(f"{BASE}/dorm/buildings/{bid}/rooms?floor={floor}", headers=hdr).json()["data"]["items"]
    rid = rooms[room_idx]["roomId"]
    beds = client.get(f"{BASE}/dorm/rooms/{rid}/beds", headers=hdr).json()["data"]["items"]
    return rid, beds


def test_m1_generate_beds(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _make_building(client, hdr)
    occ = client.get(f"{BASE}/dorm/occupancy", headers=hdr).json()["data"]
    assert occ["totalBeds"] == 24 and occ["vacantBeds"] == 24  # 2层×3间×4床


def test_m2_cascade_checkin_writeback(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _make_building(client, hdr)
    # 级联：楼列表（男生过滤仍见男寝）
    bs = client.get(f"{BASE}/dorm/buildings?gender=M", headers=hdr).json()["data"]["items"]
    assert any(b["buildingId"] == bid for b in bs)
    rid, beds = _first_bed(client, hdr, bid)
    assert len(beds) == 4 and all(b["status"] == "VACANT" for b in beds)
    # 入住第一张床
    r = client.post(f"{BASE}/dorm/beds/{beds[0]['bedId']}/checkin", headers=hdr,
                    json={"studentId": str(ids["sm"])}).json()
    assert r["data"]["status"] == "OCCUPIED"
    # 房间空床 -1
    rooms = client.get(f"{BASE}/dorm/buildings/{bid}/rooms?floor=1", headers=hdr).json()["data"]["items"]
    assert next(x for x in rooms if x["roomId"] == rid)["vacantBeds"] == 3
    # 回写 t_cs_dorm_record
    from app.db.session import get_sessionmaker
    from app.models import CsDormRecord
    db = get_sessionmaker()()
    assert db.query(CsDormRecord).filter_by(building="紫荆1号楼", status="IN").count() == 1
    db.close()


def test_m3_occupied_and_gender_conflict_409(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _make_building(client, hdr, gender="MALE")
    _, beds = _first_bed(client, hdr, bid)
    client.post(f"{BASE}/dorm/beds/{beds[0]['bedId']}/checkin", headers=hdr, json={"studentId": str(ids["sm"])})
    # 已占用 → 409
    assert client.post(f"{BASE}/dorm/beds/{beds[0]['bedId']}/checkin", headers=hdr,
                       json={"studentId": str(ids["sm"])}).status_code == 409
    # 女生入住男寝空床 → 409
    assert client.post(f"{BASE}/dorm/beds/{beds[1]['bedId']}/checkin", headers=hdr,
                       json={"studentId": str(ids["sf"])}).status_code == 409


def test_m4_transfer_executes(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _make_building(client, hdr)
    _, beds1 = _first_bed(client, hdr, bid, floor=1)
    _, beds2 = _first_bed(client, hdr, bid, floor=2)
    old_bed, new_bed = beds1[0]["bedId"], beds2[0]["bedId"]
    client.post(f"{BASE}/dorm/beds/{old_bed}/checkin", headers=hdr, json={"studentId": str(ids["sm"])})
    tid = client.post(f"{BASE}/dorm/transfers", headers=hdr, json={
        "studentId": str(ids["sm"]), "toBedId": str(new_bed), "reason": "调宿"}).json()["data"]["transferId"]
    client.post(f"{BASE}/dorm/transfers/{tid}/review", headers=hdr, json={"action": "APPROVE"})  # 辅导员
    r = client.post(f"{BASE}/dorm/transfers/{tid}/review", headers=hdr, json={"action": "APPROVE"}).json()  # 宿管→执行
    assert r["data"]["status"] == "EXECUTED"
    # 原床释放、新床占用
    from app.db.session import get_sessionmaker
    from app.models import DormBed
    db = get_sessionmaker()()
    assert db.get(DormBed, int(old_bed)).status == "VACANT"
    assert db.get(DormBed, int(new_bed)).status == "OCCUPIED"
    db.close()


def test_m5_check_abnormal_creates_risk(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _make_building(client, hdr)
    rid, _ = _first_bed(client, hdr, bid)
    task = client.post(f"{BASE}/dorm/check-tasks", headers=hdr, json={
        "taskName": "月度卫生检查", "buildingId": str(bid), "checkType": "HYGIENE"}).json()["data"]["taskId"]
    r = client.post(f"{BASE}/dorm/check-tasks/{task}/records", headers=hdr, json={
        "roomId": str(rid), "result": "ABNORMAL", "issueType": "HYGIENE",
        "detail": "卫生不合格，垃圾未清理"}).json()
    assert r["data"]["relatedRiskId"] and r["data"]["relatedExceptionId"]
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord, CsDormException
    db = get_sessionmaker()()
    assert db.query(AffairsRiskRecord).filter_by(source="DORM").count() == 1
    assert db.query(CsDormException).count() == 1
    db.close()


def test_m6_one_step_building(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 建楼时直接带布局 → 一步铺满
    client.post(f"{BASE}/dorm/buildings", headers=hdr, json={
        "buildingName": "梅苑A栋", "genderLimit": "FEMALE",
        "floors": 3, "roomsPerFloor": 2, "bedsPerRoom": 6})
    occ = client.get(f"{BASE}/dorm/occupancy", headers=hdr).json()["data"]
    assert occ["totalBeds"] == 36  # 3×2×6
