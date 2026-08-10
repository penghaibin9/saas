"""13A-P1 瀛﹀伐棣栭〉 + 鐝骇/鐝共閮ㄩ鏋?路 绔埌绔紙鐪熷疄 DB 妯″紡锛夈€?

瑕嗙洊锛氫笁瑙掕壊瑙嗗浘宸紓 + scope 宸紓锛?3 妯″潡鍗＄┖鎬侊紱鐝骇鍒楄〃鑼冨洿杩囨护锛?
鐝共閮ㄤ换鍛?鍒楄〃锛涜緟瀵煎憳璺ㄧ彮璁块棶 403锛堣秺鏉?鑷姩瀹¤锛夛紱閲嶅浠诲懡 409銆?
"""
from __future__ import annotations

TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_classes(db_mode):
    """鍦?db_mode 涔嬩笂琛ョ 2 鐝?+ 5 鐢燂紝骞惰繑鍥炵湡瀹炲鐢熶富閿€?""
    from app.db.session import get_sessionmaker
    from app.models import SchoolClass, StudentProfile, TeacherStudentScope
    db = get_sessionmaker()()
    a = SchoolClass(tenant_id=TID, major_id=1, class_name="杞欢2101", grade="2021", status="ACTIVE")
    b = SchoolClass(tenant_id=TID, major_id=1, class_name="杞欢2102", grade="2021", status="ACTIVE")
    db.add_all([a, b])
    db.flush()
    students_a = []
    students_b = []
    for i in range(3):
        row = StudentProfile(
            tenant_id=TID, student_no=f"A{i:03d}", real_name=f"鐢瞷i}",
            class_id=a.id, current_stage="ORIENTATION",
            student_status="NORMAL", status="ACTIVE",
        )
        db.add(row)
        students_a.append(row)
    for i in range(2):
        row = StudentProfile(
            tenant_id=TID, student_no=f"B{i:03d}", real_name=f"涔檣i}",
            class_id=b.id, current_stage="ORIENTATION",
            student_status="NORMAL", status="ACTIVE",
        )
        db.add(row)
        students_b.append(row)
    db.flush()
    db.add(TeacherStudentScope(
        tenant_id=TID, teacher_key="counselor01", teacher_name="鐜嬭帀",
        role_code="COUNSELOR", scope_type="CLASS", ref_value="杞欢2101",
        status="ACTIVE",
    ))
    db.commit()
    ids = {
        "A": a.id, "B": b.id,
        "A_STUDENT": students_a[0].id, "B_STUDENT": students_b[0].id,
    }
    db.close()
    return ids

def test_dashboard_three_role_views(client, db_mode):
    _seed_classes(db_mode)
    # 瀛﹀伐澶勶細鍏ㄦ牎瑙嗗浘 + ADMIN_TENANT
    r = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "school_admin01")).json()
    assert r["code"] == 0
    assert r["data"]["view"] == "SA_ADMIN"
    assert r["data"]["scopeMode"] == "ADMIN_TENANT"
    assert len(r["data"]["moduleCards"]) == 13
    # 棣栭〉鍗￠殢闃舵鐐逛寒锛歅1-P8 鍚?psy/activity 宸?LIVE
    _live = {"class", "leave", "aid", "funding", "discipline", "risk", "talk", "family", "profile",
             "dorm", "archive", "psy", "activity"}
    assert {m["key"] for m in r["data"]["moduleCards"] if m["status"] == "LIVE"} == _live
    assert all(m["status"] == "LIVE" for m in r["data"]["moduleCards"])
    assert not any(m.get("status") == "PENDING" for m in r["data"]["moduleCards"])

    # 瀛﹂櫌瀛﹀伐锛氭湰闄㈣鍥?
    r2 = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "college_admin01")).json()
    assert r2["data"]["view"] == "COLLEGE_SA"

    # 杈呭鍛橈細鏈彮瑙嗗浘 + SCOPED锛屽鐢熸暟=A 鐝?3 浜?
    r3 = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "counselor01")).json()
    assert r3["data"]["view"] == "COUNSELOR"
    assert r3["data"]["scopeMode"] == "SCOPED"
    stu = next(c["value"] for c in r3["data"]["summaryCards"] if c["key"] == "studentTotal")
    assert stu == 3


def test_class_scope_filter(client, db_mode):
    ids = _seed_classes(db_mode)
    # 瀛﹀伐澶勮 2 涓彮
    r = client.get("/api/v1/student-affairs/classes", headers=_hdr(client, "school_admin01")).json()
    assert r["code"] == 0 and len(r["data"]["items"]) == 2
    # 杈呭鍛樺彧瑙?A 鐝?
    r2 = client.get("/api/v1/student-affairs/classes", headers=_hdr(client, "counselor01")).json()
    assert len(r2["data"]["items"]) == 1
    assert r2["data"]["items"][0]["classId"] == str(ids["A"])


def test_cadre_appoint_and_list(client, db_mode):
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    body = {"studentId": str(ids["A_STUDENT"]), "position": "MONITOR", "termCode": "2026-1"}
    r = client.post(f"/api/v1/student-affairs/classes/{ids['A']}/cadres", json=body, headers=hdr).json()
    assert r["code"] == 0 and r["data"]["position"] == "MONITOR"
    # 鍘嗗彶娆犺处锛氫换鍛?鍒楄〃椤诲甫瀛︾敓濮撳悕+瀛﹀彿锛堟鍓嶅彧鍥?studentId 鍐呴儴涓婚敭锛夈€俰d=1 涓哄熀纭€绉嶅瓙瀛︾敓璧典竴鍑°€?
    assert r["data"]["studentName"] == "鐢?" and r["data"]["studentNo"] == "A000"
    # 鍒楄〃鍙 + 甯﹀鍚嶅鍙?
    r2 = client.get(f"/api/v1/student-affairs/classes/{ids['A']}/cadres", headers=hdr).json()
    assert len(r2["data"]["items"]) == 1
    assert r2["data"]["items"][0]["studentName"] == "鐢?"
    assert r2["data"]["items"][0]["studentNo"] == "A000"
    # 鍚岀彮鍚岃亴鍔￠噸澶嶄换鍛?鈫?409
    r3 = client.post(f"/api/v1/student-affairs/classes/{ids['A']}/cadres", json=body, headers=hdr)
    assert r3.status_code == 409


def test_counselor_cross_class_403(client, db_mode):
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "counselor01")
    # 杈呭鍛樿闂笉鍦ㄨ寖鍥寸殑 B 鐝彮骞查儴 鈫?403锛圢O_DATA_SCOPE + 鑷姩瀹¤锛?
    r = client.get(f"/api/v1/student-affairs/classes/{ids['B']}/cadres", headers=hdr)
    assert r.status_code == 403
    assert r.json()["bizCode"] == "NO_DATA_SCOPE"
    # 瓒婃潈浠诲懡鍚屾牱琚嫆
    r2 = client.post(f"/api/v1/student-affairs/classes/{ids['B']}/cadres",
                     json={"studentId": "1", "position": "MONITOR"}, headers=hdr)
    assert r2.status_code == 403


def test_school_admin_any_class(client, db_mode):
    ids = _seed_classes(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 瀛﹀伐澶勫彲瀵逛换鎰忕彮浠诲懡
    r = client.post(f"/api/v1/student-affairs/classes/{ids['B']}/cadres",
                    json={"studentId": str(ids["B_STUDENT"]), "position": "STUDY"}, headers=hdr)
    assert r.json()["code"] == 0


def test_dashboard_todo_scoped_to_assignee(client, db_mode):
    """杈呭鍛樺緟鍔炴寜缁熶竴寰呭姙鍙鎬э細浠呮湰鐝睜寰呭姙 + 鏈汉鎸囨淳锛涚湅涓嶅埌浠栫彮姹犲緟鍔炰笌浠栦汉鎸囨淳銆?

    mock 浠ょ墝 userId=u_<鏁板瓧>锛屼笌 workbench_todo_service._uid 瑙ｆ瀽涓€鑷淬€?
    """
    ids = _seed_classes(db_mode)
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, UnifiedTodo
    CA_UID, OTHER_UID = 61001, 61002
    db = get_sessionmaker()()
    sa = db.query(StudentProfile).filter_by(class_id=ids["A"]).first()
    sb = db.query(StudentProfile).filter_by(class_id=ids["B"]).first()
    assert sa and sb
    db.add(UnifiedTodo(
        tenant_id=TID, source_module="student-affairs", source_biz_type="LEAVE",
        source_biz_id=9101, todo_type="LEAVE_APPROVAL", assignee_id=0,
        student_id=sa.id, title="鏈彮姹犲緟鍔?, status="PENDING"))
    db.add(UnifiedTodo(
        tenant_id=TID, source_module="student-affairs", source_biz_type="LEAVE",
        source_biz_id=9102, todo_type="LEAVE_APPROVAL", assignee_id=0,
        student_id=sb.id, title="浠栫彮姹犲緟鍔?, status="PENDING"))
    db.add(UnifiedTodo(
        tenant_id=TID, source_module="student-affairs", source_biz_type="LEAVE",
        source_biz_id=9103, todo_type="LEAVE_APPROVAL", assignee_id=OTHER_UID,
        student_id=sa.id, title="浠栦汉鎸囨淳寰呭姙", status="PENDING"))
    db.add(UnifiedTodo(
        tenant_id=TID, source_module="student-affairs", source_biz_type="RISK",
        source_biz_id=9104, todo_type="RISK_HANDLE", assignee_id=CA_UID,
        student_id=sb.id, title="鏈汉鎸囨淳寰呭姙", status="PENDING"))
    db.commit()
    db.close()

    token = create_access_token({
        "userId": f"u_{CA_UID}", "loginName": "counselor01", "realName": "鐜嬭帀",
        "userType": "TEACHER", "tid": "demo", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "COUNSELOR", "clientType": "PC"})
    hdr = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/student-affairs/dashboard", headers=hdr).json()
    assert r["code"] == 0
    todo = next(c["value"] for c in r["data"]["summaryCards"] if c["key"] == "pendingTodo")
    # 鏈彮姹?1 + 鏈汉鎸囨淳 1锛涗粬鐝睜涓庝粬浜烘寚娲句笉鍙
    assert todo == 2
    assert r["data"]["scopeLabel"] in ("鏈汉璐熻矗鑼冨洿", "鍏ㄦ牎", "鏈櫌", "鏃犳暟鎹寖鍥?)
    keys = {c["key"] for c in r["data"]["summaryCards"]}
    assert "dormException" not in keys
    assert "overdueLeave" in keys
    card = next(c for c in r["data"]["summaryCards"] if c["key"] == "pendingLeave")
    assert card.get("drillPath") == "/admin/student-affairs/leave"


def test_dashboard_admin_scope_label_schoolwide(client, db_mode):
    _seed_classes(db_mode)
    r = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "school_admin01")).json()
    assert r["data"]["scopeLabel"] == "鍏ㄦ牎"
    assert r["data"]["scopeMode"] == "ADMIN_TENANT"
    # 瀛﹀伐绠＄悊鍛樺彲瑙佸叏鏍℃睜寰呭姙鍙ｅ緞锛歝onftest 绉嶅瓙閲屾棤 assignee_id=0 鐨?PENDING锛?
    # 鍙︽湁 assignee_id=1 鐨勪釜浜哄緟鍔炩€斺€攎ock 绠＄悊鍛?uid 涓嶅彲瑙ｆ瀽鏃跺彧璁℃睜寰呭姙锛屼笉寰楀洖閫€鍏ㄩ噺 PENDING
    todo = next(c["value"] for c in r["data"]["summaryCards"] if c["key"] == "pendingTodo")
    assert todo == 1


def test_dashboard_top_risk_level_critical_single_student(client, db_mode):
    """鍗充娇鍙湁 1 鍚嶅嵄鎬ラ闄╁鐢燂紝topRiskLevel 涔熷繀椤绘槸 CRITICAL锛堢姝㈢敤浜烘暟>10 鎺ㄦ柇锛夈€?""
    ids = _seed_classes(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord, StudentProfile
    db = get_sessionmaker()()
    sa = db.query(StudentProfile).filter_by(class_id=ids["A"]).first()
    assert sa
    db.add(AffairsRiskRecord(
        tenant_id=TID, student_id=sa.id, source="MANUAL", risk_level="CRITICAL",
        title="鍗辨€ヤ竴浜?, detail="鍗曚汉鍗辨€?, status="NEW"))
    db.commit(); db.close()
    r = client.get("/api/v1/student-affairs/dashboard", headers=_hdr(client, "school_admin01")).json()
    assert r["code"] == 0
    rs = r["data"]["riskSummary"]
    assert rs["openStudentCount"] == 1
    assert rs["criticalCount"] == 1
    assert rs["topRiskLevel"] == "CRITICAL"
    card = next(c for c in r["data"]["summaryCards"] if c["key"] == "riskStudents")
    assert card["value"] == 1 and card["topRiskLevel"] == "CRITICAL"

