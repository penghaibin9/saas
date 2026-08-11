"""排课管理 Tier1 R2 续工端点测试（03排课约束/05教室可用时间/07自动排课预留/10排课结果/11排课调整/13排课归档）。

复用既有课表批次/条目与冲突报告。当前生产合同要求排课坐标必须来自真实 AaTerm、已启用 AaTimeSlot，
且手工/导入排课必须落到同学期 APPROVED 教学任务批次中的 READY 教学任务；本文件不再使用伪 termId、
旧规则键或 free-text 教学任务绕过这些生产门禁。导入默认 atomic=True，任一冲突整批回滚。
"""
from __future__ import annotations

import io

from openpyxl import Workbook

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _ensure_term():
    from app.db.session import get_sessionmaker
    from app.models import AaTerm, AaTimeSlot

    db = get_sessionmaker()()
    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == TID,
        AaTerm.year_code == "2026-2027",
        AaTerm.term_no == 1,
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        term = AaTerm(
            tenant_id=TID,
            year_code="2026-2027",
            term_no=1,
            term_name="2026-2027第1学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=True,
        )
        db.add(term)
        db.flush()
    else:
        term.status = "PUBLISHED"
        term.is_current = True
        term.teaching_weeks = int(term.teaching_weeks or 18)

    existing = {
        int(row.slot_no): row for row in db.query(AaTimeSlot).filter(
            AaTimeSlot.tenant_id == TID,
            AaTimeSlot.is_deleted.is_(False),
        ).all()
    }
    for slot_no in range(1, 9):
        row = existing.get(slot_no)
        if row:
            row.enabled = True
            row.status = "ENABLED"
        else:
            db.add(AaTimeSlot(
                tenant_id=TID,
                slot_no=slot_no,
                slot_name=f"第{slot_no}节",
                enabled=True,
                status="ENABLED",
            ))
    term_id = int(term.id)
    db.commit()
    db.close()
    return term_id


def _batch(client, hdr, term_id=None):
    term_id = int(term_id or _ensure_term())
    response = client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": str(term_id)})
    assert response.status_code == 200, response.text
    return response.json()["data"]["batchId"]


def _seed_ready_task(term_id, *, teacher_key="T1", teacher_name="王老师",
                     course_name="高数", weekly_hours=1, code_suffix=""):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch

    db = get_sessionmaker()()
    suffix = str(code_suffix or f"{teacher_key}-{course_name}")
    safe = "".join(ch for ch in suffix if ch.isalnum())[-24:] or "X"
    course = AaCourse(
        tenant_id=TID,
        course_code=f"SC{int(term_id)}{safe}"[:50],
        course_name=course_name,
        credit=4,
        status="ENABLED",
    )
    db.add(course); db.flush()
    tb = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=int(term_id),
        batch_name=f"{course_name}任务批次",
        status="APPROVED",
    )
    db.add(tb); db.flush()
    task = AaTeachingTask(
        tenant_id=TID,
        batch_id=tb.id,
        course_id=course.id,
        course_code=course.course_code,
        course_name=course.course_name,
        teacher_key=teacher_key,
        teacher_name=teacher_name,
        weekly_hours=weekly_hours,
        start_week=1,
        end_week=18,
        status="READY",
    )
    db.add(task); db.flush()
    ids = {"taskBatch": tb.id, "task": task.id, "course": course.id}
    db.commit()
    db.close()
    return ids


def _schedule_term_id(batch_id):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch

    db = get_sessionmaker()()
    batch = db.get(AaScheduleBatch, int(batch_id))
    assert batch is not None
    term_id = int(batch.term_id)
    db.close()
    return term_id


def _item(client, hdr, bid, **kw):
    task_id = kw.pop("taskId", None)
    teacher_key = str(kw.pop("teacherKey", "T1"))
    teacher_name = str(kw.pop("teacherName", "王老师"))
    course_name = str(kw.pop("courseName", "高数"))
    if not task_id:
        seeded = _seed_ready_task(
            _schedule_term_id(bid),
            teacher_key=teacher_key,
            teacher_name=teacher_name,
            course_name=course_name,
            code_suffix=f"{bid}-{teacher_key}-{course_name}-{kw.get('weekday', 1)}-{kw.get('slotNo', 1)}",
        )
        task_id = str(seeded["task"])
    body = {
        "taskId": str(task_id),
        "weekday": 1,
        "slotNo": 1,
        "startWeek": 1,
        "endWeek": 18,
        "weekParity": "ALL",
        "classroom": "A101",
        **kw,
    }
    return client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json=body)


def test_03_constraint_reuses_rule_center(client, db_mode):
    admin = _hdr(client, "school_admin01")
    term_id = _ensure_term()
    r = client.put(f"{BASE}/scheduling/rules", headers=admin,
                   json={"ruleKey": "AUTO_TEACHER_MAX_PER_DAY", "termId": str(term_id), "ruleValue": 8}).json()
    assert r["code"] == 0 and r["data"]["ruleKey"] == "AUTO_TEACHER_MAX_PER_DAY"
    lst = client.get(f"{BASE}/scheduling/rules", headers=admin, params={"termId": str(term_id)}).json()
    assert any(x["ruleKey"] == "AUTO_TEACHER_MAX_PER_DAY" for x in lst["data"]["items"])


def test_05_room_view_hit_and_empty(client, db_mode):
    admin = _hdr(client, "school_admin01")
    bid = _batch(client, admin)
    assert _item(client, admin, bid, classroom="A101").status_code == 200
    hit = client.get(f"{BASE}/schedule-batches/{bid}/room-view", headers=admin, params={"classroom": "A101"}).json()
    assert hit["code"] == 0 and len(hit["data"]["items"]) == 1
    empty = client.get(f"{BASE}/schedule-batches/{bid}/room-view", headers=admin, params={"classroom": "Z999"}).json()
    assert empty["code"] == 0 and empty["data"]["items"] == [] and "暂无排课" in empty["data"]["note"]


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "导入模板"
    ws.append(["星期(1-7)", "节次", "课程名称", "教师姓名", "教师工号", "班级ID", "班级名称",
              "教室", "起始周", "结束周", "单双周(ALL/ODD/EVEN)", "教学任务ID"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_07_import_template_download(client, db_mode):
    admin = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/schedule-batches/import/template", headers=admin)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(r.content) > 0


def test_07_import_xlsx_success_and_conflict(client, db_mode):
    admin = _hdr(client, "school_admin01")
    bid = _batch(client, admin)
    term_id = _schedule_term_id(bid)
    math = _seed_ready_task(term_id, teacher_key="T9", teacher_name="张老师",
                            course_name="高等数学", code_suffix=f"{bid}-MATH")
    english = _seed_ready_task(term_id, teacher_key="T9", teacher_name="张老师",
                               course_name="英语", code_suffix=f"{bid}-ENG")
    buf = _xlsx_bytes([
        [2, 1, "高等数学", "张老师", "T9", "", "", "A201", 1, 18, "ALL", str(math["task"])],
        [2, 1, "英语", "张老师", "T9", "", "", "B202", 1, 18, "ALL", str(english["task"])],
    ])
    r = client.post(f"{BASE}/schedule-batches/{bid}/import/xlsx", headers=admin,
                    files={"file": ("import.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    data = r.json()
    assert data["code"] == 0
    assert data["data"]["atomic"] is True and data["data"]["committed"] is False
    assert data["data"]["imported"] == 0 and len(data["data"]["conflicts"]) == 1


def test_07_sanitize_import_rows_blocks_formula_injection():
    from app.modules.academic_affairs.services.academic_affairs_schedule_service import sanitize_import_rows
    rows = [{"courseName": "=SUM(A1)", "teacherName": "+cmd", "className": "-DDE", "classroom": "@evil", "weekday": "1"}]
    out = sanitize_import_rows(rows)
    assert out[0]["courseName"] == "'=SUM(A1)"
    assert out[0]["teacherName"] == "'+cmd"
    assert out[0]["className"] == "'-DDE"
    assert out[0]["classroom"] == "'@evil"
    assert out[0]["weekParity"] == "ALL" and out[0]["startWeek"] == "1" and out[0]["endWeek"] == "18"


def test_10_summary(client, db_mode):
    admin = _hdr(client, "school_admin01")
    term_id = _ensure_term()
    ids = _seed_ready_task(term_id, teacher_key="T1", teacher_name="王老师",
                           course_name="高数", weekly_hours=1, code_suffix="SUMMARY")
    bid = _batch(client, admin, term_id=term_id)
    _item(client, admin, bid, taskId=str(ids["task"]))
    r = client.get(f"{BASE}/schedule-batches/{bid}/summary", headers=admin).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["totalTasks"] == 1 and d["scheduledTasks"] == 1
    assert d["completionRate"] == 100.0
    assert d["scheduledSessions"] == 1 and d["expectedSessions"] == 1
    assert d["hardConflicts"] == 0 and d["canPrePublish"] is True


def test_11_teacher_object_then_adjust(client, db_mode):
    admin = _hdr(client, "school_admin01")
    academic = _hdr(client, "academic01")
    bid = _batch(client, admin)
    add = _item(client, admin, bid, teacherKey="academic01", teacherName="赵敏").json()
    item_id = add["data"]["itemId"]
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=admin)
    bad = client.post(f"{BASE}/schedule-batches/{bid}/teacher-object", headers=academic,
                      json={"itemId": item_id, "reason": "短"})
    assert bad.status_code == 400
    ok = client.post(f"{BASE}/schedule-batches/{bid}/teacher-object", headers=academic,
                     json={"itemId": item_id, "reason": "与其他课程时间冲突"}).json()
    assert ok["code"] == 0 and ok["data"]["batchStatus"] == "DRAFT"
    lst = client.get(f"{BASE}/schedule-batches/{bid}/objections", headers=admin).json()
    assert any(x["itemId"] == item_id for x in lst["data"]["items"])
    same = client.put(f"{BASE}/schedule-batches/{bid}/items/{item_id}", headers=admin,
                      json={"weekday": 1, "slotNo": 1, "classroom": "A101", "weekParity": "ALL"})
    assert same.status_code == 200
    adj = client.put(f"{BASE}/schedule-batches/{bid}/items/{item_id}", headers=admin,
                     json={"weekday": 3, "slotNo": 5, "classroom": "C303", "weekParity": "ALL"}).json()
    assert adj["code"] == 0 and adj["data"]["weekday"] == 3 and adj["data"]["slotNo"] == 5
    lst2 = client.get(f"{BASE}/schedule-batches/{bid}/objections", headers=admin).json()
    assert not any(x["itemId"] == item_id for x in lst2["data"]["items"])


def test_11_teacher_object_forbidden_for_others_item(client, db_mode):
    admin = _hdr(client, "school_admin01")
    academic = _hdr(client, "academic01")
    bid = _batch(client, admin)
    add = _item(client, admin, bid, teacherKey="someone-else").json()
    item_id = add["data"]["itemId"]
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=admin)
    r = client.post(f"{BASE}/schedule-batches/{bid}/teacher-object", headers=academic,
                    json={"itemId": item_id, "reason": "这不是我的课表条目"})
    assert r.status_code == 403


def test_11_adjust_into_real_conflict_409(client, db_mode):
    admin = _hdr(client, "school_admin01")
    academic = _hdr(client, "academic01")
    bid = _batch(client, admin)
    add = _item(client, admin, bid, teacherKey="academic01", teacherName="赵敏").json()
    item_id = add["data"]["itemId"]
    _item(client, admin, bid, weekday=2, slotNo=2, teacherKey="T-other", classroom="D404")
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=admin)
    client.post(f"{BASE}/schedule-batches/{bid}/teacher-object", headers=academic,
                json={"itemId": item_id, "reason": "时间不方便，申请改排"})
    r = client.put(f"{BASE}/schedule-batches/{bid}/items/{item_id}", headers=admin,
                   json={"weekday": 2, "slotNo": 2, "classroom": "D404", "weekParity": "ALL"})
    assert r.status_code == 409


def test_13_archive_requires_published(client, db_mode):
    admin = _hdr(client, "school_admin01")
    bid = _batch(client, admin)
    r = client.post(f"{BASE}/schedule-batches/{bid}/archive", headers=admin)
    assert r.status_code == 409


def test_13_archive_success_and_listed(client, db_mode):
    admin = _hdr(client, "school_admin01")
    bid = _batch(client, admin)
    _item(client, admin, bid)
    client.post(f"{BASE}/schedule-batches/{bid}/publish", headers=admin)
    r = client.post(f"{BASE}/schedule-batches/{bid}/archive", headers=admin).json()
    assert r["code"] == 0 and r["data"]["status"] == "ARCHIVED"
    lst = client.get(f"{BASE}/schedule-batches", headers=admin, params={"status": "ARCHIVED"}).json()
    assert any(x["batchId"] == bid for x in lst["data"]["items"])


def test_student_forbidden_on_new_endpoints(client, db_mode):
    from app.core.security import create_access_token

    stu = {"Authorization": "Bearer " + create_access_token({
        "userId": "u-SC900", "realName": "学生", "studentNo": "SC900",
        "userType": "STUDENT", "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP"})}
    admin = _hdr(client, "school_admin01")
    bid = _batch(client, admin)
    assert client.get(f"{BASE}/schedule-batches/{bid}/room-view", headers=stu, params={"classroom": "A101"}).status_code == 403
    assert client.get(f"{BASE}/schedule-batches/{bid}/summary", headers=stu).status_code == 403
    assert client.post(f"{BASE}/schedule-batches/{bid}/archive", headers=stu).status_code == 403
