"""选课多轮次+抽签（/academic-affairs/selection/**/rounds*）端点测试。

覆盖重点：
- 轮次生命周期（建→开→关→摇号 DRAWN 终态）；同批次双 OPEN 409
- 抽签轮：志愿登记不占容量；超额摇号后 中签=容量数、未中签 LOTTERY_LOST；绝不超容
- 摇号确定性（同输入重跑同结果——通过"摇号只许一次"的 409 终态保证不可重摇）
- 三态选课控制：allow_enroll=False 拦选课；allow_drop=False 拦退课
- 抽签志愿可撤回（不动容量）
- 无轮次批次行为不变（由既有 test_aa_selection.py 12 例回归兜底，本文件不重复）
- 学生越权操作轮次 403

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name, "studentNo": student_no,
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode, students=3):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, College, Major, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    db.add(col); db.flush()
    major = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="软件2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    c1 = AaCourse(tenant_id=TID, course_code="RND001", course_name="轮次选修课", credit=2, status="ENABLED")
    db.add(c1); db.flush()
    stus = []
    for i in range(students):
        s = StudentProfile(tenant_id=TID, student_no=f"RND24{i + 1:02d}", real_name=f"轮学{i + 1}",
                           college_id=col.id, major_id=major.id, class_id=klass.id, grade="2024",
                           student_status="NORMAL", status="ACTIVE")
        db.add(s); db.flush()
        stus.append(s.student_no)
    db.commit(); db.close()
    return {"course1": c1.id, "studentNos": stus}


def _open_batch(client, admin, course_id, capacity=5):
    bid = client.post(f"{BASE}/selection/batches", headers=admin,
                      json={"batchName": "轮次测试批次"}).json()["data"]["batchId"]
    scid = client.post(f"{BASE}/selection/batches/{bid}/courses", headers=admin,
                       json={"courseId": str(course_id), "capacity": capacity,
                             "minCapacity": 1}).json()["data"]["selectionCourseId"]
    client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin)
    client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin)
    return bid, scid


def _add_round(client, admin, bid, name="第一轮预选", mode="LOTTERY", **kw):
    body = {"roundName": name, "mode": mode, **kw}
    r = client.post(f"{BASE}/selection/batches/{bid}/rounds", headers=admin, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]["roundId"]


def _course_state(client, admin, bid, scid):
    # 后端分页统一返回 items（前端 api 层的 callList 才映射为 list）
    items = client.get(f"{BASE}/selection/batches/{bid}/courses", headers=admin).json()["data"]["items"]
    return next(c for c in items if str(c["selectionCourseId"]) == str(scid))


# ── 轮次生命周期 ──

def test_round_lifecycle_and_single_open(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _open_batch(client, admin, ids["course1"])
    r1 = _add_round(client, admin, bid, "第一轮预选", "LOTTERY")
    r2 = _add_round(client, admin, bid, "第二轮正选", "FCFS")
    assert client.post(f"{BASE}/selection/rounds/{r1}/open", headers=admin).status_code == 200
    # 同批次第二个 OPEN → 409
    assert client.post(f"{BASE}/selection/rounds/{r2}/open", headers=admin).status_code == 409
    assert client.post(f"{BASE}/selection/rounds/{r1}/close", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/rounds/{r2}/open", headers=admin).status_code == 200


# ── 抽签核心 ──

def test_lottery_register_does_not_consume_capacity(client, db_mode):
    ids = _seed(db_mode, students=2)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"], capacity=5)
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin)
    for i, sno in enumerate(ids["studentNos"][:2]):
        r = client.post(f"{BASE}/selection/student/enroll", headers=_stu_token(f"轮学{i + 1}", sno),
                        json={"selectionCourseId": str(scid)})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "PENDING_LOTTERY"
    st = _course_state(client, admin, bid, scid)
    assert st["selectedCount"] == 0, "抽签志愿不得占容量"


def test_lottery_draw_respects_capacity(client, db_mode):
    """容量1、3人报名 → 摇号后恰1人中签、2人 LOTTERY_LOST、容量恰满。"""
    ids = _seed(db_mode, students=3)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"], capacity=1)
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin)
    for i, sno in enumerate(ids["studentNos"]):
        client.post(f"{BASE}/selection/student/enroll", headers=_stu_token(f"轮学{i + 1}", sno),
                    json={"selectionCourseId": str(scid)})
    client.post(f"{BASE}/selection/rounds/{rid}/close", headers=admin)
    d = client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin)
    assert d.status_code == 200, d.text
    res = d.json()["data"]
    assert res["totalWinners"] == 1 and res["totalLosers"] == 2
    st = _course_state(client, admin, bid, scid)
    assert st["selectedCount"] == 1, "中签数必须恰等于容量，绝不超容"
    # 名册核验：1 SELECTED + 2 LOTTERY_LOST
    from app.db.session import get_sessionmaker
    from app.models import AaSelectionRecord
    db = get_sessionmaker()()
    rows = db.query(AaSelectionRecord).filter(AaSelectionRecord.batch_id == bid).all()
    statuses = sorted(r.status for r in rows)
    db.close()
    assert statuses == ["LOTTERY_LOST", "LOTTERY_LOST", "SELECTED"]


def test_lottery_all_win_when_under_capacity(client, db_mode):
    ids = _seed(db_mode, students=2)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"], capacity=5)
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin)
    for i, sno in enumerate(ids["studentNos"][:2]):
        client.post(f"{BASE}/selection/student/enroll", headers=_stu_token(f"轮学{i + 1}", sno),
                    json={"selectionCourseId": str(scid)})
    client.post(f"{BASE}/selection/rounds/{rid}/close", headers=admin)
    res = client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin).json()["data"]
    assert res["totalWinners"] == 2 and res["totalLosers"] == 0
    assert _course_state(client, admin, bid, scid)["selectedCount"] == 2


def test_draw_gates(client, db_mode):
    """开启中不可摇号；摇完 DRAWN 不可重摇。"""
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _open_batch(client, admin, ids["course1"])
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin)
    assert client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin).status_code == 409
    client.post(f"{BASE}/selection/rounds/{rid}/close", headers=admin)
    assert client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=admin).status_code == 409


# ── 三态选课控制 ──

def test_enroll_blocked_when_round_disallows(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"])
    rid = _add_round(client, admin, bid, "补退选(只可退)", "FCFS", allowEnroll=False)
    client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin)
    r = client.post(f"{BASE}/selection/student/enroll", headers=_stu_token("轮学1", ids["studentNos"][0]),
                    json={"selectionCourseId": str(scid)})
    assert r.status_code == 409, r.text


def test_drop_blocked_when_round_disallows(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"])
    stu = _stu_token("轮学1", ids["studentNos"][0])
    # 无轮次时先选上
    assert client.post(f"{BASE}/selection/student/enroll", headers=stu,
                       json={"selectionCourseId": str(scid)}).status_code == 200
    rid = _add_round(client, admin, bid, "正选(只可选)", "FCFS", allowDrop=False)
    client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin)
    r = client.post(f"{BASE}/selection/student/drop", headers=stu,
                    json={"selectionCourseId": str(scid)})
    assert r.status_code == 409, r.text


def test_withdraw_pending_lottery(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, scid = _open_batch(client, admin, ids["course1"], capacity=5)
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    client.post(f"{BASE}/selection/rounds/{rid}/open", headers=admin)
    stu = _stu_token("轮学1", ids["studentNos"][0])
    client.post(f"{BASE}/selection/student/enroll", headers=stu, json={"selectionCourseId": str(scid)})
    r = client.post(f"{BASE}/selection/student/drop", headers=stu, json={"selectionCourseId": str(scid)})
    assert r.status_code == 200 and r.json()["data"]["status"] == "DROPPED"
    assert _course_state(client, admin, bid, scid)["selectedCount"] == 0


# ── 越权 ──

def test_student_cannot_manage_rounds(client, db_mode):
    ids = _seed(db_mode, students=1)
    admin = _hdr(client, "school_admin01")
    bid, _scid = _open_batch(client, admin, ids["course1"])
    rid = _add_round(client, admin, bid, "预选抽签", "LOTTERY")
    stu = _stu_token("轮学1", ids["studentNos"][0])
    assert client.post(f"{BASE}/selection/batches/{bid}/rounds", headers=stu,
                       json={"roundName": "越权轮"}).status_code == 403
    assert client.post(f"{BASE}/selection/rounds/{rid}/open", headers=stu).status_code == 403
    assert client.post(f"{BASE}/selection/rounds/{rid}/draw", headers=stu).status_code == 403
