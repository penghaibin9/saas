"""排课管理 Tier1 R2 续工端点测试（03排课约束/05教室可用时间/07自动排课预留/10排课结果/11排课调整/13排课归档）。

复用既有课表批次/条目（academic_affairs_schedule_service）与冲突报告（academic_affairs_scheduling_service）。
本文件仅用于 SQLite 自测（禁止连接共享 MySQL 测试库）：运行前需在环境变量显式覆盖
TEST_DATABASE_URL=sqlite:///... ，令 conftest.py 的 db_mode 夹具落到 sqlite 分支，不触碰 backend/.env
中被多个并行任务共用的 MySQL 测试库。
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


def _batch(client, hdr, term_id="501"):
    return client.post(f"{BASE}/schedule-batches", headers=hdr, json={"termId": term_id}).json()["data"]["batchId"]


def _item(client, hdr, bid, **kw):
    body = {"weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
            "teacherKey": "T1", "teacherName": "王老师", "classId": "100", "className": "软件2601",
            "classroom": "A101", "courseName": "高数", **kw}
    r = client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json=body)
    return r


# ── 03 排课约束：复用排课规则中心 CRUD，仅 ruleKey 归类为约束类 ──

def test_03_constraint_reuses_rule_center(client, db_mode):
    admin = _hdr(client, "school_admin01")
    r = client.put(f"{BASE}/scheduling/rules", headers=admin,
                   json={"ruleKey": "teacherDailyMax", "termId": "501", "ruleValue": {"value": 8}}).json()
    assert r["code"] == 0 and r["data"]["ruleKey"] == "teacherDailyMax"
    lst = client.get(f"{BASE}/scheduling/rules", headers=admin, params={"termId": "501"}).json()
    assert any(x["ruleKey"] == "teacherDailyMax" for x in lst["data"]["items"])


# ── 05 教室可用时间 ──

def test_05_room_view_hit_and_empty(client, db_mode):
    admin = _hdr(client, "school_admin01")
    bid = _batch(client, admin)
    assert _item(client, admin, bid, classroom="A101").status_code == 200
    hit = client.get(f"{BASE}/schedule-batches/{bid}/room-view", headers=admin, params={"classroom": "A101"}).json()
    assert hit["code"] == 0 and len(hit["data"]["items"]) == 1
    empty = client.get(f"{BASE}/schedule-batches/{bid}/room-view", headers=admin, params={"classroom": "Z999"}).json()
    assert empty["code"] == 0 and empty["data"]["items"] == [] and "暂无排课" in empty["data"]["note"]


# ── 07 自动排课预留：Excel 结果导入通道（不写算法本体） ──

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
    buf = _xlsx_bytes([
        [2, 1, "高等数学", "张老师", "T9", "", "", "A201", 1, 18, "ALL", ""],
        [2, 1, "英语", "张老师", "T9", "", "", "B202", 1, 18, "ALL", ""],  # 同教师同时段 → 冲突
    ])
    r = client.post(f"{BASE}/schedule-batches/{bid}/import/xlsx", headers=admin,
                    files={"file": ("import.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    data = r.json()
    assert data["code"] == 0
    assert data["data"]["imported"] == 1 and len(data["data"]["conflicts"]) == 1


def test_07_sanitize_import_rows_blocks_formula_injection():
    """单测 sanitize_import_rows：xlsx 单元格若被制成「文本格式的 =/+/-/@ 开头字符串」（真实注入手法），
    openpyxl data_only=True 对真公式单元格只返回缓存计算值（无法在纯 Python 测试中稳定复现公式文本回读），
    故直接对 sanitize_import_rows 函数做单元测试，覆盖其转义逻辑本身。"""
    from app.modules.academic_affairs.services.academic_affairs_schedule_service import sanitize_import_rows
    rows = [{"courseName": "=SUM(A1)", "teacherName": "+cmd", "className": "-DDE", "classroom": "@evil", "weekday": "1"}]
    out = sanitize_import_rows(rows)
    assert out[0]["courseName"] == "'=SUM(A1)"
    assert out[0]["teacherName"] == "'+cmd"
    assert out[0]["className"] == "'-DDE"
    assert out[0]["classroom"] == "'@evil"
    # 默认值补齐
    assert out[0]["weekParity"] == "ALL" and out[0]["startWeek"] == "1" and out[0]["endWeek"] == "18"


# ── 10 排课结果：汇总统计 ──

def _seed_ready_task(term_id):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    db = get_sessionmaker()()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=int(term_id), batch_name="任务批次", status="APPROVED")
    db.add(tb); db.flush()
    t = AaTeachingTask(tenant_id=TID, batch_id=tb.id, course_id=1, course_name="高数",
                       teacher_key="T1", teacher_name="王老师", weekly_hours=4, status="READY")
    db.add(t); db.flush()
    ids = {"taskBatch": tb.id, "task": t.id}
    db.commit()
    db.close()
    return ids


def test_10_summary(client, db_mode):
    admin = _hdr(client, "school_admin01")
    term_id = "777"
    ids = _seed_ready_task(term_id)
    bid = _batch(client, admin, term_id=term_id)
    _item(client, admin, bid, taskId=str(ids["task"]))
    r = client.get(f"{BASE}/schedule-batches/{bid}/summary", headers=admin).json()
    assert r["code"] == 0
    d = r["data"]
    assert d["totalTasks"] == 1 and d["scheduledTasks"] == 1
    assert d["completionRate"] == 100.0
    assert d["scheduledHours"] == 1 and d["expectedHours"] == 4
    assert d["hardConflicts"] == 0 and d["canPrePublish"] is True


# ── 11 排课调整：预发布阶段教师异议 → 定点改排 ──

def test_11_teacher_object_then_adjust(client, db_mode):
    admin = _hdr(client, "school_admin01")
    academic = _hdr(client, "academic01")  # ACADEMIC_TEACHER，持 academicAffairs.* 权限
    bid = _batch(client, admin)
    add = _item(client, admin, bid, teacherKey="academic01", teacherName="赵敏").json()
    item_id = add["data"]["itemId"]
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=admin)

    # 原因太短 → 400（本项目校验错误码统一 400）
    bad = client.post(f"{BASE}/schedule-batches/{bid}/teacher-object", headers=academic,
                      json={"itemId": item_id, "reason": "短"})
    assert bad.status_code == 400

    ok = client.post(f"{BASE}/schedule-batches/{bid}/teacher-object", headers=academic,
                     json={"itemId": item_id, "reason": "与其他课程时间冲突"}).json()
    assert ok["code"] == 0 and ok["data"]["batchStatus"] == "DRAFT"

    lst = client.get(f"{BASE}/schedule-batches/{bid}/objections", headers=admin).json()
    assert any(x["itemId"] == item_id for x in lst["data"]["items"])

    # 改排回原时段自身（exclude_id 生效，不应误判自冲突）→ 200
    same = client.put(f"{BASE}/schedule-batches/{bid}/items/{item_id}", headers=admin,
                      json={"weekday": 1, "slotNo": 1, "classroom": "A101", "weekParity": "ALL"})
    assert same.status_code == 200

    # 改排到全新空档 → 成功，异议标记清除
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
    # 另一条已占用 周2第2节 教室 D404
    _item(client, admin, bid, weekday=2, slotNo=2, teacherKey="T-other", classroom="D404")
    client.post(f"{BASE}/schedule-batches/{bid}/pre-publish", headers=admin)
    client.post(f"{BASE}/schedule-batches/{bid}/teacher-object", headers=academic,
               json={"itemId": item_id, "reason": "时间不方便，申请改排"})
    r = client.put(f"{BASE}/schedule-batches/{bid}/items/{item_id}", headers=admin,
                  json={"weekday": 2, "slotNo": 2, "classroom": "D404", "weekParity": "ALL"})
    assert r.status_code == 409


# ── 13 排课归档：与 void-reissue 语义区分 ──

def test_13_archive_requires_published(client, db_mode):
    admin = _hdr(client, "school_admin01")
    bid = _batch(client, admin)
    r = client.post(f"{BASE}/schedule-batches/{bid}/archive", headers=admin)
    assert r.status_code == 409  # 仍是 DRAFT，尚未发布


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
