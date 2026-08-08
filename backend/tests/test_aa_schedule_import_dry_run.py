"""排课 Excel 导入语义化预检回归（P1 批次B·Excel 项1+项4）。

原实现 `academic_file_exchange_service._parse_and_validate()` 的 SCHEDULE 分支不管文件内容
是什么，永远返回 invalidRows=0——学校看到"预检通过"，确认导入时才第一次发现教师/教室/
班级冲突，体验上是"骗过关"。新实现 `academic_affairs_schedule_final_service.import_dry_run()`
与真正落库的 `import_items()` 共用同一行级校验器 `_apply_import_rows`（内部即 `_resolve_task`+
`_build_item`+`_detect_conflict`），只是全程包在一个必定回滚的保存点里。

同时验证批次B项2——ATOMIC/PARTIAL 显式契约：默认 atomic=True 时整批中 1 行冲突则整批不
写入；显式 atomic=False 时保留逐行尽力导入。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

from datetime import date, timedelta

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"
COURSE = "预检课程"

# 本文件全部用例实际用到的 (teacherKey, classId) 组合，统一在 _seed() 里建成 READY 教学任务。
_TASK_COMBOS = [
    ("DRY_T1", 9100), ("DRY_T1", 9200), ("DRY_T2", 9300),
    ("DRY_T3", 9400), ("DRY_T3", 9500), ("DRY_T4", 9600),
    ("DRY_T1", 9700), ("DRY_T5", 9800), ("DRY_T1", 9900),
]


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _svc_user():
    return {
        "tenantId": str(TID), "userId": "81002", "realName": "排课预检测试",
        "userType": "TEACHER", "currentRoleCode": "ACADEMIC_ADMIN",
        "permissions": ["*"], "dataScope": "ALL",
    }


def _term(client, hdr) -> str:
    """建一个已发布(current)学期；不能假设 AaTerm 自增 id=1。"""
    start = date(2026, 9, 1)
    tid = client.post(f"{BASE}/terms", headers=hdr, json={
        "yearCode": "2098-2099", "termNo": 1, "termName": "导入预检回归测试学期",
        "startDate": start.isoformat(), "endDate": (start + timedelta(days=200)).isoformat(),
        "teachingWeeks": 18}).json()["data"]["termId"]
    client.post(f"{BASE}/terms/{tid}/publish", headers=hdr)
    return str(tid)


def _seed_tasks(term_id: str) -> None:
    """建一条 APPROVED 教学任务批次 + 全部用例用到的 (courseName=预检课程, teacherKey,
    classId) 组合各一条 READY 教学任务，让 `_resolve_task()` 的模糊匹配总能命中。"""
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTimeSlot, College
    db = get_sessionmaker()()
    for slot_no in range(1, 6):
        db.add(AaTimeSlot(tenant_id=TID, slot_no=slot_no, slot_name=f"第{slot_no}节",
                          start_time="00:00", end_time="23:59", enabled=True, status="ENABLED"))
    col = College(tenant_id=TID, college_name="导入预检测试学院", status="ACTIVE")
    db.add(col); db.flush()
    course = AaCourse(tenant_id=TID, course_code="DRY_RUN_TEST_COURSE", course_name=COURSE, credit=2)
    db.add(course); db.flush()
    tb = AaTeachingTaskBatch(tenant_id=TID, term_id=int(term_id), batch_name="导入预检测试教学任务批次",
                             college_id=col.id, status="APPROVED")
    db.add(tb); db.flush()
    for teacher_key, class_id in _TASK_COMBOS:
        db.add(AaTeachingTask(
            tenant_id=TID, batch_id=tb.id, course_id=course.id, course_name=COURSE, class_id=class_id,
            teaching_class_name=f"预检班{class_id}", teacher_key=teacher_key,
            teacher_name=f"{teacher_key}老师", status="READY",
            weekly_hours=8, total_hours=144, start_week=1, end_week=18,
        ))
    db.commit()
    db.close()


def _setup(client) -> tuple[dict, int]:
    hdr = _hdr(client, "school_admin01")
    term_id = _term(client, hdr)
    _seed_tasks(term_id)
    bid = int(client.post(f"{BASE}/schedule-batches", headers=hdr,
                          json={"termId": term_id}).json()["data"]["batchId"])
    return hdr, bid


def _seed_existing_item(client, hdr, bid):
    """先手工排一节课，作为后续预检/导入行的冲突基准。"""
    body = {"weekday": 3, "slotNo": 2, "startWeek": 1, "endWeek": 18, "weekParity": "ALL",
            "teacherKey": "DRY_T1", "teacherName": "预检老师", "classId": "9100", "className": "预检班",
            "classroom": "DRY_A101", "courseName": COURSE}
    r = client.post(f"{BASE}/schedule-batches/{bid}/items", headers=hdr, json=body)
    assert r.status_code == 200, r.text


def test_dry_run_reports_real_conflict_not_fake_zero(client, db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as sched

    hdr, bid = _setup(client)
    _seed_existing_item(client, hdr, bid)

    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    try:
        preview = sched.import_dry_run(bid, _svc_user(), [
            # 同教师同时段，与已排课程冲突——旧实现会谎报 invalidRows=0
            {"courseName": COURSE, "weekday": 3, "slotNo": 2, "teacherKey": "DRY_T1",
             "classId": "9200", "classroom": "DRY_B202"},
        ])
    finally:
        set_current_user(None)
        set_tenant(None)

    assert preview["totalRows"] == 1
    assert preview["invalidRows"] == 1, "旧实现会硬编码 invalidRows=0，预检必须真正跑冲突检测"
    assert preview["validRows"] == 0
    assert "TEACHER" in preview["errors"][0]["message"]


def test_dry_run_never_writes_even_on_success(client, db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as sched

    hdr, bid = _setup(client)

    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    try:
        preview = sched.import_dry_run(bid, _svc_user(), [
            {"courseName": COURSE, "weekday": 4, "slotNo": 3, "teacherKey": "DRY_T2",
             "classId": "9300", "classroom": "DRY_C303"},
        ])
    finally:
        set_current_user(None)
        set_tenant(None)

    assert preview["validRows"] == 1 and preview["invalidRows"] == 0

    db = get_sessionmaker()()
    try:
        count = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == TID, AaScheduleItem.batch_id == bid,
        ).count()
    finally:
        db.close()
    assert count == 0, "预检必须零写入——一次通过的预检不应该在数据库里留下任何排课条目"


def test_dry_run_catches_intra_file_conflict(client, db_mode):
    """同一份待导入文件内部两行互相冲突（都是新行，谁都不在数据库里）也要能发现。"""
    from app.core.context import set_current_user, set_tenant
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as sched

    hdr, bid = _setup(client)

    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    try:
        preview = sched.import_dry_run(bid, _svc_user(), [
            {"courseName": COURSE, "weekday": 5, "slotNo": 1, "teacherKey": "DRY_T3",
             "classId": "9400", "classroom": "DRY_D404"},
            {"courseName": COURSE, "weekday": 5, "slotNo": 1, "teacherKey": "DRY_T3",
             "classId": "9500", "classroom": "DRY_E505"},
        ])
    finally:
        set_current_user(None)
        set_tenant(None)

    assert preview["validRows"] == 1 and preview["invalidRows"] == 1


def test_dry_run_and_confirm_agree_same_validator(client, db_mode):
    """预检说 1 行冲突，真正确认导入（atomic=False 逐行尽力）也必须恰好是同一行冲突——
    两边共用 _apply_import_rows，不是两套会漂移的校验逻辑。"""
    from app.core.context import set_current_user, set_tenant
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as sched

    hdr, bid = _setup(client)
    _seed_existing_item(client, hdr, bid)

    rows = [
        {"courseName": COURSE, "weekday": 6, "slotNo": 4, "teacherKey": "DRY_T4",
         "classId": "9600", "classroom": "DRY_F606"},
        {"courseName": COURSE, "weekday": 3, "slotNo": 2, "teacherKey": "DRY_T1",
         "classId": "9700", "classroom": "DRY_G707"},  # 冲突
    ]
    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    try:
        preview = sched.import_dry_run(bid, _svc_user(), rows)
        confirmed = sched.import_items(bid, _svc_user(), rows, atomic=False)
    finally:
        set_current_user(None)
        set_tenant(None)

    assert preview["invalidRows"] == 1 and confirmed["imported"] == 1
    assert len(confirmed["conflicts"]) == 1
    assert preview["errors"][0]["row"] == confirmed["conflicts"][0]["row"] == 2


def test_atomic_default_rolls_back_whole_batch_on_any_conflict(client, db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as sched

    hdr, bid = _setup(client)
    _seed_existing_item(client, hdr, bid)

    rows = [
        {"courseName": COURSE, "weekday": 6, "slotNo": 5, "teacherKey": "DRY_T5",
         "classId": "9800", "classroom": "DRY_H808"},
        {"courseName": COURSE, "weekday": 3, "slotNo": 2, "teacherKey": "DRY_T1",
         "classId": "9900", "classroom": "DRY_I909"},  # 冲突
    ]
    set_tenant({"tenantId": str(TID)})
    set_current_user(_svc_user())
    try:
        result = sched.import_items(bid, _svc_user(), rows)  # atomic 默认 True
    finally:
        set_current_user(None)
        set_tenant(None)

    assert result["atomic"] is True and result["committed"] is False
    assert result["imported"] == 0 and len(result["conflicts"]) == 1

    db = get_sessionmaker()()
    try:
        # 只应存在预置的那一节课；不冲突的第一行也不能被单独写进去
        count = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == TID, AaScheduleItem.batch_id == bid,
        ).count()
    finally:
        db.close()
    assert count == 1, "atomic=True 时任一行冲突必须整批回滚，不冲突的行也不能单独落库"
