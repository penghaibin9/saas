"""文档 2 R0 第①步：学院教务、校领导的权限变化必须经发布模板生效（隔离 MySQL）。

覆盖：新岗位有发布版本；旧的宽松校领导版本被追加的新版本取代且旧版本不被改写；
发布后实际解析出的权限收窄；可按模板服务的回滚草稿恢复上一版。
"""
import pytest
from sqlalchemy import select

from app.core import permissions as perms
from app.services import system_role_shadow_service as shadow

_ACADEMIC_LEADER = {
    "academicAffairs.dashboard.view", "academicAffairs.stats.view",
    "academicAffairs.stats.snapshot.view",
}


def _published(db, role_code):
    from app.models.permission_governance import RoleTemplate

    return db.scalars(select(RoleTemplate).where(
        RoleTemplate.tenant_id == 0,
        RoleTemplate.template_code == role_code,
        RoleTemplate.publish_status == "PUBLISHED",
        RoleTemplate.is_deleted.is_(False),
    ).order_by(RoleTemplate.template_version.desc())).first()


def _template_codes(db, template_id):
    from app.models.permission_governance import RoleTemplatePermission

    return {row.permission_code for row in db.scalars(select(RoleTemplatePermission).where(
        RoleTemplatePermission.role_template_id == int(template_id),
        RoleTemplatePermission.is_deleted.is_(False),
    )).all()}


def test_college_academic_has_a_published_template_matching_code(db_mode):
    from app.db.session import get_sessionmaker

    shadow.converge_published_system_templates(actor_user_id=9811, source_commit_sha="r0-step1-head")
    db = get_sessionmaker()()
    try:
        assert set(shadow.published_system_role_permissions(db, "COLLEGE_ACADEMIC")) == set(
            shadow.expected_system_role_permissions("COLLEGE_ACADEMIC"))
        leader = set(shadow.published_system_role_permissions(db, "LEADER"))
        assert {code for code in leader if code.startswith("academicAffairs.")} == _ACADEMIC_LEADER
        from app.models import Role

        role = Role(tenant_id=1000000000000000001, role_code="COLLEGE_ACADEMIC",
                    role_name="学院教务", role_type="SYSTEM", status="ACTIVE")
        db.add(role)
        db.commit()
        actor = {"userId": "9811", "tenantId": str(role.tenant_id), "userType": "TEACHER",
                 "currentRoleCode": role.role_code, "activeContextId": f"role:{role.id}"}
        assert perms.has_permission(actor, "academicAffairs.teachingTask.assign")
        assert perms.has_permission(actor, "student.profile.update")
        for code in ("academicAffairs.grade.collegeReview", "academicAffairs.grade.publish",
                     "academicAffairs.roster.export", "student.profile.restore"):
            assert not perms.has_permission(actor, code)
    finally:
        db.close()


@pytest.fixture
def r0_teacher_schedule(db_mode):
    """隔离库的本院/外院同教师课表，直接造查询夹具，不冒充业务流程验收。"""
    from app.core.context import get_tenant, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaScheduleBatch, AaScheduleItem, AaScheduleScopeHead,
                            AaTeachingClass, AaTeachingClassTeacher, AaTeachingTask,
                            AaTeachingTaskBatch, AaTerm, College, TeacherStudentScope)

    tid = 1000000000000000001
    old_tenant = get_tenant()
    set_tenant({"tenantId": str(tid)})
    try:
        with get_sessionmaker()() as db:
            colleges = [College(tenant_id=tid, college_name=f"R0学院{i}", status="ACTIVE") for i in (1, 2)]
            db.add_all(colleges)
            term = AaTerm(tenant_id=tid, year_code="2098-2099", term_no=1,
                          term_name="R0测试学期", teaching_weeks=18, is_current=True, status="PUBLISHED")
            db.add(term)
            db.flush()
            own, other = [int(row.id) for row in colleges]
            batch = AaScheduleBatch(tenant_id=tid, term_id=term.id, batch_name="R0全校课表", status="PUBLISHED")
            db.add(batch)
            db.flush()
            db.add(AaScheduleScopeHead(tenant_id=tid, term_id=term.id, scope_type="SCHOOL",
                                      scope_id=0, active_batch_id=batch.id))
            for role in ("COLLEGE_ACADEMIC", "COLLEGE_ADMIN"):
                db.add(TeacherStudentScope(tenant_id=tid, teacher_key="r0-college",
                    teacher_name="R0本院教务", role_code=role, scope_type="COLLEGE",
                    ref_value=colleges[0].college_name, status="ACTIVE"))
            item_ids = {}
            task_ids = {}
            # 同一教师跨院授课；课程归属应覆盖冲突的批次归属，缺开课单位时才退到批次。
            cases = [("own", own, other, tid, False), ("other", other, own, tid, False),
                     ("fallback", None, own, tid, False), ("unknown", None, None, tid, False),
                     ("foreign", own, own, tid + 1, False), ("deleted", own, own, tid, True)]
            for index, (name, owner, batch_owner, task_tid, deleted) in enumerate(cases, 1):
                course = AaCourse(tenant_id=task_tid, course_code=f"R0-{name}", course_name=name,
                                  owner_college_id=owner, status="ENABLED")
                task_batch = AaTeachingTaskBatch(tenant_id=task_tid, term_id=term.id,
                    batch_name=f"R0-{name}", college_id=batch_owner, status="APPROVED")
                db.add_all([course, task_batch])
                db.flush()
                task = AaTeachingTask(tenant_id=task_tid, batch_id=task_batch.id, course_id=course.id,
                                      teacher_key="r0-shared", status="READY", is_deleted=deleted)
                db.add(task)
                db.flush()
                task_ids[name] = int(task.id)
                item = AaScheduleItem(tenant_id=tid, batch_id=batch.id, task_id=task.id,
                    course_id=course.id, course_name=name, teacher_key="r0-shared", teacher_name="R0教师",
                    weekday=1, slot_no=index, start_week=1, end_week=18, status="EFFECTIVE")
                db.add(item)
                if name in ("own", "other"):
                    teaching_class = AaTeachingClass(tenant_id=tid, teaching_task_id=task.id,
                        term_id=term.id, course_id=course.id, class_code=f"R0-{name}", class_name=name)
                    db.add(teaching_class)
                    db.flush()
                    db.add(AaTeachingClassTeacher(tenant_id=tid, teaching_class_id=teaching_class.id,
                        teacher_key="r0-shared", start_week=3, end_week=8, status="ACTIVE"))
                    item.teacher_key = "stale-teacher"
                db.flush()
                item_ids[name] = str(item.id)
            orphan = AaScheduleItem(tenant_id=tid, batch_id=batch.id, teacher_key="r0-shared",
                                    weekday=2, slot_no=1, start_week=1, end_week=18)
            db.add(orphan)
            other_batch = AaScheduleBatch(tenant_id=tid, term_id=term.id,
                batch_name="R0纯外院课表", college_id=other, status="PUBLISHED")
            db.add(other_batch)
            db.flush()
            db.add(AaScheduleScopeHead(tenant_id=tid, term_id=term.id, scope_type="COLLEGE",
                                      scope_id=other, active_batch_id=other_batch.id))
            db.add(AaScheduleItem(tenant_id=tid, batch_id=other_batch.id, task_id=task_ids["other"],
                                 teacher_key="r0-shared", weekday=3, slot_no=1, start_week=1, end_week=18))
            db.commit()
            ids = {"batch": int(batch.id), "other_batch": int(other_batch.id),
                   "term": int(term.id), "items": item_ids}
        yield ids
    finally:
        set_tenant(old_tenant)


@pytest.mark.parametrize("entry", ["teacher_view", "teacher_schedule"])
def test_teacher_schedule_keeps_own_college_and_rejects_foreign_or_unresolved_rows(r0_teacher_schedule, entry):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as schedule

    ids = r0_teacher_schedule

    def read(actor, key="r0-shared"):
        if entry == "teacher_view":
            return schedule.teacher_view(ids["batch"], actor, key)
        return schedule.teacher_schedule(actor, key, ids["term"])

    for role in ("COLLEGE_ACADEMIC", "COLLEGE_ADMIN"):
        actor = {"userId": "r0-college", "loginName": "r0-college", "userType": "TEACHER",
                 "currentRoleCode": role, "collegeIds": [999], "dataScope": "SCHOOL"}
        result = read(actor)
        assert {row["itemId"] for row in result["items"]} == {ids["items"]["own"], ids["items"]["fallback"]}
        formal = next(row for row in result["items"] if row["itemId"] == ids["items"]["own"])
        assert (formal["startWeek"], formal["endWeek"]) == (3, 8)
        if entry == "teacher_schedule":
            assert result["weeklyHours"] == 2
            assert result["batchIds"] == [str(ids["batch"])]
        with pytest.raises(AppException) as exc:
            read({**actor, "userId": "unscoped", "loginName": "unscoped"})
        assert exc.value.code == "NO_DATA_SCOPE"

    teacher = {"userId": "r0-shared", "loginName": "r0-shared", "userType": "TEACHER",
               "currentRoleCode": "ACADEMIC_TEACHER"}
    assert {ids["items"]["own"], ids["items"]["other"]} <= {row["itemId"] for row in read(teacher)["items"]}
    with pytest.raises(AppException):
        read(teacher, "another-teacher")
    admin = {**teacher, "currentRoleCode": "ACADEMIC_ADMIN"}
    assert ids["items"]["other"] in {row["itemId"] for row in read(admin)["items"]}
    if entry == "teacher_schedule":
        assert set(read(admin)["batchIds"]) == {str(ids["batch"]), str(ids["other_batch"])}


def test_wide_leader_version_is_superseded_by_append_only_publish_and_can_roll_back(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.modules.system_admin.services import role_template_service as templates

    narrowed = set(perms.ROLE_PERMISSIONS["LEADER"])
    # 模拟 R0 之前已发布的宽松校领导模板（*.view + *.stat）。
    monkeypatch.setitem(perms.ROLE_PERMISSIONS, "LEADER", {"audit.view", "*.view", "*.stat", *perms._WORKBENCH_SELF})
    shadow.converge_published_system_templates(actor_user_id=9812, source_commit_sha="r0-before-head")
    db = get_sessionmaker()()
    try:
        wide = _published(db, "LEADER")
        wide_id, wide_version = int(wide.id), int(wide.template_version)
        wide_codes = _template_codes(db, wide_id)
        assert "academicAffairs.roster.view" in wide_codes
    finally:
        db.close()

    monkeypatch.setitem(perms.ROLE_PERMISSIONS, "LEADER", narrowed)
    result = shadow.converge_published_system_templates(actor_user_id=9812, source_commit_sha="r0-step1-head")
    assert "LEADER" in {item["roleCode"] for item in result["created"]}
    db = get_sessionmaker()()
    try:
        current = _published(db, "LEADER")
        assert int(current.template_version) == wide_version + 1
        assert _template_codes(db, wide_id) == wide_codes  # 旧版本只读保留
        resolved = set(shadow.published_system_role_permissions(db, "LEADER"))
        assert "academicAffairs.roster.view" not in resolved
        assert {code for code in resolved if code.startswith("academicAffairs.")} == _ACADEMIC_LEADER
    finally:
        db.close()

    # 恢复路径：用上一版生成回滚草稿并正式发布。
    draft = templates.create_rollback_draft(
        wide_id, change_reason="R0 验收：回滚到收窄前版本", actor_user_id=9812,
    )
    templates.publish_draft(int(draft["id"]), expected_version=int(draft["version"]), actor_user_id=9812)
    db = get_sessionmaker()()
    try:
        restored = _published(db, "LEADER")
        assert int(restored.template_version) == wide_version + 2
        assert set(shadow.published_system_role_permissions(db, "LEADER")) == wide_codes
        assert _template_codes(db, wide_id) == wide_codes
    finally:
        db.close()


def test_legacy_template_new_or_modified_permissions_are_still_rejected(db_mode):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate
    from app.modules.system_admin.services import role_template_service as templates

    with get_sessionmaker()() as db:
        source = _published(db, "LEADER")
        source_id = int(source.id)
        source_digest = source.permission_digest
        codes = _template_codes(db, source_id)
        other_id = int(_published(db, "SYS_ADMIN").id)
    assert any(code.startswith("system.") for code in codes)
    assert "academicAffairs.grade.publish" not in codes
    canonical_draft = templates.create_draft(template_code="LEADER", template_name="校领导",
        permission_codes=sorted(_ACADEMIC_LEADER), change_reason="验证未发布版本不能成为回滚来源", actor_user_id=9813)
    with get_sessionmaker()() as db:
        before_count = db.query(RoleTemplate).count()
    with pytest.raises(AppException) as exc:
        templates.create_draft(template_code="LEADER", template_name="校领导",
            permission_codes=sorted(codes), change_reason="普通新增仍然禁止历史权限码", actor_user_id=9813)
    assert exc.value.code == "LEGACY_PERMISSION_WRITE_FORBIDDEN"
    candidates = [
        (None, codes, source_digest),
        (int(canonical_draft["id"]), codes, source_digest),
        (other_id, codes, source_digest),
        (source_id, codes | {"academicAffairs.grade.publish"}, source_digest),
        (source_id, codes - {"academicAffairs.dashboard.view"}, source_digest),
        (source_id, codes, "0" * 64),
    ]
    for source_template_id, candidate, digest in candidates:
        with pytest.raises(AppException) as exc:
            templates.create_draft(template_code="LEADER", template_name="校领导",
                permission_codes=sorted(candidate), change_reason="验证不能借回滚新增或篡改历史权限",
                actor_user_id=9813, source_template_id=source_template_id, rollback_source_digest=digest)
        assert exc.value.code in {"DATA_CONFLICT", "VALIDATION_ERROR"}
    with pytest.raises(AppException):
        templates.create_rollback_draft(int(canonical_draft["id"]), change_reason="草稿不能作为回滚来源",
                                        actor_user_id=9813)
    with get_sessionmaker()() as db:
        assert db.query(RoleTemplate).count() == before_count
        assert int(_published(db, "LEADER").id) == source_id
        assert _template_codes(db, source_id) == codes


@pytest.mark.parametrize("damage", [
    "candidate_add", "candidate_remove", "source_digest", "source_empty_digest",
    "source_permission", "source_rehashed", "source_deny",
])
def test_legacy_rollback_rechecks_source_and_candidate_before_publish(db_mode, damage):
    """只在隔离库模拟持久化篡改，证明发布前重验；不是业务状态造终态。"""
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate, RoleTemplatePermission
    from app.modules.system_admin.services import role_template_service as templates

    with get_sessionmaker()() as db:
        source = _published(db, "LEADER")
        source_id = int(source.id)
    draft = templates.create_rollback_draft(source_id, change_reason="验证回滚发布前的完整性校验", actor_user_id=9814)
    draft_id = int(draft["id"])
    with get_sessionmaker()() as db:
        if damage in {"source_digest", "source_empty_digest"}:
            db.get(RoleTemplate, source_id).permission_digest = "0" * 64 if damage == "source_digest" else ""
        elif damage in {"candidate_add", "source_deny"}:
            db.add(RoleTemplatePermission(tenant_id=0,
                role_template_id=draft_id if damage == "candidate_add" else source_id,
                permission_code="academicAffairs.grade.publish",
                effect="ALLOW" if damage == "candidate_add" else "DENY"))
        else:
            target_id = draft_id if damage == "candidate_remove" else source_id
            row = db.scalars(select(RoleTemplatePermission).where(
                RoleTemplatePermission.role_template_id == target_id,
                RoleTemplatePermission.permission_code == "academicAffairs.dashboard.view",
                RoleTemplatePermission.is_deleted.is_(False),
            )).one()
            row.is_deleted = True
        db.flush()
        if damage in {"candidate_add", "candidate_remove", "source_rehashed"}:
            target_id = source_id if damage == "source_rehashed" else draft_id
            db.get(RoleTemplate, target_id).permission_digest = templates._digest(_template_codes(db, target_id))
        db.commit()
    with pytest.raises(AppException) as exc:
        templates.publish_draft(draft_id, expected_version=int(draft["version"]), actor_user_id=9814)
    assert exc.value.code == "DATA_CONFLICT"
    with get_sessionmaker()() as db:
        assert db.get(RoleTemplate, draft_id).publish_status == "DRAFT"
        assert int(_published(db, "LEADER").id) == source_id


@pytest.mark.parametrize("damage", ["digest", "empty_digest", "deny"])
def test_legacy_rollback_rejects_corrupted_source_before_creating_draft(db_mode, damage):
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models.permission_governance import RoleTemplate, RoleTemplatePermission
    from app.modules.system_admin.services import role_template_service as templates

    with get_sessionmaker()() as db:
        source = _published(db, "LEADER")
        source_id = int(source.id)
        before_count = db.query(RoleTemplate).count()
        if damage == "deny":
            db.add(RoleTemplatePermission(tenant_id=0, role_template_id=source_id,
                                          permission_code="academicAffairs.grade.publish", effect="DENY"))
        else:
            source.permission_digest = "0" * 64 if damage == "digest" else ""
        db.commit()
    with pytest.raises(AppException) as exc:
        templates.create_rollback_draft(source_id, change_reason="拒绝已损坏的历史来源快照", actor_user_id=9815)
    assert exc.value.code == "DATA_CONFLICT"
    with get_sessionmaker()() as db:
        assert db.query(RoleTemplate).count() == before_count
