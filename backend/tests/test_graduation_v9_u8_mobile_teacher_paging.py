"""U8/M6 教师移动端毕设队列：MySQL 真分页、dataScope 与查询量合同。"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event

TID = 1000000000000000001


def _ctx(role="SCHOOL_ADMIN", *, college_id=None):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    user = {
        "userId": "1",
        "tenantId": str(TID),
        "realName": "U8教师",
        "currentRoleCode": role,
        "userType": "TEACHER",
        "activeContextId": "ctx",
    }
    if college_id is not None:
        user["collegeId"] = str(college_id)
    set_current_user(user)
    return user


def _clear_ctx():
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def _new_batch(db, label: str, planned_count: int):
    from app.models import GraduationBatch

    suffix = uuid.uuid4().hex[:10]
    row = GraduationBatch(
        tenant_id=TID,
        batch_name=f"U8 {label}-{suffix}",
        batch_no=f"U8-{label.upper()}-{suffix}",
        academic_year="2026-2027",
        grade_year="2027届",
        planned_count=planned_count,
        status="RUNNING",
    )
    db.add(row)
    db.flush()
    return row


def _seed(db, *, primary_count=220, other_count=9):
    from app.models import GraduationGrade, GraduationMidterm, GraduationStudent, GraduationTaskBook

    primary = _new_batch(db, "mobile-scale", primary_count)
    other = _new_batch(db, "other-batch", other_count)

    def add_rows(batch, count, prefix):
        students = []
        for idx in range(1, count + 1):
            student = GraduationStudent(
                tenant_id=TID,
                batch_id=batch.id,
                student_no=f"{prefix}{idx:04d}",
                name=f"U8学生{prefix}{idx:04d}",
                college_id="U8-COL-A" if idx <= max(1, count // 2) else "U8-COL-B",
                major_id="U8-MAJOR",
                class_name=f"软件{(idx - 1) // 50 + 1:02d}班",
                topic_title=f"U8毕设课题{idx:04d}",
                stage="MIDTERM",
                record_status="ACTIVE",
            )
            students.append(student)
        db.add_all(students)
        db.flush()
        db.add_all([
            GraduationTaskBook(
                tenant_id=TID,
                gd_student_id=student.id,
                taskbook_version=1,
                status="PENDING_CONFIRM",
                objective="U8任务目标",
                content="U8任务内容",
                progress_plan="U8进度计划",
                outcome_requirement="U8成果要求",
            ) for student in students
        ])
        db.add_all([
            GraduationMidterm(
                tenant_id=TID,
                gd_student_id=student.id,
                batch_id=batch.id,
                status="PENDING" if idx % 2 else "RECTIFY_SUBMITTED",
            ) for idx, student in enumerate(students, start=1)
        ])
        db.add_all([
            GraduationGrade(
                tenant_id=TID,
                gd_student_id=student.id,
                advisor_score=80,
                reviewer_score=82,
                defense_score=84,
                total_score=82,
                grade_level="良好",
                status="CALCULATED",
            ) for student in students
        ])
        return students

    primary_students = add_rows(primary, primary_count, "U8A")
    add_rows(other, other_count, "U8B")
    db.commit()
    return int(primary.id), int(other.id), [int(x.id) for x in primary_students]


def _count_selects(engine, fn):
    count = 0

    def before_cursor_execute(_conn, _cursor, statement, *_args, **_kwargs):
        nonlocal count
        if statement.lstrip().upper().startswith("SELECT"):
            count += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return result, count


def test_u8_mysql_teacher_mobile_queues_page_220_without_collect_all(db_mode):
    from app.db.session import get_engine, get_sessionmaker
    from app.modules.graduation.services import graduation_mobile_teacher_query_service as query

    db = get_sessionmaker()()
    try:
        batch_id, _other_batch_id, _ids = _seed(db)
    finally:
        db.close()

    user = _ctx()
    scoped = {**user, "graduationBatchId": str(batch_id), "batchId": str(batch_id)}
    engine = get_engine()
    try:
        for fn in (query.taskbooks_page, query.midterms_page, query.grades_page):
            first, first_selects = _count_selects(engine, lambda fn=fn: fn(scoped, 1, 20))
            second, second_selects = _count_selects(engine, lambda fn=fn: fn(scoped, 2, 20))

            assert first["total"] == 220
            assert second["total"] == 220
            assert first["page"] == 1 and second["page"] == 2
            assert first["pageSize"] == second["pageSize"] == 20
            assert len(first["items"]) == len(second["items"]) == 20
            assert first["hasMore"] is True and second["hasMore"] is True
            assert first["items"] != second["items"], "page2 must be a real SQL page, not page1 replay"
            assert first_selects <= 2, f"{fn.__name__} page1 SELECTs={first_selects}"
            assert second_selects <= 2, f"{fn.__name__} page2 SELECTs={second_selects}"
    finally:
        _clear_ctx()


def test_u8_teacher_mobile_batch_and_college_scope_fail_closed(db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.modules.graduation.services import graduation_mobile_teacher_query_service as query

    db = get_sessionmaker()()
    try:
        batch_id, other_batch_id, _ids = _seed(db, primary_count=220, other_count=11)
    finally:
        db.close()

    try:
        user = _ctx("COLLEGE_ADMIN", college_id="U8-COL-A")
        scoped = {**user, "graduationBatchId": str(batch_id), "batchId": str(batch_id)}
        for fn in (query.taskbooks_page, query.midterms_page, query.grades_page):
            page = fn(scoped, 1, 25)
            assert page["total"] == 110
            assert len(page["items"]) == 25

        # 切到另一批次只能看到另一批次自己的记录，不能把主批次 220 条串进来。
        other = {**user, "graduationBatchId": str(other_batch_id), "batchId": str(other_batch_id)}
        assert query.taskbooks_page(other, 1, 25)["total"] <= 11
        assert query.midterms_page(other, 1, 25)["total"] <= 11
        assert query.grades_page(other, 1, 25)["total"] <= 11

        # 缺批次必须失败，不允许退化为全租户读取。
        with pytest.raises(AppException):
            query.taskbooks_page(user, 1, 20)

        # 学院角色缺学院 claim 的既有语义是 SQL false()：返回 0 条，不能猜测可见范围。
        no_scope_user = _ctx("COLLEGE_ADMIN")
        missing_scope = {**no_scope_user, "graduationBatchId": str(batch_id), "batchId": str(batch_id)}
        for fn in (query.taskbooks_page, query.midterms_page, query.grades_page):
            page = fn(missing_scope, 1, 20)
            assert page["total"] == 0
            assert page["items"] == []
            assert page["hasMore"] is False
    finally:
        _clear_ctx()
