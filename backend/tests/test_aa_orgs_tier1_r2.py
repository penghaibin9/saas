"""13B-学院专业班级 Tier1 续工 R2 · 端到端（真实 DB 模式）。

06 专业方向：D1 总开关默认关闭 400 FEATURE_DISABLED；D2 教务处启用/学院教务无权设置；
D3 CRUD + 同编码冲突409；D4 跨学院403；D5 学生token403。
07 班级学生（增强）：S1 关键字+性别/学籍状态/手机号脱敏；S2 跨学院403。
08 班级调整申请单：A1 合班全链路(发起→核对→执行，来源班class_status→DISBANDED)；
A2 停用核对阻断(有在读学生)→执行400；A3 无权限403；A4 跨学院403002；A5 跨租户404；
A6 核对过期→执行409；A7 撤销。

数据范围复用 test_aa_status_change.py 的 _seed_scoped 模式：school_admin01=TENANT_ALL；
college_admin01 需显式 TeacherStudentScope(COLLEGE,软件学院) 行才会收敛到本学院（无该行时 fail-closed）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

TID = 1000000000000000001
TID2 = 1000000000000000002
BASE = "/api/v1/academic-affairs/orgs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_scoped(db_mode):
    """两学院两专业各一班，college_admin01 授权限定「软件学院」；额外一名在读学生供阻断测试。"""
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    col_sw = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    col_wl = College(tenant_id=TID, college_name="网络学院", status="ACTIVE")
    db.add(col_sw); db.add(col_wl); db.flush()
    maj_sw = Major(tenant_id=TID, college_id=col_sw.id, major_name="软件技术", status="ACTIVE",
                   enroll_status="ENROLLING")
    maj_wl = Major(tenant_id=TID, college_id=col_wl.id, major_name="网络技术", status="ACTIVE",
                   enroll_status="ENROLLING")
    db.add(maj_sw); db.add(maj_wl); db.flush()
    c1 = SchoolClass(tenant_id=TID, major_id=maj_sw.id, class_name="软件2601", grade="2026",
                     class_status="NORMAL", status="ACTIVE", capacity=40)
    c2 = SchoolClass(tenant_id=TID, major_id=maj_sw.id, class_name="软件2602", grade="2026",
                     class_status="NORMAL", status="ACTIVE", capacity=40)
    c_empty = SchoolClass(tenant_id=TID, major_id=maj_sw.id, class_name="软件2603（拟停用）", grade="2023",
                          class_status="NORMAL", status="ACTIVE", capacity=40)
    c_wl = SchoolClass(tenant_id=TID, major_id=maj_wl.id, class_name="网络2601", grade="2026",
                       class_status="NORMAL", status="ACTIVE", capacity=40)
    db.add_all([c1, c2, c_empty, c_wl]); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="ORG601", real_name="方向甲", gender="男",
                        class_id=c1.id, major_id=maj_sw.id, college_id=col_sw.id,
                        current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="ORG602", real_name="方向乙", gender="女",
                        class_id=c1.id, major_id=maj_sw.id, college_id=col_sw.id,
                        current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add_all([s1, s2]); db.flush()
    from app.models import StudentContact
    db.add(StudentContact(tenant_id=TID, student_id=s1.id, contact_type="PHONE",
                          contact_value_encrypted="13900001111", is_primary=True, verified_status="VERIFIED"))
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", teacher_name="张晓明",
                               role_code="COLLEGE_ADMIN", scope_type="COLLEGE", ref_value="软件学院",
                               status="ACTIVE"))
    db.commit()
    ids = {"colSw": col_sw.id, "colWl": col_wl.id, "majSw": maj_sw.id, "majWl": maj_wl.id,
          "c1": c1.id, "c2": c2.id, "cEmpty": c_empty.id, "cWl": c_wl.id, "s1": s1.id, "s2": s2.id}
    db.close()
    return ids


# ═══════════ 06 专业方向 ═══════════

def test_d1_toggle_default_off_blocks_all(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/major-direction-toggle", headers=hdr)
    assert r.status_code == 200 and r.json()["data"]["enabled"] is False
    r2 = client.get(f"{BASE}/majors/{ids['majSw']}/directions", headers=hdr)
    assert r2.status_code == 400 and r2.json()["bizCode"] == "FEATURE_DISABLED"
    r3 = client.post(f"{BASE}/majors/{ids['majSw']}/directions", headers=hdr,
                     json={"directionName": "Web方向"})
    assert r3.status_code == 400


def test_d2_toggle_only_tenant_all_role(client, db_mode):
    ids = _seed_scoped(db_mode)
    admin_hdr = _hdr(client, "school_admin01")
    college_hdr = _hdr(client, "college_admin01")
    r_denied = client.post(f"{BASE}/major-direction-toggle", headers=college_hdr, json={"enabled": True})
    assert r_denied.status_code == 403
    r_ok = client.post(f"{BASE}/major-direction-toggle", headers=admin_hdr, json={"enabled": True})
    assert r_ok.status_code == 200 and r_ok.json()["data"]["enabled"] is True


def test_d3_direction_crud_and_dup_code_conflict(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "school_admin01")
    client.post(f"{BASE}/major-direction-toggle", headers=hdr, json={"enabled": True})
    d1 = client.post(f"{BASE}/majors/{ids['majSw']}/directions", headers=hdr,
                     json={"directionName": "Web开发方向", "code": "WEB"}).json()["data"]
    assert d1["status"] == "ACTIVE" and d1["code"] == "WEB"
    # 同编码冲突
    r_dup = client.post(f"{BASE}/majors/{ids['majSw']}/directions", headers=hdr,
                        json={"directionName": "嵌入式方向", "code": "WEB"})
    assert r_dup.status_code == 409
    # 编辑
    up = client.put(f"{BASE}/majors/{ids['majSw']}/directions/{d1['id']}", headers=hdr,
                    json={"directionName": "Web全栈方向"}).json()["data"]
    assert up["directionName"] == "Web全栈方向"
    # 停用（幂等）
    dis1 = client.post(f"{BASE}/majors/{ids['majSw']}/directions/{d1['id']}/disable", headers=hdr).json()["data"]
    assert dis1["status"] == "DISABLED"
    dis2 = client.post(f"{BASE}/majors/{ids['majSw']}/directions/{d1['id']}/disable", headers=hdr).json()["data"]
    assert dis2["status"] == "DISABLED"
    # 列表可见
    lst = client.get(f"{BASE}/majors/{ids['majSw']}/directions", headers=hdr).json()["data"]["items"]
    assert any(x["id"] == d1["id"] for x in lst)


def test_d4_direction_cross_college_denied(client, db_mode):
    ids = _seed_scoped(db_mode)
    admin_hdr = _hdr(client, "school_admin01")
    client.post(f"{BASE}/major-direction-toggle", headers=admin_hdr, json={"enabled": True})
    college_hdr = _hdr(client, "college_admin01")
    # college_admin01 限「软件学院」，对网络学院专业发起 → 403
    r = client.post(f"{BASE}/majors/{ids['majWl']}/directions", headers=college_hdr,
                    json={"directionName": "越权方向"})
    assert r.status_code == 403
    # 对本学院专业可正常操作
    r_ok = client.post(f"{BASE}/majors/{ids['majSw']}/directions", headers=college_hdr,
                       json={"directionName": "本院方向"})
    assert r_ok.status_code == 200


def test_d5_direction_student_token_forbidden(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "student01")
    assert client.get(f"{BASE}/majors/{ids['majSw']}/directions", headers=hdr).status_code == 403


# ═══════════ 07 班级学生（增强）═══════════

def test_s1_students_roster_fields_and_keyword(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/classes/{ids['c1']}/students", headers=hdr).json()["data"]
    assert r["total"] == 2
    row1 = next(x for x in r["items"] if x["studentNo"] == "ORG601")
    assert row1["realName"] == "方向甲" and row1["gender"] == "男" and row1["studentStatus"] == "NORMAL"
    assert row1["phoneMasked"].startswith("139") and "****" in row1["phoneMasked"]
    assert "9001111" not in row1["phoneMasked"] or row1["phoneMasked"] != "13900001111"
    # 关键字过滤
    r2 = client.get(f"{BASE}/classes/{ids['c1']}/students", headers=hdr,
                    params={"keyword": "方向乙"}).json()["data"]
    assert r2["total"] == 1 and r2["items"][0]["realName"] == "方向乙"


def test_s2_students_roster_cross_college_denied(client, db_mode):
    ids = _seed_scoped(db_mode)
    college_hdr = _hdr(client, "college_admin01")
    r = client.get(f"{BASE}/classes/{ids['cWl']}/students", headers=college_hdr)
    assert r.status_code == 403


# ═══════════ 08 班级调整申请单 ═══════════

def test_a1_merge_full_flow_updates_class_status(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "school_admin01")
    create = client.post(f"{BASE}/class-adjustment-requests", headers=hdr, json={
        "adjustType": "MERGE", "fromClassIds": [str(ids["c2"])], "toClassId": str(ids["c1"]),
        "reason": "编制不足两班合并教学安排"}).json()["data"]
    assert create["status"] == "DRAFT"
    aid = create["id"]
    checked = client.post(f"{BASE}/class-adjustment-requests/{aid}/precheck", headers=hdr).json()["data"]
    assert checked["status"] == "CHECKED" and checked["checkResult"]["blocked"] is False
    executed = client.post(f"{BASE}/class-adjustment-requests/{aid}/execute", headers=hdr).json()["data"]
    assert executed["status"] == "EXECUTED"
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass
    db = get_sessionmaker()()
    c2_after = db.get(SchoolClass, int(ids["c2"]))
    assert c2_after.class_status == "DISBANDED"
    db.close()
    # 幂等重复执行
    executed2 = client.post(f"{BASE}/class-adjustment-requests/{aid}/execute", headers=hdr).json()["data"]
    assert executed2["status"] == "EXECUTED"


def test_a2_disband_blocked_by_active_students(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "school_admin01")
    create = client.post(f"{BASE}/class-adjustment-requests", headers=hdr, json={
        "adjustType": "DISBAND", "fromClassIds": [str(ids["c1"])], "reason": "误建班级需撤销"}).json()["data"]
    aid = create["id"]
    checked = client.post(f"{BASE}/class-adjustment-requests/{aid}/precheck", headers=hdr).json()["data"]
    assert checked["checkResult"]["blocked"] is True  # c1 仍有2名在读学生
    r_exec = client.post(f"{BASE}/class-adjustment-requests/{aid}/execute", headers=hdr)
    assert r_exec.status_code == 400
    # 空班可正常停用
    create2 = client.post(f"{BASE}/class-adjustment-requests", headers=hdr, json={
        "adjustType": "DISBAND", "fromClassIds": [str(ids["cEmpty"])], "reason": "空班误建需撤销"}).json()["data"]
    aid2 = create2["id"]
    client.post(f"{BASE}/class-adjustment-requests/{aid2}/precheck", headers=hdr)
    r_exec2 = client.post(f"{BASE}/class-adjustment-requests/{aid2}/execute", headers=hdr)
    assert r_exec2.status_code == 200 and r_exec2.json()["data"]["status"] == "EXECUTED"


def test_a3_create_denied_without_permission(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "student01")
    r = client.post(f"{BASE}/class-adjustment-requests", headers=hdr, json={
        "adjustType": "MERGE", "fromClassIds": [str(ids["c2"])], "toClassId": str(ids["c1"]),
        "reason": "无权限尝试"})
    assert r.status_code == 403


def test_a4_cross_college_denied(client, db_mode):
    ids = _seed_scoped(db_mode)
    college_hdr = _hdr(client, "college_admin01")
    # 混选跨学院班级 → 校验期即拒绝（合班仅限同学院）
    r_mixed = client.post(f"{BASE}/class-adjustment-requests", headers=college_hdr, json={
        "adjustType": "MERGE", "fromClassIds": [str(ids["cWl"])], "toClassId": str(ids["c1"]),
        "reason": "跨学院混选测试"})
    assert r_mixed.status_code == 400
    # 纯越权学院班级（网络学院）单独发起 → 403
    r_out = client.post(f"{BASE}/class-adjustment-requests", headers=college_hdr, json={
        "adjustType": "DISBAND", "fromClassIds": [str(ids["cWl"])], "reason": "越权停用网络学院班级"})
    assert r_out.status_code == 403


def test_a5_cross_tenant_not_found(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaClassAdjustmentRequest
    ids = _seed_scoped(db_mode)
    db = get_sessionmaker()()
    other = AaClassAdjustmentRequest(tenant_id=TID2, adjust_type="DISBAND",
                                     from_class_ids=f'[{ids["c1"]}]', reason="其它租户数据", status="DRAFT")
    db.add(other); db.commit(); db.refresh(other)
    oid = other.id
    db.close()
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/class-adjustment-requests/{oid}/precheck", headers=hdr)
    assert r.status_code == 404


def test_a6_expired_check_requires_recheck(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "school_admin01")
    create = client.post(f"{BASE}/class-adjustment-requests", headers=hdr, json={
        "adjustType": "DISBAND", "fromClassIds": [str(ids["cEmpty"])], "reason": "过期核对测试用例"}).json()["data"]
    aid = create["id"]
    client.post(f"{BASE}/class-adjustment-requests/{aid}/precheck", headers=hdr)
    from app.db.session import get_sessionmaker
    from app.models import AaClassAdjustmentRequest
    db = get_sessionmaker()()
    row = db.get(AaClassAdjustmentRequest, int(aid))
    row.checked_at = datetime.utcnow() - timedelta(hours=25)
    db.commit()
    db.close()
    r = client.post(f"{BASE}/class-adjustment-requests/{aid}/execute", headers=hdr)
    assert r.status_code == 409


def test_a7_cancel_before_execute(client, db_mode):
    ids = _seed_scoped(db_mode)
    hdr = _hdr(client, "school_admin01")
    create = client.post(f"{BASE}/class-adjustment-requests", headers=hdr, json={
        "adjustType": "MERGE", "fromClassIds": [str(ids["c2"])], "toClassId": str(ids["c1"]),
        "reason": "先发起后又想撤销"}).json()["data"]
    aid = create["id"]
    cancelled = client.post(f"{BASE}/class-adjustment-requests/{aid}/cancel", headers=hdr).json()["data"]
    assert cancelled["status"] == "CANCELLED"
    r_exec = client.post(f"{BASE}/class-adjustment-requests/{aid}/execute", headers=hdr)
    assert r_exec.status_code == 409
