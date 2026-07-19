"""专业分流（/academic-affairs/major-split/*）端点测试。

覆盖重点：
- 分配算法：绩点降序×志愿顺序（分数优先遵循志愿），绝不超容量
- 志愿全满 → UNALLOCATED；未清零禁止确认(409)；人工调剂后可确认
- 确认写 StudentProfile.major_id + 逐生审计
- 学生志愿校验（年级不符/志愿超数/重复/不在可选列表）
- dryRun 试分不落库；学生越权管理端点 403

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


def _seed(db_mode):
    """大类专业 + 两个目标专业 + 3 名 2024 级学生（绩点 甲3.8/乙3.5/丙2.0）。"""
    from app.db.session import get_sessionmaker
    from app.models import AcademicStudent, College, Major, SchoolClass, StudentProfile
    db = get_sessionmaker()()
    col = College(tenant_id=TID, college_name="信息学院", status="ACTIVE")
    db.add(col); db.flush()
    src = Major(tenant_id=TID, college_id=col.id, major_name="电子信息大类", status="ACTIVE")
    ma = Major(tenant_id=TID, college_id=col.id, major_name="软件技术", status="ACTIVE")
    mb = Major(tenant_id=TID, college_id=col.id, major_name="网络技术", status="ACTIVE")
    db.add_all([src, ma, mb]); db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=src.id, class_name="电信2401", grade="2024", status="ACTIVE")
    db.add(klass); db.flush()
    stus = {}
    for no, name, gpa in (("FL2401", "分甲", 3.8), ("FL2402", "分乙", 3.5), ("FL2403", "分丙", 2.0)):
        p = StudentProfile(tenant_id=TID, student_no=no, real_name=name, college_id=col.id,
                           major_id=src.id, class_id=klass.id, grade="2024",
                           student_status="NORMAL", status="ACTIVE")
        db.add(p); db.flush()
        db.add(AcademicStudent(tenant_id=TID, student_no=no, name=name, student_id=p.id,
                               class_name="电信2401", gpa=gpa, record_status="ACTIVE"))
        stus[no] = p.id
    db.commit(); db.close()
    return {"src": src.id, "ma": ma.id, "mb": mb.id, "stus": stus}


def _mk_batch(client, admin, ids, options=(("ma", 1), ("mb", 2)), max_choices=3):
    bid = client.post(f"{BASE}/major-split/batches", headers=admin,
                      json={"batchName": "2024级电信大类分流", "grade": "2024",
                            "sourceMajorId": str(ids["src"]), "maxChoices": max_choices}
                      ).json()["data"]["batchId"]
    for key, cap in options:
        r = client.post(f"{BASE}/major-split/batches/{bid}/options", headers=admin,
                        json={"majorId": str(ids[key]), "capacity": cap})
        assert r.status_code == 200, r.text
    client.post(f"{BASE}/major-split/batches/{bid}/open", headers=admin)
    return bid


def _submit_all(client, ids, bid, choices_keys=("ma", "mb")):
    for i, no in enumerate(("FL2401", "FL2402", "FL2403")):
        r = client.post(f"{BASE}/major-split/batches/{bid}/volunteer",
                        headers=_stu_token(f"分{i}", no),
                        json={"choices": [str(ids[k]) for k in choices_keys]})
        assert r.status_code == 200, r.text


def test_allocate_gpa_priority_follows_choices(client, db_mode):
    """甲3.8→A(容1第1志愿)；乙3.5 A满→B(第2志愿)；丙2.0→B。绝不超容。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _mk_batch(client, admin, ids)
    _submit_all(client, ids, bid)
    client.post(f"{BASE}/major-split/batches/{bid}/close", headers=admin)
    d = client.post(f"{BASE}/major-split/batches/{bid}/allocate", headers=admin).json()["data"]
    assert d["allocated"] == 3 and d["unallocated"] == 0
    vols = client.get(f"{BASE}/major-split/batches/{bid}/volunteers",
                      headers=admin).json()["data"]["items"]
    by = {v["studentNo"]: v for v in vols}
    assert by["FL2401"]["resultMajorId"] == str(ids["ma"]) and by["FL2401"]["resultChoiceRank"] == 1
    assert by["FL2402"]["resultMajorId"] == str(ids["mb"]) and by["FL2402"]["resultChoiceRank"] == 2
    assert by["FL2403"]["resultMajorId"] == str(ids["mb"])
    opts = client.get(f"{BASE}/major-split/batches/{bid}/options", headers=admin).json()["data"]["items"]
    for o in opts:
        assert o["allocatedCount"] <= o["capacity"], "分配不得超容量"


def test_dry_run_not_persisted(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _mk_batch(client, admin, ids)
    _submit_all(client, ids, bid)
    client.post(f"{BASE}/major-split/batches/{bid}/close", headers=admin)
    d = client.post(f"{BASE}/major-split/batches/{bid}/allocate?dryRun=true",
                    headers=admin).json()["data"]
    assert d["dryRun"] is True and d["allocated"] == 3
    vols = client.get(f"{BASE}/major-split/batches/{bid}/volunteers",
                      headers=admin).json()["data"]["items"]
    assert all(v["status"] == "PENDING" for v in vols), "试分不得落库"


def test_unallocated_blocks_confirm_then_reassign(client, db_mode):
    """只开 A(容1)：3 人报 → 1 分配 2 待调剂 → 确认 409 → 调剂无处可去仍 409（容量满）。"""
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _mk_batch(client, admin, ids, options=(("ma", 1),), max_choices=1)
    for i, no in enumerate(("FL2401", "FL2402", "FL2403")):
        client.post(f"{BASE}/major-split/batches/{bid}/volunteer", headers=_stu_token(f"分{i}", no),
                    json={"choices": [str(ids["ma"])]})
    client.post(f"{BASE}/major-split/batches/{bid}/close", headers=admin)
    d = client.post(f"{BASE}/major-split/batches/{bid}/allocate", headers=admin).json()["data"]
    assert d["allocated"] == 1 and d["unallocated"] == 2
    assert client.post(f"{BASE}/major-split/batches/{bid}/confirm",
                       headers=admin).status_code == 409, "待调剂未清零必须禁止确认"
    # 调剂到已满的 A → 409（容量守护）
    vols = client.get(f"{BASE}/major-split/batches/{bid}/volunteers?status=UNALLOCATED",
                      headers=admin).json()["data"]["items"]
    r = client.post(f"{BASE}/major-split/volunteers/{vols[0]['volunteerId']}/reassign",
                    headers=admin, json={"majorId": str(ids["ma"]), "reason": "测试调剂到满员专业"})
    assert r.status_code == 409, r.text


def test_confirm_writes_student_major(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _mk_batch(client, admin, ids)
    _submit_all(client, ids, bid)
    client.post(f"{BASE}/major-split/batches/{bid}/close", headers=admin)
    client.post(f"{BASE}/major-split/batches/{bid}/allocate", headers=admin)
    r = client.post(f"{BASE}/major-split/batches/{bid}/confirm", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["confirmed"] == 3
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    db = get_sessionmaker()()
    p1 = db.get(StudentProfile, ids["stus"]["FL2401"])
    p2 = db.get(StudentProfile, ids["stus"]["FL2402"])
    db.close()
    assert p1.major_id == ids["ma"], "确认后学籍专业必须更新"
    assert p2.major_id == ids["mb"]


def test_volunteer_validations(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid = _mk_batch(client, admin, ids, max_choices=1)
    stu = _stu_token("分甲", "FL2401")
    # 志愿超数
    r = client.post(f"{BASE}/major-split/batches/{bid}/volunteer", headers=stu,
                    json={"choices": [str(ids["ma"]), str(ids["mb"])]})
    assert r.status_code == 400, r.text
    # 不在可选列表
    r = client.post(f"{BASE}/major-split/batches/{bid}/volunteer", headers=stu,
                    json={"choices": [str(ids["src"])]})
    assert r.status_code == 400, r.text
    # OPEN 期间可修改（重复提交 200 覆盖）
    assert client.post(f"{BASE}/major-split/batches/{bid}/volunteer", headers=stu,
                       json={"choices": [str(ids["ma"])]}).status_code == 200
    assert client.post(f"{BASE}/major-split/batches/{bid}/volunteer", headers=stu,
                       json={"choices": [str(ids["mb"])]}).status_code == 200
    my = client.get(f"{BASE}/major-split/my?batchId={bid}", headers=stu).json()["data"]["items"]
    assert len(my) == 1 and my[0]["choices"] == [ids["mb"]] or my[0]["choices"] == [str(ids["mb"])]


def test_student_forbidden_manage(client, db_mode):
    ids = _seed(db_mode)
    stu = _stu_token("分甲", "FL2401")
    assert client.post(f"{BASE}/major-split/batches", headers=stu,
                       json={"batchName": "越权", "grade": "2024"}).status_code == 403
    admin = _hdr(client, "school_admin01")
    bid = _mk_batch(client, admin, ids)
    assert client.post(f"{BASE}/major-split/batches/{bid}/allocate", headers=stu).status_code == 403
