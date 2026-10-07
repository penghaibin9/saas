"""承接后的成绩责任和工作量：隔离 MySQL 正式范围与分页合同。"""
from types import SimpleNamespace

from tests.test_aa_task_source_review import _pair
from tests.test_aa_task_handoff_schedule_consumers import _handoff
from tests.test_aa_schedule import BASE, TID


def _workload_pair(client):
    from app.db.session import get_sessionmaker
    from app.models import Role, RolePermission
    from tests.support_academic_review_identity import _ensure_permission
    from tests.test_aa_schedule import _hdr
    facts = _pair(client)
    with get_sessionmaker()() as db:
        role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == "SCHOOL_ADMIN").one()
        permission = _ensure_permission(db, "academicAffairs.stats.view")
        if not db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
            db.add(RolePermission(tenant_id=TID, role_id=role.id,
                permission_id=permission.id, status="ACTIVE"))
        db.commit()
    facts["school"] = _hdr(client, "school_admin01")
    return facts


def test_workload_handoff_deduplicates_hours_before_paging_and_preserves_history(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask
    facts = _workload_pair(client)
    teacher = facts["tasks"][0]["teacherKey"]
    params = {"termId": facts["termId"], "collegeId": facts["tasks"][0]["collegeId"]}
    before = client.get(f"{BASE}/stats/workload", headers=facts["school"], params=params)
    assert before.status_code == 200, before.text
    row = next(row for row in before.json()["data"]["ranking"] if row["teacherKey"] == teacher)
    assert row["totalHours"] == 36 and row["taskCount"] == 2, row
    with get_sessionmaker()() as db:
        history = [(task.id, task.status, task.total_hours, task.source_program_course_id)
            for task in db.query(AaTeachingTask).filter(AaTeachingTask.id.in_(
                [int(facts["oldId"]), int(facts["newId"])] )).order_by(AaTeachingTask.id)]
    _handoff(facts)
    response = client.get(f"{BASE}/stats/workload", headers=facts["school"], params=params)
    assert response.status_code == 200, response.text
    row = next(row for row in response.json()["data"]["ranking"] if row["teacherKey"] == teacher)
    assert row["totalHours"] == 18 and row["taskCount"] == 1, row
    for page in (1, 2):
        response = client.get(f"{BASE}/stats/workload/detail", headers=facts["school"],
            params={**params, "teacherKey": teacher, "page": page, "pageSize": 1})
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["total"] == 1, data
        assert [item["taskId"] for item in data["items"]] == ([facts["oldId"]] if page == 1 else []), data
    with get_sessionmaker()() as db:
        after = [(task.id, task.status, task.total_hours, task.source_program_course_id)
            for task in db.query(AaTeachingTask).filter(AaTeachingTask.id.in_(
                [int(facts["oldId"]), int(facts["newId"])] )).order_by(AaTeachingTask.id)]
        assert after == history


def test_college_missing_grade_responsibility_only_requires_original(client, db_mode):
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaGradeTask, AaTerm
    from app.modules.academic_affairs.services import academic_affairs_flow_service as flow
    facts = _pair(client)
    _handoff(facts)
    previous = get_tenant(); set_tenant(TID)
    try:
        with get_sessionmaker()() as db:
            term = db.get(AaTerm, facts["termId"])
            ctx = SimpleNamespace(permission_codes={"academicAffairs.grade.view"})
            stage = flow._stage(8, term, status="NOT_STARTED", evidence={})
            missing = flow._with_missing_college_grade_tasks(db, term,
                int(facts["tasks"][0]["collegeId"]), ctx, stage)
            assert missing["evidence"]["missingGradeTaskCount"] == 1, missing
            assert missing["currentObject"]["id"] == facts["oldId"], missing
            db.add(AaGradeTask(tenant_id=TID, term_id=term.id,
                teaching_task_id=int(facts["oldId"]), status="PUBLISHED"))
            db.flush()
            assert flow._with_missing_college_grade_tasks(db, term,
                int(facts["tasks"][0]["collegeId"]), ctx, stage) is stage
            db.rollback()
    finally:
        set_tenant(previous)


def test_malformed_handoff_cannot_silently_disappear_from_workload(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTaskSourceHandoff
    facts = _workload_pair(client)
    _handoff(facts)
    with get_sessionmaker()() as db:
        relation = db.query(AaTeachingTaskSourceHandoff).filter(
            AaTeachingTaskSourceHandoff.tenant_id == TID,
            AaTeachingTaskSourceHandoff.successor_task_id == int(facts["newId"])).one()
        relation.successor_source_id += 1
        db.commit()
    response = client.get(f"{BASE}/stats/workload/detail", headers=facts["school"], params={
        "termId": facts["termId"], "collegeId": facts["tasks"][0]["collegeId"],
        "teacherKey": facts["tasks"][0]["teacherKey"], "pageSize": 1})
    assert response.status_code == 409, response.text
    assert "TASK_HANDOFF_REFERENCE_INVALID" in response.text
