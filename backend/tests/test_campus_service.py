"""在校服务域测试：台账/资助/宿舍异常/违纪/工单闭环 + 历史请假只读数据 + 审计 + 看板。"""
from __future__ import annotations

from datetime import datetime

MAIN_TID = 1000000000000000001
LEGACY_LEAVE_API = "/api/v1/campus-service/" + "leaves"


def _seed(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import CsDormException, CsGrant, CsLeave, CsServiceStudent, CsWorkOrder
    db = get_sessionmaker()()
    try:
        s = CsServiceStudent(tenant_id=MAIN_TID, name="服务生甲", student_no="2024999001",
                             class_id="CL01", class_name="软件2401班", care_level="FOCUS",
                             risk_level="HIGH", building="B3", room="301-1", counselor="李辅导",
                             phone_encrypted="13900008888")
        db.add(s)
        db.flush()
        lv = CsLeave(tenant_id=MAIN_TID, code="LV-T-1", cs_student_id=s.id, leave_type="SICK",
                     start_time=datetime.utcnow(), duration="2 天", reason="就医",
                     status="PENDING_REVIEW", apply_time=datetime.utcnow())
        gr = CsGrant(tenant_id=MAIN_TID, code="GR-T-1", cs_student_id=s.id, grant_type="NATIONAL_GRANT",
                     amount=3300, apply_reason="困难", material_sensitive=True, status="REVIEWING",
                     apply_time=datetime.utcnow())
        de = CsDormException(tenant_id=MAIN_TID, code="DE-T-1", cs_student_id=s.id, exc_type="NIGHT_OUT",
                             happen_time=datetime.utcnow(), detail="晚归超时", status="PENDING_HANDLE")
        wo = CsWorkOrder(tenant_id=MAIN_TID, code="WO-T-1", cs_student_id=s.id, title="开在读证明",
                         wo_type="CERT", priority="MEDIUM", status="PENDING_HANDLE")
        db.add_all([lv, gr, de, wo])
        db.commit()
        return {"student": s.id, "leave": lv.id, "grant": gr.id, "de": de.id, "wo": wo.id}
    finally:
        db.close()


def test_students_and_detail(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/campus-service/students", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1
    assert lst["data"]["items"][0]["careLevelLabel"] == "重点关注"
    det = client.get(f"/api/v1/campus-service/students/{ids['student']}", headers=auth_headers).json()
    assert det["code"] == 0 and len(det["data"]["leaves"]) == 1 and len(det["data"]["workOrders"]) == 1


def test_void_student(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/campus-service/students/{ids['student']}/void", headers=auth_headers,
                      json={"reason": "x"}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/campus-service/students/{ids['student']}/void", headers=auth_headers,
                     json={"reason": "重复台账予以作废"}).json()
    assert ok["code"] == 0


def test_legacy_leave_routes_retired(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    assert client.get(LEGACY_LEAVE_API, headers=auth_headers).status_code == 404
    assert client.post(
        f"{LEGACY_LEAVE_API}/{ids['leave']}/approve",
        headers=auth_headers,
        json={"comment": "同意", "version": 0},
    ).status_code == 404


def test_grant_masked_and_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    lst = client.get("/api/v1/campus-service/grants", headers=auth_headers).json()
    # 列表脱敏：无 amount，仅 amountRange
    assert lst["code"] == 0 and "amount" not in lst["data"]["items"][0]
    assert lst["data"]["items"][0]["amountRange"] != ""
    det = client.get(f"/api/v1/campus-service/grants/{ids['grant']}", headers=auth_headers).json()
    assert det["data"]["grant"]["amount"] == 3300  # 详情可见真实金额
    ok = client.post(f"/api/v1/campus-service/grants/{ids['grant']}/approve", headers=auth_headers,
                     json={"version": det["data"]["grant"]["version"]}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "APPROVED"


def test_dorm_exception_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    bad = client.post(f"/api/v1/campus-service/dorm-exceptions/{ids['de']}/handle", headers=auth_headers,
                      json={"note": "x", "complete": True, "version": 0}).json()
    assert bad["code"] == 422001
    ok = client.post(f"/api/v1/campus-service/dorm-exceptions/{ids['de']}/handle", headers=auth_headers,
                     json={"note": "已联系家长核实并教育", "complete": True, "version": 0}).json()
    assert ok["code"] == 0 and ok["data"]["status"] == "COMPLETED"
    # 新标记异常
    mk = client.post("/api/v1/campus-service/dorm-exceptions", headers=auth_headers,
                     json={"studentId": str(ids["student"]), "type": "HYGIENE", "detail": "宿舍卫生不合格需整改"}).json()
    assert mk["code"] == 0


def test_discipline_legacy_write_retired(client, auth_headers, db_mode):
    """旧版违纪直接编辑入口已下线（甲方拍板保留新版流程）：create/update/void 三个写操作
    一律 DATA_CONFLICT；existing 存量数据仍可通过 list 只读查询，不受影响。"""
    ids = _seed(db_mode)
    from app.db.session import get_sessionmaker
    from app.models import CsDiscipline
    db = get_sessionmaker()()
    d = CsDiscipline(tenant_id=MAIN_TID, code="DIS-T-1", cs_student_id=ids["student"],
                     disc_type="WARNING", reason="历史存量处分记录", status="EFFECTIVE",
                     record_status="ACTIVE")
    db.add(d); db.commit()
    did = d.id
    db.close()

    lst = client.get("/api/v1/campus-service/disciplines", headers=auth_headers).json()
    assert lst["code"] == 0 and lst["data"]["total"] == 1

    c = client.post("/api/v1/campus-service/disciplines", headers=auth_headers,
                    json={"studentId": str(ids["student"]), "type": "WARNING",
                          "reason": "违反宿舍管理规定给予警告"}).json()
    assert c["code"] != 0 and c["bizCode"] == "DATA_CONFLICT"
    u = client.put(f"/api/v1/campus-service/disciplines/{did}", headers=auth_headers,
                   json={"status": "REVOKED"}).json()
    assert u["code"] != 0 and u["bizCode"] == "DATA_CONFLICT"
    v = client.post(f"/api/v1/campus-service/disciplines/{did}/void", headers=auth_headers,
                    json={"reason": "处分决定撤销"}).json()
    assert v["code"] != 0 and v["bizCode"] == "DATA_CONFLICT"


def test_work_order_closed_loop(client, auth_headers, db_mode):
    ids = _seed(db_mode)
    asg = client.post("/api/v1/campus-service/work-orders/assign", headers=auth_headers,
                      json={"ids": [str(ids["wo"])], "handler": "王学工"}).json()
    assert asg["code"] == 0 and asg["data"]["count"] == 1
    h = client.post(f"/api/v1/campus-service/work-orders/{ids['wo']}/handle", headers=auth_headers,
                    json={"note": "已开具证明并交付学生", "close": True, "version": 0}).json()
    assert h["code"] == 0 and h["data"]["status"] == "COMPLETED"
    det = client.get(f"/api/v1/campus-service/work-orders/{ids['wo']}", headers=auth_headers).json()
    assert det["code"] == 0 and len(det["data"]["order"]["trail"]) >= 1


def test_dashboard_mental_audit(client, auth_headers, db_mode):
    _seed(db_mode)
    dash = client.get("/api/v1/campus-service/dashboard", headers=auth_headers).json()
    assert dash["code"] == 0 and any(k["key"] == "students" for k in dash["data"]["kpis"])
    # 查看心理记录会写涉密审计
    client.get("/api/v1/campus-service/mental-records", headers=auth_headers)
    audit = client.get("/api/v1/campus-service/audit-logs?bizType=MENTAL", headers=auth_headers).json()
    assert audit["code"] == 0 and audit["data"]["total"] >= 1


def test_requires_login(client):
    assert client.get("/api/v1/campus-service/dashboard").json()["code"] == 401001


def _hdr(client, login):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_sec6_non_authorized_denied(client, db_mode):
    """SEC-6 回归：旧在校服务面已由 get_current_user 收紧到 campusService.* 细粒度权限。
    ① 学生令牌不再可达（原 get_current_user 只认证不鉴别身份，学生可读全校处分/资助）；
    ② 无 campusService.* 授权的教职工（就业老师）同样 403——对齐登记的越权实证。"""
    # ① 学生 → 403（PC 管理端一律拒学生）
    r_stu = client.get("/api/v1/campus-service/disciplines", headers=_hdr(client, "student01"))
    assert r_stu.status_code == 403
    # ② 就业老师（EMPLOYMENT_TEACHER，无 campusService.*）读资助 → 403（原实证为 200 越权）
    r_emp = client.get("/api/v1/campus-service/grants", headers=_hdr(client, "employment01"))
    assert r_emp.status_code == 403
    assert r_emp.json()["bizCode"] == "NO_PERMISSION"
    # ③ 学工处管理员正常放行（授权路径未误伤）
    r_ok = client.get("/api/v1/campus-service/grants", headers=_hdr(client, "sa_admin01"))
    assert r_ok.status_code == 200 and r_ok.json()["code"] == 0
