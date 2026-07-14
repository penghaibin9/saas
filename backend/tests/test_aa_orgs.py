"""13B-R3 学院专业班级（组织架构）· 端到端。

O1 学院→专业→班级 CRUD 级联；O2 教学秘书绑定/解绑落审计；O3 班级调整移动学生+审计；
O4 组织树/统计/年级聚合；O5 越权（学生令牌 403）；O6 状态机/校验异常（占比/学制/删非空父级）；
O7 组织变更审计 AA_ORG_* 可读。

数据范围：school_admin01=TENANT_ALL 走全流程；student01 无 academicAffairs 权限点 → 403。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs/orgs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _mk_college(client, hdr, name="软件学院", short="软院"):
    return client.post(f"{BASE}/colleges", headers=hdr,
                       json={"collegeName": name, "shortName": short, "sortOrder": 1}).json()["data"]


def _mk_major(client, hdr, college_id, name="软件技术"):
    return client.post(f"{BASE}/majors", headers=hdr, json={
        "collegeId": college_id, "majorName": name, "educationYears": 3,
        "trainingLevel": "HIGHER", "enrollStatus": "ENROLLING", "direction": "Web方向"}).json()["data"]


def _mk_class(client, hdr, major_id, name="软件2601", grade="2026"):
    return client.post(f"{BASE}/classes", headers=hdr, json={
        "majorId": major_id, "className": name, "classCode": "RJ2601", "grade": grade,
        "capacity": 40, "graduateYear": "2029", "classStatus": "NORMAL"}).json()["data"]


def test_o1_college_major_class_crud(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    col = _mk_college(client, hdr)
    assert col["shortName"] == "软院" and col["status"] == "ACTIVE"
    maj = _mk_major(client, hdr, col["id"])
    assert maj["educationYears"] == 3 and maj["enrollStatus"] == "ENROLLING" and maj["direction"] == "Web方向"
    cls = _mk_class(client, hdr, maj["id"])
    assert cls["capacity"] == 40 and cls["classStatus"] == "NORMAL" and cls["classCode"] == "RJ2601"
    # 列表可见
    cols = client.get(f"{BASE}/colleges", headers=hdr).json()["data"]["items"]
    assert any(c["id"] == col["id"] for c in cols)
    majs = client.get(f"{BASE}/majors?collegeId={col['id']}", headers=hdr).json()["data"]["items"]
    assert any(m["id"] == maj["id"] for m in majs)
    clss = client.get(f"{BASE}/classes?majorId={maj['id']}", headers=hdr).json()["data"]["items"]
    assert any(c["id"] == cls["id"] for c in clss)
    # 编辑专业招生状态 → 停招
    up = client.put(f"{BASE}/majors/{maj['id']}", headers=hdr, json={"enrollStatus": "STOPPED"}).json()["data"]
    assert up["enrollStatus"] == "STOPPED"


def test_o2_bind_secretary_audit(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    col = _mk_college(client, hdr, "机电学院", "机电")
    r = client.post(f"{BASE}/colleges/{col['id']}/secretary", headers=hdr,
                    json={"secretaryId": "88"}).json()["data"]
    assert r["secretaryId"] == "88"
    # 解绑
    r2 = client.post(f"{BASE}/colleges/{col['id']}/secretary", headers=hdr,
                     json={"secretaryId": None}).json()["data"]
    assert r2["secretaryId"] is None
    aud = client.get(f"{BASE}/audit?bizType=AA_ORG_COLLEGE", headers=hdr).json()["data"]["items"]
    assert any(a["action"] == "BIND_SECRETARY" for a in aud)


def test_o3_class_adjust_moves_student(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    hdr = _hdr(client, "school_admin01")
    col = _mk_college(client, hdr, "商贸学院", "商贸")
    maj = _mk_major(client, hdr, col["id"], "电子商务")
    c1 = _mk_class(client, hdr, maj["id"], "电商2601")
    c2 = _mk_class(client, hdr, maj["id"], "电商2602")
    db = get_sessionmaker()()
    s = StudentProfile(tenant_id=TID, student_no="ADJ001", real_name="调整生", class_id=int(c1["id"]),
                       major_id=int(maj["id"]), current_stage="ON_CAMPUS",
                       student_status="REGISTERED", status="ACTIVE")
    db.add(s); db.flush(); sid = s.id
    db.commit(); db.close()
    r = client.post(f"{BASE}/class-adjustments", headers=hdr,
                    json={"studentId": str(sid), "targetClassId": c2["id"]}).json()["data"]
    assert r["toClassId"] == c2["id"] and r["fromClassId"] == c1["id"]
    # 目标班学生列表含之
    stu = client.get(f"{BASE}/classes/{c2['id']}/students", headers=hdr).json()["data"]["items"]
    assert any(x["id"] == str(sid) for x in stu)
    # 审计留痕
    aud = client.get(f"{BASE}/audit?bizType=AA_ORG_CLASS_ADJUST", headers=hdr).json()["data"]["items"]
    assert any(a["action"] == "ADJUST_CLASS" for a in aud)


def test_o4_tree_stats_grades(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    col = _mk_college(client, hdr, "建筑学院", "建院")
    maj = _mk_major(client, hdr, col["id"], "建筑工程")
    _mk_class(client, hdr, maj["id"], "建工2601", "2026")
    tree = client.get(f"{BASE}/tree", headers=hdr).json()["data"]
    assert any(c["collegeName"] == "建筑学院" and c["majors"] for c in tree["colleges"])
    stats = client.get(f"{BASE}/stats", headers=hdr).json()["data"]
    assert stats["collegeCount"] >= 1 and stats["classCount"] >= 1 and stats["enrollingMajorCount"] >= 1
    grades = client.get(f"{BASE}/grades", headers=hdr).json()["data"]["items"]
    assert any(g["grade"] == "2026" and g["classCount"] >= 1 for g in grades)


def test_o5_student_token_forbidden(client, db_mode):
    hdr = _hdr(client, "student01")
    assert client.get(f"{BASE}/colleges", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/colleges", headers=hdr, json={"collegeName": "X"}).status_code == 403
    assert client.get(f"{BASE}/tree", headers=hdr).status_code == 403


def test_o6_validation_and_guard(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    col = _mk_college(client, hdr, "医护学院", "医护")
    # 学制越界 → 400（本项目 pydantic 校验错误统一转 400，见 test_aa_grade 既有契约）
    assert client.post(f"{BASE}/majors", headers=hdr, json={
        "collegeId": col["id"], "majorName": "护理", "educationYears": 99}).status_code == 400
    maj = _mk_major(client, hdr, col["id"], "护理")
    _mk_class(client, hdr, maj["id"], "护理2601")
    # 删非空学院 → 409（下有专业）
    assert client.delete(f"{BASE}/colleges/{col['id']}", headers=hdr).status_code == 409
    # 删非空专业 → 409（下有班级）
    assert client.delete(f"{BASE}/majors/{maj['id']}", headers=hdr).status_code == 409
    # 同名专业重复 → 409
    assert client.post(f"{BASE}/majors", headers=hdr, json={
        "collegeId": col["id"], "majorName": "护理"}).status_code == 409


def test_o7_teaching_classes_readonly(client, db_mode):
    """教学班无独立表：无教学任务时返回空汇总（只读，不 500）。"""
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/teaching-classes", headers=hdr)
    assert r.status_code == 200 and "items" in r.json()["data"]
