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


def test_m5_room_abnormal_exception_no_orphan_risk(client, db_mode):
    """SEC-4：纯房间级卫生异常(无涉事学生) → 建异常记录，但不再生成 student_id=0 孤儿风险。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _make_building(client, hdr)
    rid, _ = _first_bed(client, hdr, bid)
    task = client.post(f"{BASE}/dorm/check-tasks", headers=hdr, json={
        "taskName": "月度卫生检查", "buildingId": str(bid), "checkType": "HYGIENE"}).json()["data"]["taskId"]
    r = client.post(f"{BASE}/dorm/check-tasks/{task}/records", headers=hdr, json={
        "roomId": str(rid), "result": "ABNORMAL", "issueType": "HYGIENE",
        "detail": "卫生不合格，垃圾未清理"}).json()
    assert r["data"]["relatedExceptionId"] and not r["data"]["relatedRiskId"]  # 异常在、无孤儿风险
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord, CsDormException
    db = get_sessionmaker()()
    assert db.query(AffairsRiskRecord).filter_by(source="DORM").count() == 0  # 不再有 student_id=0 孤儿
    assert db.query(CsDormException).count() == 1
    db.close()


def test_m8_student_abnormal_binds_real_risk(client, db_mode):
    """SEC-4：异常指定涉事学生 → 风险绑真实 student_id（非 0），列表按范围可见。"""
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _make_building(client, hdr)
    rid, _ = _first_bed(client, hdr, bid)
    task = client.post(f"{BASE}/dorm/check-tasks", headers=hdr, json={
        "taskName": "夜查", "buildingId": str(bid), "checkType": "NIGHT_ABSENCE"}).json()["data"]["taskId"]
    # 夜不归宿不指定学生 → 400
    assert client.post(f"{BASE}/dorm/check-tasks/{task}/records", headers=hdr, json={
        "roomId": str(rid), "result": "ABNORMAL", "issueType": "NIGHT_ABSENCE",
        "detail": "23:00 未归宿且失联"}).status_code == 400
    # 指定真实学生 → 生成绑该生的风险
    r = client.post(f"{BASE}/dorm/check-tasks/{task}/records", headers=hdr, json={
        "roomId": str(rid), "result": "ABNORMAL", "issueType": "NIGHT_ABSENCE",
        "detail": "23:00 未归宿且失联", "studentId": str(ids["sm"])}).json()
    assert r["data"]["relatedRiskId"]
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord
    db = get_sessionmaker()()
    risk = db.query(AffairsRiskRecord).filter_by(source="DORM").first()
    assert risk and risk.student_id == ids["sm"]  # 绑真实学生，非 0
    db.close()


def test_m9_dorm_permission_least_privilege(client, db_mode):
    """宿管仅宿舍权限：能访问 /dorm/*，但看不到心理/风险明细端点；无宿舍权限角色被 403。"""
    _seed(db_mode)
    dorm = _hdr(client, "dorm01")
    assert client.get(f"{BASE}/dorm/buildings", headers=dorm).status_code == 200  # 宿管可用宿舍
    assert client.get(f"{BASE}/mental/list", headers=dorm).status_code == 403     # 宿管不得见心理
    assert client.get(f"{BASE}/risk/records", headers=dorm).status_code == 403    # 宿管不得见风险明细
    # 无宿舍权限的就业老师 → /dorm/* 403
    assert client.get(f"{BASE}/dorm/buildings", headers=_hdr(client, "employment01")).status_code == 403


def test_m10_dorm_building_scope(client, db_mode):
    """DORM_BUILDING：宿管只看到自己负责的楼栋。"""
    _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    # A 楼归 dorm01；B 楼不归
    a = client.post(f"{BASE}/dorm/buildings", headers=admin, json={
        "buildingName": "紫荆A", "genderLimit": "MALE", "managerTeacherKey": "dorm01"}).json()["data"]["buildingId"]
    client.post(f"{BASE}/dorm/buildings", headers=admin, json={
        "buildingName": "梅苑B", "genderLimit": "FEMALE", "managerTeacherKey": "other"})
    # 学工处看到 2 栋
    admin_bs = client.get(f"{BASE}/dorm/buildings", headers=admin).json()["data"]["items"]
    assert len(admin_bs) >= 2
    # 宿管 dorm01 只看到 A
    dorm_bs = client.get(f"{BASE}/dorm/buildings", headers=_hdr(client, "dorm01")).json()["data"]["items"]
    bids = {b["buildingId"] for b in dorm_bs}
    assert a in bids and all(b["buildingName"] == "紫荆A" for b in dorm_bs)


def test_m6_one_step_building(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 建楼时直接带布局 → 一步铺满
    client.post(f"{BASE}/dorm/buildings", headers=hdr, json={
        "buildingName": "梅苑A栋", "genderLimit": "FEMALE",
        "floors": 3, "roomsPerFloor": 2, "bedsPerRoom": 6})
    occ = client.get(f"{BASE}/dorm/occupancy", headers=hdr).json()["data"]
    assert occ["totalBeds"] == 36  # 3×2×6


def test_m7_self_select_toggle(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    bid = _make_building(client, hdr)
    _, beds = _first_bed(client, hdr, bid)
    # 默认关：配置显示辅导员分配 + 给学生的提醒文案
    cfg_off = client.get(f"{BASE}/dorm/config", headers=hdr).json()["data"]
    assert cfg_off["selfSelectEnabled"] is False and cfg_off["assignMode"] == "COUNSELOR_ASSIGN"
    assert "辅导员" in cfg_off["studentNotice"]  # 关闭时提醒学生
    # 学生自选 → 403，错误信息即提醒文案
    r403 = client.post(f"{BASE}/dorm/beds/{beds[0]['bedId']}/self-select", headers=hdr,
                       json={"studentId": str(ids["sm"])})
    assert r403.status_code == 403 and "辅导员" in r403.text
    # 辅导员分配（普通 checkin）始终可用 —— 不受开关影响
    assert client.post(f"{BASE}/dorm/beds/{beds[1]['bedId']}/checkin", headers=hdr,
                       json={"studentId": str(ids["sm"])}).status_code == 200
    # 学校放开
    client.put(f"{BASE}/dorm/config/self-select", headers=hdr, json={"enabled": True})
    cfg = client.get(f"{BASE}/dorm/config", headers=hdr).json()["data"]
    assert cfg["selfSelectEnabled"] is True and cfg["assignMode"] == "SELF_SELECT"
    # 放开后学生自选成功（换到另一张床）
    r = client.post(f"{BASE}/dorm/beds/{beds[2]['bedId']}/self-select", headers=hdr,
                    json={"studentId": str(ids["sm"])}).json()
    assert r["data"]["status"] == "OCCUPIED"
