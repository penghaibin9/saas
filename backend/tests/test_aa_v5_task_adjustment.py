"""第五版教学任务调整：真实接口拒绝与同事务回滚。

仅在 db_mode 隔离库准备既有已审批任务事实，不作为多角色正常办理验收。
被测调整始终走正式接口及真实学院身份；故障仅注入教学班同步边界。
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import or_, select

from tests.support_academic_review_identity import ensure_course_review_college
from tests.support_task_review_identity import ensure_task_review_identity
from tests.test_aa_teaching_task import BASE, TID, _hdr, _seed, _tasks, _term


def _approved_facts(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch

    students = _seed(db_mode, two=True)
    college_id = ensure_course_review_college()
    ensure_task_review_identity(college_id)
    school = _hdr(client, "school_admin01")
    college = _hdr(client, "college_admin01")
    term_id = int(_term(client, school))
    marker = "V5-ADJUST-" + uuid4().hex[:12]
    assert students["college"] != college_id, "学生学院与开课责任学院必须独立"
    with get_sessionmaker()() as db:
        course = AaCourse(tenant_id=TID, course_code=marker, course_name="调整回滚课程",
                          owner_college_id=college_id, status="ENABLED", hours_total=64)
        batch = AaTeachingTaskBatch(tenant_id=TID, term_id=term_id, college_id=college_id,
                                    batch_name=marker, status="APPROVED", editable_scope_key=None)
        db.add_all([course, batch]); db.flush()
        tasks, classes = [], []
        for index, class_id in enumerate((students["class1"], students["class2"]), 1):
            code = f"{marker}-{index}"
            task = AaTeachingTask(tenant_id=TID, batch_id=batch.id, course_id=course.id,
                                  course_code=marker, course_name=course.course_name,
                                  class_id=class_id, formation_mode="ADMIN_FIXED",
                                  teaching_class_code=code, teaching_class_name=f"调整回滚教学班{index}",
                                  teacher_key="academic01", teacher_name="赵敏",
                                  start_week=1, end_week=18, weekly_hours=4, total_hours=64,
                                  confirm_at=datetime(2026, 9, 1), status="READY")
            db.add(task); db.flush()
            teaching_class = AaTeachingClass(tenant_id=TID, teaching_task_id=task.id,
                                             term_id=term_id, course_id=course.id,
                                             class_code=code, class_name=task.teaching_class_name,
                                             class_type="ADMIN", source_type="TEACHING_TASK", status="ACTIVE")
            db.add(teaching_class); db.flush()
            db.add(AaTeachingClassTeacher(tenant_id=TID, teaching_class_id=teaching_class.id,
                                          teacher_key="academic01", teacher_name="赵敏",
                                          role_type="PRIMARY", start_week=1, end_week=18, status="ACTIVE"))
            tasks.append(int(task.id)); classes.append(int(teaching_class.id))
        db.commit()
        return {"school": school, "college": college, "term": term_id, "college_id": college_id,
                "batch": int(batch.id), "course": int(course.id), "tasks": tasks, "classes": classes}


def _snapshot(facts):
    """从新会话读取完整落库行，连同投影、兄弟课表和相关业务审计比较。"""
    from app.db.session import get_sessionmaker
    from app.models import (
        AaScheduleItem, AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask,
        AaTeachingTaskBatch, AffairsAuditTrail,
    )

    def rows(db, model, *conditions):
        return [dict(row) for row in db.execute(select(model.__table__).where(
            model.tenant_id == TID, *conditions,
        ).order_by(model.id)).mappings().all()]

    with get_sessionmaker()() as db:
        return {
            "batches": rows(db, AaTeachingTaskBatch, AaTeachingTaskBatch.term_id == facts["term"],
                            AaTeachingTaskBatch.college_id == facts["college_id"]),
            "tasks": rows(db, AaTeachingTask, AaTeachingTask.batch_id == facts["batch"]),
            "classes": rows(db, AaTeachingClass, AaTeachingClass.id.in_(facts["classes"])),
            "teachers": rows(db, AaTeachingClassTeacher,
                             AaTeachingClassTeacher.teaching_class_id.in_(facts["classes"])),
            "schedules": rows(db, AaScheduleItem, AaScheduleItem.task_id.in_(facts["tasks"])),
            "audit": rows(db, AffairsAuditTrail, or_(
                (AffairsAuditTrail.biz_type == "AA_TASK_BATCH") & (AffairsAuditTrail.biz_id == facts["batch"]),
                (AffairsAuditTrail.biz_type == "AA_TASK") & AffairsAuditTrail.biz_id.in_(facts["tasks"]),
            )),
        }


def _adjust(client, facts):
    return client.post(f"{BASE}/teaching-tasks/{facts['tasks'][0]}/adjust", headers=facts["college"],
                       json={"teacherKey": "academic02", "teacherName": "李老师", "weeklyHours": 5,
                             "reason": "原任课教师因故申请更换"})


def _assert_unchanged(client, facts, before):
    assert _snapshot(facts) == before
    rows = _tasks(client, facts["school"], facts["batch"])
    assert {row["status"] for row in rows} == {"READY"}
    assert {row["teacherKey"] for row in rows} == {"academic01"}
    workbench = client.get(f"{BASE}/teaching-task-batches/{facts['batch']}/workbench", headers=facts["college"])
    assert workbench.status_code == 200, workbench.text
    assert workbench.json()["data"]["status"] == "APPROVED"


def test_adjust_approved_task_with_sibling_schedule_rolls_back(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleBatch, AaScheduleItem

    facts = _approved_facts(client, db_mode)
    with get_sessionmaker()() as db:
        schedule = AaScheduleBatch(tenant_id=TID, term_id=facts["term"], college_id=facts["college_id"],
                                   batch_name="兄弟教学任务已有课表", status="DRAFT")
        db.add(schedule); db.flush()
        db.add(AaScheduleItem(tenant_id=TID, batch_id=schedule.id, task_id=facts["tasks"][1],
                             course_id=facts["course"], teacher_key="academic01", weekday=1, slot_no=1,
                             start_week=1, end_week=18, week_parity="ALL", status="EFFECTIVE"))
        db.commit()
    before = _snapshot(facts)
    response = _adjust(client, facts)
    assert response.status_code == 409, response.text
    assert response.json()["bizCode"] == "DATA_CONFLICT"
    assert "本批次已有课表" in response.json()["message"]
    _assert_unchanged(client, facts, before)


def test_adjust_approved_task_with_other_editable_batch_rolls_back(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskBatch
    from app.modules.academic_affairs.services.academic_affairs_task_batch_inventory_service import canonical_editable_scope_key

    facts = _approved_facts(client, db_mode)
    with get_sessionmaker()() as db:
        db.add(AaTeachingTaskBatch(tenant_id=TID, term_id=facts["term"], college_id=facts["college_id"],
                                  batch_name="另一原有可编辑批次", status="DRAFT",
                                  editable_scope_key=canonical_editable_scope_key(facts["term"], facts["college_id"])))
        db.commit()
    before = _snapshot(facts)
    response = _adjust(client, facts)
    assert response.status_code == 409, response.text
    assert response.json()["bizCode"] == "DATA_CONFLICT"
    assert "另一可编辑批次" in response.json()["message"]
    _assert_unchanged(client, facts, before)


def test_adjust_projection_failure_rolls_back_task_batch_relation_and_audit(client, db_mode, monkeypatch):
    from app.models import AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask, AaTeachingTaskBatch, AffairsAuditTrail
    from app.modules.academic_affairs.services import academic_affairs_task_service as service

    facts = _approved_facts(client, db_mode)
    before = _snapshot(facts)
    reached = []

    def failing_projection(db, task_id):
        task = db.get(AaTeachingTask, int(task_id))
        batch = db.get(AaTeachingTaskBatch, facts["batch"])
        assert task.status == "ASSIGNED" and task.teacher_key == "academic02"
        assert batch.status == "RETURNED" and batch.editable_scope_key
        actions = set(db.scalars(select(AffairsAuditTrail.action).where(
            AffairsAuditTrail.tenant_id == TID,
            AffairsAuditTrail.biz_id.in_([task.id, batch.id]),
        )).all())
        assert {"TEACHER_ADJUST_REOPEN", "ADJUST"} <= actions
        teaching_class = db.get(AaTeachingClass, facts["classes"][0])
        teaching_class.class_name = "注入故障前已写入的教学班变化"
        relation = db.scalars(select(AaTeachingClassTeacher).where(
            AaTeachingClassTeacher.tenant_id == TID,
            AaTeachingClassTeacher.teaching_class_id == teaching_class.id,
            AaTeachingClassTeacher.teacher_key == "academic01",
        )).one()
        relation.status = "INACTIVE"
        db.flush()
        reached.append(int(task_id))
        raise RuntimeError("v5 injected adjustment projection failure")

    monkeypatch.setattr(service.teaching_class, "ensure_teaching_class_for_task", failing_projection)
    try:
        response = _adjust(client, facts)
    except RuntimeError as exc:
        assert "v5 injected adjustment projection failure" in str(exc)
    else:
        assert response.status_code >= 500, response.text
    assert reached == [facts["tasks"][0]], "必须真实到达投影故障点，不能因前置拒绝冒充回滚通过"
    _assert_unchanged(client, facts, before)


def test_adjust_explicit_teacher_topology_rejects_and_rolls_back(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClassTeacher

    facts = _approved_facts(client, db_mode)
    with get_sessionmaker()() as db:
        db.add(AaTeachingClassTeacher(tenant_id=TID, teaching_class_id=facts["classes"][0],
                                      teacher_key="academic02", teacher_name="李老师",
                                      role_type="CO_TEACHER", start_week=1, end_week=18, status="ACTIVE"))
        db.commit()
    before = _snapshot(facts)
    response = _adjust(client, facts)
    assert response.status_code == 409, response.text
    assert response.json()["bizCode"] == "DATA_CONFLICT"
    assert "正式教师关系管理" in response.json()["message"]
    _assert_unchanged(client, facts, before)


def test_adjust_and_formal_teacher_update_serialize_without_deadlock(client, db_mode, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Event

    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClassTeacher
    from app.modules.academic_affairs.services import academic_affairs_grade_todo_teacher_relation_guard as projection
    from app.modules.academic_affairs.services import academic_affairs_teaching_class_teacher_service as teachers

    facts = _approved_facts(client, db_mode)
    with get_sessionmaker()() as db:
        relation_id = db.scalar(select(AaTeachingClassTeacher.id).where(
            AaTeachingClassTeacher.tenant_id == TID,
            AaTeachingClassTeacher.teaching_class_id == facts["classes"][0],
            AaTeachingClassTeacher.teacher_key == "academic01",
            AaTeachingClassTeacher.status == "ACTIVE",
        ))
    assert relation_id is not None
    start, adjustment_has_task, relation_has_read = Barrier(2), Event(), Event()
    original_sync, original_task_term = projection.sync_default_assignment_change, teachers._task_term

    def rendezvous_sync(db, task, previous_assignment):
        if int(task.id) == facts["tasks"][0]:
            # 此时真实调整事务已经持有任务锁；不替代任何权限、SQL 或业务规则。
            adjustment_has_task.set()
            assert relation_has_read.wait(30), "正式任课修改未到达真实关联任务读取点"
        return original_sync(db, task, previous_assignment)

    def rendezvous_task_term(db, teaching_class):
        result = original_task_term(db, teaching_class)
        if int(teaching_class.id) == facts["classes"][0]:
            # 旧实现先锁教学班再到这里，将与任务调整形成反向等待；新实现尚未锁班。
            relation_has_read.set()
            assert adjustment_has_task.wait(30), "教学任务调整未到达真实同步边界"
        return result

    monkeypatch.setattr(projection, "sync_default_assignment_change", rendezvous_sync)
    monkeypatch.setattr(teachers, "_task_term", rendezvous_task_term)

    def adjust():
        start.wait(timeout=30)
        return _adjust(client, facts)

    def update_relation():
        start.wait(timeout=30)
        return client.put(
            f"{BASE}/teaching-classes/{facts['classes'][0]}/teachers/{relation_id}",
            headers=facts["college"],
            json={"teacherKey": "academic02", "reason": "正式任课关系同步更换教师"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        adjusted, updated = pool.submit(adjust), pool.submit(update_relation)
        adjustment_response, relation_response = adjusted.result(timeout=60), updated.result(timeout=60)
    assert adjustment_has_task.is_set() and relation_has_read.is_set()
    assert adjustment_response.status_code == 200, adjustment_response.text
    # 调整先完成并停用原关系；等待中的正式命令必须读到该新状态，不能覆盖或死锁。
    assert relation_response.status_code == 409, relation_response.text
    assert relation_response.json()["bizCode"] == "DATA_CONFLICT"
    after = _snapshot(facts)
    task = next(row for row in after["tasks"] if row["id"] == facts["tasks"][0])
    batch = next(row for row in after["batches"] if row["id"] == facts["batch"])
    assert task["status"] == "ASSIGNED" and task["teacher_key"] == "academic02"
    assert batch["status"] == "RETURNED" and batch["editable_scope_key"]
    relations = [row for row in after["teachers"] if row["teaching_class_id"] == facts["classes"][0]]
    assert [(row["teacher_key"], row["role_type"]) for row in relations if row["status"] == "ACTIVE"] == [
        ("academic02", "PRIMARY"),
    ]
    assert next(row for row in relations if row["id"] == relation_id)["status"] == "INACTIVE"
    assert sum(row["action"] == "ADJUST" for row in after["audit"]) == 1
    assert sum(row["action"] == "TEACHER_ADJUST_REOPEN" for row in after["audit"]) == 1
    formal = client.get(f"{BASE}/teaching-classes/{facts['classes'][0]}/teachers", headers=facts["college"])
    assert formal.status_code == 200, formal.text
    assert [row["teacherKey"] for row in formal.json()["data"]["items"]] == ["academic02"]
