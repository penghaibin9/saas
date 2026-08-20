"""D-W3 evaluation full-read data-scope contracts."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

TID = 1000000000000000001


def _seed_scope_fixture():
    from app.db.session import get_sessionmaker
    from app.models import (
        AaCourse,
        AaEvaluationBatch,
        AaEvaluationRecord,
        AaEvaluationResult,
        AaEvaluationTask,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        College,
    )

    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID, year_code="2036-2037", term_no=1,
            term_name="D-W3评教范围学期", teaching_weeks=18,
            status="PUBLISHED", is_current=False,
        )
        db.add(term); db.flush()
        college_a = College(tenant_id=TID, college_name="D-W3范围学院A", code="DW3-SCOPE-A", status="ACTIVE")
        college_b = College(tenant_id=TID, college_name="D-W3范围学院B", code="DW3-SCOPE-B", status="ACTIVE")
        db.add_all([college_a, college_b]); db.flush()
        batch_a = AaTeachingTaskBatch(
            tenant_id=TID, term_id=term.id, batch_name="D-W3学院A教学任务",
            college_id=college_a.id, status="APPROVED",
        )
        batch_b = AaTeachingTaskBatch(
            tenant_id=TID, term_id=term.id, batch_name="D-W3学院B教学任务",
            college_id=college_b.id, status="APPROVED",
        )
        db.add_all([batch_a, batch_b]); db.flush()
        course_a = AaCourse(tenant_id=TID, course_code="DW3-SCOPE-CA", course_name="D-W3范围课程A", credit=2, status="ENABLED")
        course_b = AaCourse(tenant_id=TID, course_code="DW3-SCOPE-CB", course_name="D-W3范围课程B", credit=2, status="ENABLED")
        db.add_all([course_a, course_b]); db.flush()
        teaching_a = AaTeachingTask(
            tenant_id=TID, batch_id=batch_a.id, course_id=course_a.id,
            course_code=course_a.course_code, course_name=course_a.course_name,
            teacher_key="dw3_scope_teacher_a", teacher_name="D-W3范围教师A",
            status="READY", weekly_hours=2, total_hours=36, start_week=1, end_week=18,
        )
        teaching_b = AaTeachingTask(
            tenant_id=TID, batch_id=batch_b.id, course_id=course_b.id,
            course_code=course_b.course_code, course_name=course_b.course_name,
            teacher_key="dw3_scope_teacher_b", teacher_name="D-W3范围教师B",
            status="READY", weekly_hours=2, total_hours=36, start_week=1, end_week=18,
        )
        db.add_all([teaching_a, teaching_b]); db.flush()
        evaluation_batch = AaEvaluationBatch(
            tenant_id=TID, batch_name="D-W3跨学院评教批次", term_id=term.id,
            anonymous=True, status="RESULT_READY",
        )
        foreign_batch = AaEvaluationBatch(
            tenant_id=TID, batch_name="D-W3纯外院评教批次", term_id=term.id,
            anonymous=True, status="RESULT_READY",
        )
        db.add_all([evaluation_batch, foreign_batch]); db.flush()
        eval_task_a = AaEvaluationTask(
            tenant_id=TID, batch_id=evaluation_batch.id, teaching_task_id=teaching_a.id,
            course_id=course_a.id, course_name=course_a.course_name,
            teacher_key=teaching_a.teacher_key, teacher_name=teaching_a.teacher_name,
            evaluator_type="STUDENT", submitted_count=10, status="PENDING",
        )
        eval_task_b = AaEvaluationTask(
            tenant_id=TID, batch_id=evaluation_batch.id, teaching_task_id=teaching_b.id,
            course_id=course_b.id, course_name=course_b.course_name,
            teacher_key=teaching_b.teacher_key, teacher_name=teaching_b.teacher_name,
            evaluator_type="STUDENT", submitted_count=20, status="PENDING",
        )
        foreign_task = AaEvaluationTask(
            tenant_id=TID, batch_id=foreign_batch.id, teaching_task_id=teaching_b.id,
            course_id=course_b.id, course_name=course_b.course_name,
            teacher_key=teaching_b.teacher_key, teacher_name=teaching_b.teacher_name,
            evaluator_type="STUDENT", submitted_count=5, status="PENDING",
        )
        db.add_all([eval_task_a, eval_task_b, foreign_task]); db.flush()

        # OPEN-window participation now comes from active answer facts. Keep this scope fixture
        # internally consistent with the result/student-count projections instead of relying on
        # the legacy AaEvaluationTask.submitted_count field as a second live authority.
        for task, count, score in (
            (eval_task_a, 10, 91),
            (eval_task_b, 20, 72),
            (foreign_task, 5, 66),
        ):
            for index in range(count):
                db.add(AaEvaluationRecord(
                    tenant_id=TID,
                    batch_id=task.batch_id,
                    task_id=task.id,
                    teacher_key=task.teacher_key,
                    evaluator_type="STUDENT",
                    answers_json=f'{{"scopeFixture":{index}}}',
                    objective_score=score,
                ))

        db.add_all([
            AaEvaluationResult(
                tenant_id=TID, batch_id=evaluation_batch.id, teaching_task_id=teaching_a.id,
                teacher_key=teaching_a.teacher_key, teacher_name=teaching_a.teacher_name,
                course_name=course_a.course_name, student_avg=91, student_count=10,
                composite_score=91, level="EXCELLENT", published=True,
            ),
            AaEvaluationResult(
                tenant_id=TID, batch_id=evaluation_batch.id, teaching_task_id=teaching_b.id,
                teacher_key=teaching_b.teacher_key, teacher_name=teaching_b.teacher_name,
                course_name=course_b.course_name, student_avg=72, student_count=20,
                composite_score=72, level="PASS", published=True,
            ),
            AaEvaluationResult(
                tenant_id=TID, batch_id=foreign_batch.id, teaching_task_id=teaching_b.id,
                teacher_key=teaching_b.teacher_key, teacher_name=teaching_b.teacher_name,
                course_name=course_b.course_name, student_avg=66, student_count=5,
                composite_score=66, level="PASS", published=True,
            ),
        ])
        db.commit()
        return {
            "collegeA": int(college_a.id), "batch": int(evaluation_batch.id),
            "foreignBatch": int(foreign_batch.id), "taskA": int(eval_task_a.id), "taskB": int(eval_task_b.id),
        }
    finally:
        db.close()


def _ctx(scope_type, college_ids=()):
    return SimpleNamespace(scope_type=scope_type, college_ids=set(college_ids))


@pytest.mark.usefixtures("db_mode")
def test_teacher_owner_scope_limits_full_management_reads(monkeypatch):
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services import academic_affairs_evaluation_scale_service as scale
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as public

    ids = _seed_scope_fixture()
    set_tenant({"tenantId": str(TID)})
    monkeypatch.setattr(scale, "build_affairs_context", lambda _user, _db: _ctx("NONE"))
    monkeypatch.setattr(scale, "_derive_keys", lambda _user: {"dw3_scope_teacher_a"})
    user = {"currentRoleCode": "ACADEMIC_TEACHER", "loginName": "dw3_scope_teacher_a", "userType": "TEACHER"}
    try:
        batches, total = public.list_batches(user, page=1, page_size=20)
        assert total == 1
        assert [int(row["batchId"]) for row in batches] == [ids["batch"]]
        assert int(public.get_batch(user, ids["batch"])["batchId"]) == ids["batch"]
        assert [int(row["taskId"]) for row in public.list_tasks(user, ids["batch"])] == [ids["taskA"]]
        results, total = public.list_results(user, ids["batch"], mine=False, page=1, page_size=50)
        assert total == 1
        assert [row["teacherName"] for row in results] == ["D-W3范围教师A"]
        summary = public.stats(user, ids["batch"])
        assert summary["resultCount"] == 1
        assert summary["overallAvg"] == 91.0
        assert summary["participation"]["STUDENT"] == {"total": 1, "submitted": 1, "rate": 100.0}
        with pytest.raises(Exception) as exc:
            public.get_batch(user, ids["foreignBatch"])
        assert getattr(exc.value, "http_status", None) == 403
    finally:
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_teacher_owner_cannot_read_result_before_formal_publication(monkeypatch):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaEvaluationResult
    from app.modules.academic_affairs.services import academic_affairs_evaluation_scale_service as scale
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as public

    ids = _seed_scope_fixture()
    db = get_sessionmaker()()
    try:
        row = db.query(AaEvaluationResult).filter(
            AaEvaluationResult.tenant_id == TID,
            AaEvaluationResult.batch_id == ids["batch"],
            AaEvaluationResult.teacher_key == "dw3_scope_teacher_a",
            AaEvaluationResult.is_deleted.is_(False),
        ).one()
        row.published = False
        db.commit()
    finally:
        db.close()

    set_tenant({"tenantId": str(TID)})
    monkeypatch.setattr(scale, "build_affairs_context", lambda _user, _db: _ctx("NONE"))
    monkeypatch.setattr(scale, "_derive_keys", lambda _user: {"dw3_scope_teacher_a"})
    user = {"currentRoleCode": "ACADEMIC_TEACHER", "loginName": "dw3_scope_teacher_a", "userType": "TEACHER"}
    try:
        results, total = public.list_results(user, ids["batch"], mine=False, page=1, page_size=50)
        assert results == [] and total == 0
        summary = public.stats(user, ids["batch"])
        assert summary["resultCount"] == 0
        assert summary["overallAvg"] is None
        assert summary["byLevel"] == {}
        # Participation may remain visible for the teacher's own task; score/result truth may not.
        assert summary["participation"]["STUDENT"] == {"total": 1, "submitted": 1, "rate": 100.0}
    finally:
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_college_scope_filters_tasks_results_stats_and_export(monkeypatch):
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services import academic_affairs_evaluation_scale_service as scale
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as public
    from app.services import xlsx_util

    ids = _seed_scope_fixture()
    set_tenant({"tenantId": str(TID)})
    monkeypatch.setattr(scale, "build_affairs_context", lambda _user, _db: _ctx("COLLEGE", {ids["collegeA"]}))
    monkeypatch.setattr(scale._legacy, "_audit", lambda *_args, **_kwargs: None)
    captured = {}

    def _capture_xlsx(title, headers, rows, **kwargs):
        captured["rows"] = list(rows)
        return b"xlsx-scope-ok"

    monkeypatch.setattr(xlsx_util, "build_ledger_xlsx", _capture_xlsx)
    user = {"currentRoleCode": "COLLEGE_ADMIN", "loginName": "dw3_college_a"}
    try:
        assert [int(row["taskId"]) for row in public.list_tasks(user, ids["batch"])] == [ids["taskA"]]
        results, total = public.list_results(user, ids["batch"], mine=False, page=1, page_size=50)
        assert total == 1 and results[0]["courseName"] == "D-W3范围课程A"
        summary = public.stats(user, ids["batch"])
        assert summary["resultCount"] == 1 and summary["byLevel"] == {"EXCELLENT": 1}
        assert public.export_evaluation_xlsx(user, ids["batch"], "results", "学院教学质量复核") == b"xlsx-scope-ok"
        assert len(captured["rows"]) == 1
        assert captured["rows"][0][0] == "D-W3范围教师A"
        assert all("D-W3范围教师B" not in str(value) for row in captured["rows"] for value in row)
    finally:
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_tenant_all_keeps_full_management_visibility(monkeypatch):
    from app.core.context import set_tenant
    from app.modules.academic_affairs.services import academic_affairs_evaluation_scale_service as scale
    from app.modules.academic_affairs.services import academic_affairs_evaluation_public_service as public

    ids = _seed_scope_fixture()
    set_tenant({"tenantId": str(TID)})
    monkeypatch.setattr(scale, "build_affairs_context", lambda _user, _db: _ctx("TENANT_ALL"))
    user = {"currentRoleCode": "SCHOOL_ADMIN", "loginName": "school_admin01"}
    try:
        assert {int(row["taskId"]) for row in public.list_tasks(user, ids["batch"])} == {ids["taskA"], ids["taskB"]}
        results, total = public.list_results(user, ids["batch"], mine=False, page=1, page_size=50)
        assert total == 2
        assert {row["teacherName"] for row in results} == {"D-W3范围教师A", "D-W3范围教师B"}
        summary = public.stats(user, ids["batch"])
        assert summary["resultCount"] == 2 and summary["overallAvg"] == 81.5
    finally:
        set_tenant(None)
