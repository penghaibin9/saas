"""校历节次 Tier1 R2 · 端到端（本文件仅供本智能体自测，SQLite 隔离，不连共享 MySQL 测试库）：
节假日配置/补课日配置（t_aa_calendar_event HOLIDAY/SWAP）+ 节次管理（t_aa_time_slot 编辑/停用/删除）+
上课时间段（新表 t_aa_class_time_band）+ 教学周日历（派生聚合）+ 校历发布（校验门禁+锁定）+ 校历归档。

运行方式：
    cd backend && TEST_DATABASE_URL=sqlite:///./diag_aa_calperiod.db \
        .venv/Scripts/python.exe -m pytest tests/test_aa_calendar_period.py -q
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _term(client, hdr, year="2027-2028", no=1):
    return client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": year, "termNo": no, "termName": f"{year}第{no}学期",
        "startDate": "2027-09-01", "endDate": "2028-01-15", "teachingWeeks": 4, "examWeekStart": 4})


def test_r1_holiday_crud(client, db_mode):
    """节假日配置：新建/列表按 eventType 过滤/编辑/删除。"""
    hdr = _hdr(client, "school_admin01")
    tid = _term(client, hdr).json()["data"]["termId"]
    r = client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={
        "eventType": "HOLIDAY", "startDate": "2027-10-01", "endDate": "2027-10-07", "remark": "国庆"})
    assert r.status_code == 200
    event_id = r.json()["data"]["eventId"]
    items = client.get(f"{BASE}/terms/{tid}/calendar", headers=hdr, params={"eventType": "HOLIDAY"}).json()["data"]["items"]
    assert len(items) == 1 and items[0]["eventType"] == "HOLIDAY"
    up = client.put(f"{BASE}/terms/{tid}/calendar/{event_id}", headers=hdr, json={"remark": "国庆节假期"})
    assert up.status_code == 200 and up.json()["data"]["remark"] == "国庆节假期"
    de = client.delete(f"{BASE}/terms/{tid}/calendar/{event_id}", headers=hdr)
    assert de.status_code == 200
    items2 = client.get(f"{BASE}/terms/{tid}/calendar", headers=hdr, params={"eventType": "HOLIDAY"}).json()["data"]["items"]
    assert len(items2) == 0


def test_r2_makeup_day_pairing_validation(client, db_mode):
    """补课日配置：必须成对（缺 swapToDate 400），越界日期 400。"""
    hdr = _hdr(client, "school_admin01")
    tid = _term(client, hdr, "2027-2028", 2).json()["data"]["termId"]
    bad = client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={
        "eventType": "SWAP", "startDate": "2027-10-08"})
    assert bad.status_code == 400
    out_of_range = client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={
        "eventType": "SWAP", "startDate": "2020-01-01", "swapToDate": "2020-01-05"})
    assert out_of_range.status_code == 400
    ok = client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={
        "eventType": "SWAP", "startDate": "2027-10-08", "swapToDate": "2027-10-11", "remark": "国庆调休"})
    assert ok.status_code == 200 and ok.json()["data"]["swapToDate"] == "2027-10-11T00:00:00"


def test_r3_period_management_crud_and_dup(client, db_mode):
    """节次管理：创建去重(409)/编辑/停用/删除，含 includeDisabled 列表。"""
    hdr = _hdr(client, "school_admin01")
    r1 = client.post(f"{BASE}/time-slots", headers=hdr, json={"slotNo": 21, "slotName": "第21节", "startTime": "08:00", "endTime": "08:45"})
    assert r1.status_code == 200
    slot_id = r1.json()["data"]["slotId"]
    dup = client.post(f"{BASE}/time-slots", headers=hdr, json={"slotNo": 21})
    assert dup.status_code == 409
    # 时间重叠须拦截（与序号去重并列的异常门禁）
    overlap = client.post(f"{BASE}/time-slots", headers=hdr, json={
        "slotNo": 211, "slotName": "重叠节", "startTime": "08:10", "endTime": "08:50"})
    assert overlap.status_code == 409, overlap.text
    upd = client.put(f"{BASE}/time-slots/{slot_id}", headers=hdr, json={"slotName": "早读", "enabled": False})
    assert upd.status_code == 200 and upd.json()["data"]["enabled"] is False and upd.json()["data"]["status"] == "DISABLED"
    visible = client.get(f"{BASE}/time-slots", headers=hdr).json()["data"]["items"]
    assert not any(s["slotId"] == slot_id for s in visible)  # 停用后默认列表不可见
    all_visible = client.get(f"{BASE}/time-slots", headers=hdr, params={"includeDisabled": True}).json()["data"]["items"]
    assert any(s["slotId"] == slot_id for s in all_visible)
    de = client.delete(f"{BASE}/time-slots/{slot_id}", headers=hdr)
    assert de.status_code == 200
    all_after = client.get(f"{BASE}/time-slots", headers=hdr, params={"includeDisabled": True}).json()["data"]["items"]
    assert not any(s["slotId"] == slot_id for s in all_after)


def test_r4_class_time_band_crud(client, db_mode):
    """上课时间段：新表 CRUD + 时间格式/先后校验。"""
    hdr = _hdr(client, "school_admin01")
    slot_id = client.post(f"{BASE}/time-slots", headers=hdr, json={"slotNo": 22, "slotName": "第22节"}).json()["data"]["slotId"]
    bad = client.post(f"{BASE}/time-slots/{slot_id}/time-bands", headers=hdr, json={"startTime": "09:00", "endTime": "08:00"})
    assert bad.status_code == 400
    ok = client.post(f"{BASE}/time-slots/{slot_id}/time-bands", headers=hdr, json={
        "bandName": "夏季作息", "startTime": "08:00", "endTime": "08:45"})
    assert ok.status_code == 200
    band_id = ok.json()["data"]["bandId"]
    items = client.get(f"{BASE}/time-slots/{slot_id}/time-bands", headers=hdr).json()["data"]["items"]
    assert len(items) == 1 and items[0]["bandName"] == "夏季作息"
    upd = client.put(f"{BASE}/time-bands/{band_id}", headers=hdr, json={"endTime": "08:50"})
    assert upd.status_code == 200 and upd.json()["data"]["endTime"] == "08:50"
    de = client.delete(f"{BASE}/time-bands/{band_id}", headers=hdr)
    assert de.status_code == 200
    items2 = client.get(f"{BASE}/time-slots/{slot_id}/time-bands", headers=hdr).json()["data"]["items"]
    assert len(items2) == 0


def test_r5_week_calendar_aggregate(client, db_mode):
    """教学周日历：按学期起止+教学周数派生，叠加节假日/考试周着色。"""
    hdr = _hdr(client, "school_admin01")
    tid = _term(client, hdr, "2028-2029", 1).json()["data"]["termId"]
    # 学期 4 教学周，起于 2027-09-01：第1周=09-01~09-07。假期落在第1周内以验证着色叠加。
    client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={
        "eventType": "HOLIDAY", "startDate": "2027-09-02", "endDate": "2027-09-03", "remark": "校庆假"})
    wc = client.get(f"{BASE}/terms/{tid}/week-calendar", headers=hdr)
    assert wc.status_code == 200
    weeks = wc.json()["data"]["weeks"]
    assert len(weeks) == 4
    assert weeks[0]["weekType"] == "HOLIDAY" and len(weeks[0]["holidays"]) == 1
    assert weeks[-1]["weekType"] == "EXAM"  # examWeekStart=4，第4周（最后一周）应为 EXAM


def test_r6_publish_calendar_gate_and_lock(client, db_mode):
    """校历发布：无节次时 400；补全后可发布；发布后再写日历事件 409（锁定）。"""
    hdr = _hdr(client, "school_admin01")
    tid = _term(client, hdr, "2029-2030", 1).json()["data"]["termId"]
    no_slot = client.post(f"{BASE}/terms/{tid}/calendar/publish", headers=hdr)
    assert no_slot.status_code == 400  # 无任何 ENABLED 节次时门禁失败
    client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={"eventType": "TEACHING", "startDate": "2027-09-01"})
    client.post(f"{BASE}/time-slots", headers=hdr, json={"slotNo": 23})
    pub = client.post(f"{BASE}/terms/{tid}/calendar/publish", headers=hdr)
    assert pub.status_code == 200 and pub.json()["data"]["status"] == "PUBLISHED"
    locked = client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={"eventType": "HOLIDAY", "startDate": "2027-09-10"})
    assert locked.status_code == 409


def test_r7_term_detail_readonly(client, db_mode):
    """学期详情只读端点：返回真实状态；不提供直写归档的 POST /archive（归档统一走教务归档模块批次流程，
    见总控合并复核——原 archive_term 直写 AaTerm.status 绕开批次+9域完整性检查且无法撤销，已移除）。"""
    hdr = _hdr(client, "school_admin01")
    tid = _term(client, hdr, "2030-2031", 1).json()["data"]["termId"]
    detail = client.get(f"{BASE}/terms/{tid}", headers=hdr)
    assert detail.status_code == 200 and detail.json()["data"]["status"] == "DRAFT"
    assert client.post(f"{BASE}/terms/{tid}/archive", headers=hdr).status_code == 404  # 端点已移除


def test_r7b_teacher_role_forbidden_publish(client, db_mode):
    """任课教师（ACADEMIC_TEACHER）有 academicAffairs.* 通配权限，但不在超高危角色白名单 → 发布 403。"""
    admin_hdr = _hdr(client, "school_admin01")
    tid = _term(client, admin_hdr, "2031-2032", 2).json()["data"]["termId"]
    client.post(f"{BASE}/time-slots", headers=admin_hdr, json={"slotNo": 25})
    teacher_hdr = _hdr(client, "academic01")
    pub = client.post(f"{BASE}/terms/{tid}/calendar/publish", headers=teacher_hdr)
    assert pub.status_code == 403


def test_r8_student_forbidden_403(client, db_mode):
    """越权红线：学生令牌打新端点一律 403。"""
    hdr = _hdr(client, "student01")
    tid = _term(client, _hdr(client, "school_admin01"), "2032-2033", 1).json()["data"]["termId"]
    assert client.get(f"{BASE}/terms/{tid}/calendar", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/terms/{tid}/calendar", headers=hdr, json={"eventType": "HOLIDAY", "startDate": "2027-09-10"}).status_code == 403
    assert client.get(f"{BASE}/terms/{tid}/week-calendar", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/terms/{tid}/calendar/publish", headers=hdr).status_code == 403
    assert client.post(f"{BASE}/time-slots", headers=hdr, json={"slotNo": 1}).status_code == 403
    assert client.get(f"{BASE}/time-slots/1/time-bands", headers=hdr).status_code == 403
