"""学工中心核心审计安全门。

只收紧已经确认的跨端/跨模块缺陷，不改其他业务域：
- 学生工作台关怀数量必须来自真实本人在办风险，禁止假零；
- 困难认定批量学生查询必须带租户与软删除条件；
- 学生申请金额/家庭经济数字在进入 MySQL 前校验 DECIMAL(14,2) 上限；
- 辅导员交接只能迁移 student-affairs 待办，且按完整业务键去重；
- 学生画像只展示当前在住房、未关闭心理关注，并按动态权限裁剪敏感摘要；
- 风险转办/升级/接管/重开/跟进必须留下可审计依据；
- 辅导员考评按数据范围查看/评分，发布仅限全域且所有记录已评分。

本模块在 api/v1/router.py 的既有四端兼容层之后安装，幂等执行。
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select

from app.core.exceptions import AppException, no_data_scope, not_found
from app.core.permissions import has_permission
from app.services.db_service import _tid, session

_INSTALLED = False
_MAX_DECIMAL_14_2 = Decimal("999999999999.99")


def _patch_student_overview() -> None:
    from app.models import AffairsRiskRecord
    from app.services import mobile_affairs_service as affairs

    previous = affairs.overview_my

    def overview_my(user):
        data = dict(previous(user) or {})
        with session() as db:
            student = affairs._me(db, user)
            care_count = db.scalar(select(func.count()).select_from(AffairsRiskRecord).where(
                AffairsRiskRecord.tenant_id == _tid(),
                AffairsRiskRecord.student_id == int(student.id),
                AffairsRiskRecord.status != "CLOSED",
                AffairsRiskRecord.is_deleted.is_(False),
            )) or 0
        data.pop("riskOpen", None)
        data["careActionCount"] = int(care_count)
        return data

    affairs.overview_my = overview_my


def _patch_decimal_boundaries() -> None:
    from app.services import affairs_student_atomic_service as atomic

    def optional_non_negative_decimal(value, field_name: str):
        if value in (None, ""):
            return None
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise AppException("VALIDATION_ERROR", f"{field_name}格式非法") from exc
        if not result.is_finite():
            raise AppException("VALIDATION_ERROR", f"{field_name}格式非法")
        if result < 0:
            raise AppException("VALIDATION_ERROR", f"{field_name}不能小于0")
        if result > _MAX_DECIMAL_14_2:
            raise AppException("VALIDATION_ERROR", f"{field_name}不能超过999999999999.99")
        if result.as_tuple().exponent < -2:
            raise AppException("VALIDATION_ERROR", f"{field_name}最多保留2位小数")
        return result

    atomic._optional_non_negative_decimal = optional_non_negative_decimal


def _patch_aid_student_batch_lookup() -> None:
    from app.models import StudentProfile
    from app.services import affairs_aid_service as aid

    def students_by_ids(db, rows, attr="student_id"):
        ids = {int(getattr(row, attr)) for row in rows if getattr(row, attr, None)}
        if not ids:
            return {}
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.id.in_(ids),
            StudentProfile.is_deleted.is_(False),
        )).all()
        return {int(student.id): student for student in students}

    aid._students_by_ids = students_by_ids


def _patch_counselor_handover() -> None:
    from app.services import affairs_counselor_service as counselor

    def migrate_class_work(db, class_id, from_user_id, to_user_id, reason: str) -> dict:
        from app.models import (
            AffairsRiskRecord,
            CsLeave,
            UnifiedTodo,
            WorkflowInstance,
            WorkflowTask,
        )

        from_uid, to_uid = int(from_user_id), int(to_user_id)
        if from_uid == to_uid:
            return {"todos": 0, "workflowTasks": 0, "risks": 0}
        student_ids = counselor._class_student_ids(db, class_id)
        if not student_ids:
            return {"todos": 0, "workflowTasks": 0, "risks": 0}

        moved_todos = 0
        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.assignee_id == from_uid,
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.student_id.in_(student_ids),
            UnifiedTodo.is_deleted.is_(False),
        )).all()
        for todo in todos:
            clash = db.scalars(select(UnifiedTodo).where(
                UnifiedTodo.tenant_id == _tid(),
                UnifiedTodo.source_module == todo.source_module,
                UnifiedTodo.source_biz_type == todo.source_biz_type,
                UnifiedTodo.source_biz_id == todo.source_biz_id,
                UnifiedTodo.todo_type == todo.todo_type,
                UnifiedTodo.assignee_id == to_uid,
                UnifiedTodo.is_deleted.is_(False),
            )).first()
            if clash:
                clash.status = "PENDING"
                clash.title = todo.title
                clash.version = int(clash.version or 0) + 1
                todo.status = "CANCELLED"
                todo.remark = ((todo.remark or "") + f"|交接取消→{to_uid}")[:500]
                todo.version = int(todo.version or 0) + 1
            else:
                todo.assignee_id = to_uid
                todo.remark = ((todo.remark or "") + f"|交接自{from_uid}:{reason}")[:500]
                todo.version = int(todo.version or 0) + 1
            moved_todos += 1

        leave_ids = set(db.scalars(select(CsLeave.id).where(
            CsLeave.tenant_id == _tid(),
            CsLeave.student_id.in_(student_ids),
            CsLeave.is_deleted.is_(False),
        )).all())
        moved_tasks = 0
        if leave_ids:
            tasks = db.scalars(select(WorkflowTask).where(
                WorkflowTask.tenant_id == _tid(),
                WorkflowTask.assignee_id == from_uid,
                WorkflowTask.status == "PENDING",
                WorkflowTask.is_deleted.is_(False),
            )).all()
            for task in tasks:
                instance = db.get(WorkflowInstance, int(task.instance_id)) if task.instance_id else None
                if not instance or (instance.source_module or "").replace("_", "-") != "student-affairs":
                    continue
                if (instance.source_biz_type or "").upper() != "LEAVE":
                    continue
                if int(instance.source_biz_id or 0) not in leave_ids:
                    continue
                task.assignee_id = to_uid
                task.version = int(task.version or 0) + 1
                moved_tasks += 1

        moved_risks = 0
        risks = db.scalars(select(AffairsRiskRecord).where(
            AffairsRiskRecord.tenant_id == _tid(),
            AffairsRiskRecord.owner_id == from_uid,
            AffairsRiskRecord.student_id.in_(student_ids),
            AffairsRiskRecord.status != "CLOSED",
            AffairsRiskRecord.is_deleted.is_(False),
        )).all()
        for risk in risks:
            risk.owner_id = to_uid
            risk.version = int(risk.version or 0) + 1
            moved_risks += 1

        return {"todos": moved_todos, "workflowTasks": moved_tasks, "risks": moved_risks}

    counselor._migrate_class_work = migrate_class_work


def _patch_student_profile() -> None:
    from app.models import AffairsRiskRecord, DisciplineCase, DormBed, DormBuilding, DormRoom
    from app.services import affairs_profile_service as profile

    original_profile = profile.get_profile
    original_timeline = profile.get_timeline

    def get_profile(student_id, user):
        data = dict(original_profile(student_id, user) or {})
        sid = int(student_id)
        with session() as db:
            # 当前宿舍只能来自 OCCUPIED 床位，不能把已退宿历史床位当成当前入住。
            bed = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(),
                DormBed.student_id == sid,
                DormBed.status == "OCCUPIED",
                DormBed.is_deleted.is_(False),
            ).order_by(DormBed.id.desc())).first()
            dorm_summary = {"hasDorm": False, "text": ""}
            if bed and bed.room_id:
                room = db.get(DormRoom, int(bed.room_id))
                if room and not room.is_deleted and room.tenant_id == _tid():
                    building = db.get(DormBuilding, int(room.building_id)) if room.building_id else None
                    if building and (building.is_deleted or building.tenant_id != _tid()):
                        building = None
                    parts = []
                    if building and building.building_name:
                        parts.append(building.building_name)
                    if room.room_no:
                        parts.append(str(room.room_no))
                    if bed.bed_no:
                        parts.append(f"{bed.bed_no}床")
                    dorm_summary = {"hasDorm": True, "text": " · ".join(parts) if parts else "已入住"}
            data["dormSummary"] = dorm_summary

            open_mental = db.scalar(select(func.count()).select_from(AffairsRiskRecord).where(
                AffairsRiskRecord.tenant_id == _tid(),
                AffairsRiskRecord.student_id == sid,
                AffairsRiskRecord.source == "MENTAL",
                AffairsRiskRecord.status != "CLOSED",
                AffairsRiskRecord.is_deleted.is_(False),
            )) or 0
            data["psyFlag"] = "需关注" if open_mental else "无"

            if has_permission(user, "studentAffairs.discipline.view"):
                active = db.scalar(select(func.count()).select_from(DisciplineCase).where(
                    DisciplineCase.tenant_id == _tid(),
                    DisciplineCase.student_id == sid,
                    DisciplineCase.status == "EFFECTIVE",
                    DisciplineCase.is_deleted.is_(False),
                )) or 0
                data["disciplineSummary"] = {"activeCount": int(active)}
            else:
                data["disciplineSummary"] = {"activeCount": None, "restricted": True}
        return data

    module_permissions = {
        "leave": "studentAffairs.leave.view",
        "aid": "studentAffairs.aid.view",
        "funding": "studentAffairs.funding.view",
        "discipline": "studentAffairs.discipline.view",
        "risk": "studentAffairs.risk.view",
        "talk": "studentAffairs.talk.view",
    }

    def get_timeline(student_id, user, event_type=None, page=1, page_size=20):
        items, total = original_timeline(student_id, user, event_type, page, page_size)
        for item in items:
            permission = module_permissions.get(item.get("module"))
            if permission and not has_permission(user, permission):
                item["title"] = "受限学工事件"
                item["detail"] = "当前角色无权查看该业务事件内容"
                item["restricted"] = True
        return items, total

    profile.get_profile = get_profile
    profile.get_timeline = get_timeline


def _require_text(value, label: str, minimum: int = 5, maximum: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) < minimum or len(text) > maximum:
        raise AppException("VALIDATION_ERROR", f"{label}需{minimum}-{maximum}字")
    return text


def _patch_risk_audit_evidence() -> None:
    from app.services import affairs_risk_service as risk

    previous_message = risk._msg
    previous_follow = risk.follow
    previous_transfer = risk.transfer
    previous_escalate = risk.escalate
    previous_takeover = risk.takeover
    previous_reopen = risk.reopen

    def message(db, receiver_id, title, content, mtype, risk_id):
        try:
            receiver = int(receiver_id or 0)
        except (TypeError, ValueError):
            receiver = 0
        if receiver <= 0:
            return
        return previous_message(db, receiver, title, content, mtype, risk_id)

    def follow(risk_id, user, content="", expected_version=None):
        return previous_follow(risk_id, user, _require_text(content, "跟进记录"), expected_version)

    def transfer(risk_id, user, new_owner_id, reason="", expected_version=None):
        return previous_transfer(risk_id, user, new_owner_id, _require_text(reason, "转办原因"), expected_version)

    def escalate(risk_id, user, reason="", expected_version=None):
        return previous_escalate(risk_id, user, _require_text(reason, "升级依据"), expected_version)

    def takeover(risk_id, user, content="", expected_version=None):
        return previous_takeover(risk_id, user, _require_text(content, "接管说明"), expected_version)

    def reopen(risk_id, user, reason="", expected_version=None):
        return previous_reopen(risk_id, user, _require_text(reason, "重开原因"), expected_version)

    risk._msg = message
    risk.follow = follow
    risk.transfer = transfer
    risk.escalate = escalate
    risk.takeover = takeover
    risk.reopen = reopen


def _patch_counselor_evaluation() -> None:
    from app.models import (
        AffairsCounselorAssessment,
        AffairsCounselorAssessmentPeriod,
        SchoolClass,
    )
    from app.services import affairs_class_service as classes

    original_collect = classes.collect_assessments
    original_list = classes.list_assessments
    original_score = classes.score_assessment
    original_publish = classes.publish_period

    def allowed_counselors(db, user):
        allowed, _scope = classes._allowed_class_ids(db, user)
        if allowed is None:
            return None
        return set(int(value) for value in db.scalars(select(SchoolClass.counselor_id).where(
            SchoolClass.tenant_id == _tid(),
            SchoolClass.id.in_(allowed or {-1}),
            SchoolClass.counselor_id.is_not(None),
            SchoolClass.is_deleted.is_(False),
        )).all())

    def collect_assessments(period_id, user, expected_version=None):
        # 旧接口未传 version 时使用服务端刚读取的版本做 CAS，仍能保证并发只成功一次；
        # 新客户端传 version 时继续执行严格的客户端乐观锁。
        if expected_version is None:
            with session() as db:
                period = db.get(AffairsCounselorAssessmentPeriod, int(period_id))
                if not period or period.is_deleted or period.tenant_id != _tid():
                    raise not_found("考评周期不存在")
                expected_version = int(period.version or 0)
        return original_collect(period_id, user, expected_version)

    def list_assessments(period_id, user):
        rows = original_list(period_id, user)
        with session() as db:
            permitted = allowed_counselors(db, user)
        if permitted is None:
            return rows
        return [row for row in rows if str(row.get("counselorId") or "").isdigit()
                and int(row["counselorId"]) in permitted]

    def score_assessment(assessment_id, user, college_score, expected_version=None):
        with session() as db:
            assessment = db.get(AffairsCounselorAssessment, int(assessment_id))
            if not assessment or assessment.is_deleted or assessment.tenant_id != _tid():
                raise not_found("考评记录不存在")
            permitted = allowed_counselors(db, user)
            if permitted is not None and int(assessment.counselor_id or 0) not in permitted:
                raise no_data_scope("该辅导员不在您的学院或班级数据范围内")
        return original_score(assessment_id, user, college_score, expected_version)

    def publish_period(period_id, user, expected_version=None):
        from app.core.affairs_security import build_affairs_context
        with session() as db:
            context = build_affairs_context(user, db)
            if context.scope_type != "TENANT_ALL":
                raise AppException("NO_PERMISSION", "仅学校/学工处全域管理员可发布全校辅导员考评")
            period = db.get(AffairsCounselorAssessmentPeriod, int(period_id))
            if not period or period.is_deleted or period.tenant_id != _tid():
                raise not_found("考评周期不存在")
            rows = db.scalars(select(AffairsCounselorAssessment).where(
                AffairsCounselorAssessment.tenant_id == _tid(),
                AffairsCounselorAssessment.period_id == int(period_id),
                AffairsCounselorAssessment.is_deleted.is_(False),
            )).all()
            if not rows:
                raise AppException("DATA_CONFLICT", "考评周期尚未生成任何辅导员记录")
            pending = [row for row in rows if row.status != "SCORED" or row.college_score is None]
            if pending:
                raise AppException("DATA_CONFLICT", f"仍有{len(pending)}名辅导员未完成学院评分，不能发布")
        return original_publish(period_id, user, expected_version)

    classes.collect_assessments = collect_assessments
    classes.list_assessments = list_assessments
    classes.score_assessment = score_assessment
    classes.publish_period = publish_period


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_student_overview()
    _patch_decimal_boundaries()
    _patch_aid_student_batch_lookup()
    _patch_counselor_handover()
    _patch_student_profile()
    _patch_risk_audit_evidence()
    _patch_counselor_evaluation()
    _INSTALLED = True
