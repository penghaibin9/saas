"""sandbox-school 低风险关系回填。

只修可以由现有一对一权威来源无歧义推导的字段/流水：
- 课堂考勤 <- roster consumer snapshot 的 teaching_task_id；
- 已发布课表 <- batch.publish_at 的发布流水补录。
- 在途调停课 <- 单据状态、组织责任人和原课位共同重建审批实例/任务/待办。

不在这里改写已发布/已归档课表、不伪造成绩来源、不覆盖用户正在编辑的排课草稿。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, text

from app.core.tenant_scoped import tenant_get


_ACTIVE_CHANGE_STATUSES = ("SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW")


def _rebase_schedule_change_origins(db, tenant_id: int) -> dict:
    """Rebind a stale in-flight request only to one exact active-scope item."""
    from app.models import (
        AaScheduleBatch, AaScheduleChange, AaScheduleItem, AaScheduleScopeHead,
        AffairsAuditTrail,
    )

    rows = list(db.scalars(select(AaScheduleChange).where(
        AaScheduleChange.tenant_id == tenant_id,
        AaScheduleChange.status.in_(_ACTIVE_CHANGE_STATUSES),
        AaScheduleChange.is_deleted.is_(False),
    ).order_by(AaScheduleChange.id)).all())
    repaired = 0
    ambiguous = []
    for change in rows:
        batch = db.get(AaScheduleBatch, int(change.batch_id or 0))
        if not batch or batch.is_deleted:
            continue
        scope_type = "COLLEGE" if batch.college_id else "SCHOOL"
        scope_id = int(batch.college_id or 0)
        head = db.scalars(select(AaScheduleScopeHead).where(
            AaScheduleScopeHead.tenant_id == tenant_id,
            AaScheduleScopeHead.term_id == int(change.term_id or batch.term_id),
            AaScheduleScopeHead.scope_type == scope_type,
            AaScheduleScopeHead.scope_id == scope_id,
            AaScheduleScopeHead.is_deleted.is_(False),
        )).first()
        if head and int(head.active_batch_id or 0) == int(change.batch_id or 0) and batch.status == "PUBLISHED":
            continue
        if not head or not head.active_batch_id:
            ambiguous.append(int(change.id))
            continue
        candidates = list(db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == tenant_id,
            AaScheduleItem.batch_id == int(head.active_batch_id),
            AaScheduleItem.task_id == change.task_id,
            AaScheduleItem.class_id == change.class_id,
            AaScheduleItem.teacher_key == change.teacher_key,
            AaScheduleItem.weekday == change.origin_weekday,
            AaScheduleItem.slot_no == change.origin_slot_no,
            AaScheduleItem.start_week == change.origin_start_week,
            AaScheduleItem.end_week == change.origin_end_week,
            AaScheduleItem.week_parity == change.origin_week_parity,
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.is_deleted.is_(False),
        ).order_by(AaScheduleItem.id).limit(2)).all())
        if len(candidates) != 1:
            ambiguous.append(int(change.id))
            continue
        origin = candidates[0]
        old_batch_id, old_item_id = change.batch_id, change.origin_item_id
        change.batch_id = int(head.active_batch_id)
        change.origin_item_id = int(origin.id)
        change.origin_classroom = origin.classroom_text
        change.version = int(change.version or 0) + 1
        db.add(AffairsAuditTrail(
            tenant_id=tenant_id,
            biz_type="AA_SCHEDULE_CHANGE",
            biz_id=int(change.id),
            action="REBASE_ACTIVE_SCOPE",
            operator="sandbox 关系闭包修复器",
            role_name="SYSTEM",
            detail=(f"batch {old_batch_id}->{change.batch_id}; "
                    f"originItem {old_item_id}->{change.origin_item_id}"),
            occurred_at=datetime.utcnow(),
        ))
        repaired += 1
    return {"repaired": repaired, "ambiguousChangeIds": ambiguous}


def _repair_applied_partial_schedule_changes(db, tenant_id: int) -> dict:
    """Restore residual weeks lost by the historical whole-row CHANGED behavior."""
    from app.models import AaScheduleChange, AaScheduleItem, AffairsAuditTrail

    changes = list(db.scalars(select(AaScheduleChange).where(
        AaScheduleChange.tenant_id == tenant_id,
        AaScheduleChange.change_type == "ADJUST",
        AaScheduleChange.status == "APPLIED",
        AaScheduleChange.is_deleted.is_(False),
    ).order_by(AaScheduleChange.id)).all())
    inserted = 0
    repaired_changes = []
    for change in changes:
        origin = tenant_get(
            db, AaScheduleItem, int(change.origin_item_id or 0), tenant_id=tenant_id
        )
        if not origin or origin.is_deleted or origin.status != "CHANGED":
            continue
        start_week = int(change.target_start_week or origin.start_week)
        end_week = int(change.target_end_week or origin.end_week)
        if start_week <= int(origin.start_week) and end_week >= int(origin.end_week):
            continue
        expected = []
        if int(origin.start_week) < start_week:
            expected.append((int(origin.start_week), start_week - 1, str(origin.week_parity or "ALL")))
        if end_week < int(origin.end_week):
            expected.append((end_week + 1, int(origin.end_week), str(origin.week_parity or "ALL")))
        origin_parity = str(origin.week_parity or "ALL").upper()
        target_parity = str(change.target_week_parity or "ALL").upper()
        if origin_parity == "ALL" and target_parity in {"ODD", "EVEN"}:
            expected.append((start_week, end_week, "EVEN" if target_parity == "ODD" else "ODD"))
        change_inserted = 0
        for residual_start, residual_end, residual_parity in expected:
            exists = db.scalars(select(AaScheduleItem.id).where(
                AaScheduleItem.tenant_id == tenant_id,
                AaScheduleItem.batch_id == origin.batch_id,
                AaScheduleItem.task_id == origin.task_id,
                AaScheduleItem.change_id.is_(None),
                AaScheduleItem.weekday == origin.weekday,
                AaScheduleItem.slot_no == origin.slot_no,
                AaScheduleItem.start_week == residual_start,
                AaScheduleItem.end_week == residual_end,
                AaScheduleItem.week_parity == residual_parity,
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.is_deleted.is_(False),
            )).first()
            if exists:
                continue
            db.add(AaScheduleItem(
                tenant_id=tenant_id, batch_id=origin.batch_id, task_id=origin.task_id,
                course_id=origin.course_id, course_name=origin.course_name,
                class_id=origin.class_id, class_name=origin.class_name,
                teacher_key=origin.teacher_key, teacher_name=origin.teacher_name,
                weekday=origin.weekday, slot_no=origin.slot_no,
                start_week=residual_start, end_week=residual_end, week_parity=residual_parity,
                classroom_id=origin.classroom_id, classroom_text=origin.classroom_text,
                source=origin.source, change_id=None, status="EFFECTIVE",
            ))
            inserted += 1
            change_inserted += 1
        if change_inserted:
            repaired_changes.append(int(change.id))
            db.add(AffairsAuditTrail(
                tenant_id=tenant_id, biz_type="AA_SCHEDULE_CHANGE", biz_id=int(change.id),
                action="REPAIR_PARTIAL_RESIDUALS", operator="sandbox 关系闭包修复器",
                role_name="SYSTEM", detail=f"insertedResidualItems={change_inserted}",
                occurred_at=datetime.utcnow(),
            ))
    return {"insertedResidualItems": inserted, "changeIds": repaired_changes}


def _normalize_partial_residual_change_links(db, tenant_id: int) -> dict:
    """Remove target-only change_id from already-created residual source segments."""
    from app.models import AaScheduleChange, AaScheduleItem

    updated = 0
    changes = list(db.scalars(select(AaScheduleChange).where(
        AaScheduleChange.tenant_id == tenant_id,
        AaScheduleChange.change_type == "ADJUST",
        AaScheduleChange.status == "APPLIED",
        AaScheduleChange.is_deleted.is_(False),
    )).all())
    for change in changes:
        origin = db.get(AaScheduleItem, int(change.origin_item_id or 0))
        if not origin:
            continue
        for item in db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == tenant_id,
            AaScheduleItem.change_id == int(change.id),
            AaScheduleItem.id != int(change.new_item_id or 0),
            AaScheduleItem.batch_id == origin.batch_id,
            AaScheduleItem.task_id == origin.task_id,
            AaScheduleItem.weekday == origin.weekday,
            AaScheduleItem.slot_no == origin.slot_no,
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.is_deleted.is_(False),
        )).all():
            item.change_id = None
            updated += 1
    return {"updated": updated}


def _dedupe_partial_residual_items(db, tenant_id: int) -> dict:
    """Soft-delete exact duplicate residual patterns created by earlier repair retries."""
    rows = list(db.execute(text("""
        SELECT batch_id,task_id,weekday,slot_no,start_week,end_week,week_parity,
               MIN(id) keep_id,COUNT(*) row_count
          FROM t_aa_schedule_item
         WHERE tenant_id=:tenant_id AND is_deleted=0 AND status='EFFECTIVE' AND change_id IS NULL
         GROUP BY batch_id,task_id,weekday,slot_no,start_week,end_week,week_parity
        HAVING COUNT(*)>1
    """), {"tenant_id": tenant_id}).mappings())
    removed = 0
    for row in rows:
        result = db.execute(text("""
            UPDATE t_aa_schedule_item
               SET is_deleted=1,status='CANCELLED',updated_at=:updated_at
             WHERE tenant_id=:tenant_id AND is_deleted=0 AND status='EFFECTIVE'
               AND change_id IS NULL AND batch_id=:batch_id AND task_id=:task_id
               AND weekday=:weekday AND slot_no=:slot_no AND start_week=:start_week
               AND end_week=:end_week AND week_parity=:week_parity AND id<>:keep_id
        """), {**dict(row), "tenant_id": tenant_id, "updated_at": datetime.utcnow()})
        removed += int(result.rowcount or 0)
    return {"softDeleted": removed}


def _schedule_change_workflow_preview(db, tenant_id: int) -> dict:
    row = db.execute(text("""
        SELECT COUNT(*) active_changes,
               SUM(c.workflow_instance_id IS NULL OR w.id IS NULL) missing_workflow,
               SUM((c.status='SUBMITTED' AND c.current_node<>'COLLEGE_REVIEW')
                   OR (c.status IN ('COLLEGE_REVIEW','ACADEMIC_REVIEW')
                       AND c.current_node<>'ACADEMIC_REVIEW')) node_mismatch
          FROM t_aa_schedule_change c
          LEFT JOIN t_workflow_instance w
            ON w.id=c.workflow_instance_id AND w.tenant_id=c.tenant_id AND w.is_deleted=0
           AND w.source_module='academic-affairs' AND w.source_biz_type='AA_SCHEDULE_CHANGE'
           AND w.source_biz_id=c.id
         WHERE c.tenant_id=:tenant_id AND c.is_deleted=0
           AND c.status IN ('SUBMITTED','COLLEGE_REVIEW','ACADEMIC_REVIEW')
    """), {"tenant_id": tenant_id}).mappings().one()
    return {
        "active": int(row["active_changes"] or 0),
        "missingWorkflow": int(row["missing_workflow"] or 0),
        "nodeMismatch": int(row["node_mismatch"] or 0),
    }


def _approval_identity(db, tenant_id: int, change, node: str) -> int:
    from app.models import College, Major, SchoolClass, StaffAssignment, User

    if node == "COLLEGE_REVIEW":
        school_class = db.get(SchoolClass, int(change.class_id or 0))
        major = db.get(Major, int(school_class.major_id or 0)) if school_class else None
        college = db.get(College, int(major.college_id or 0)) if major else None
        user_id = int(college.secretary_id or 0) if college else 0
    else:
        reviewers = list(db.scalars(select(StaffAssignment.user_id).where(
            StaffAssignment.tenant_id == tenant_id,
            StaffAssignment.org_type == "SCHOOL",
            StaffAssignment.org_node_id == tenant_id,
            StaffAssignment.assignment_type == "ACADEMIC_REVIEWER",
            StaffAssignment.status == "ACTIVE",
            StaffAssignment.is_deleted.is_(False),
            StaffAssignment.effective_at <= datetime.utcnow(),
        )).all())
        user_id = int(reviewers[0]) if len({int(value) for value in reviewers}) == 1 else 0
    user = db.get(User, user_id) if user_id else None
    if not user or user.tenant_id != tenant_id or user.is_deleted or user.status != "ACTIVE":
        raise RuntimeError(f"调停课 {change.id} 的 {node} 没有唯一有效受理人")
    return int(user.id)


def _repair_schedule_change_workflows(db, tenant_id: int) -> dict:
    from app.models import (
        AaScheduleChange, AffairsAuditTrail, UnifiedTodo, WorkflowInstance, WorkflowTask,
    )

    rows = list(db.scalars(select(AaScheduleChange).where(
        AaScheduleChange.tenant_id == tenant_id,
        AaScheduleChange.status.in_(_ACTIVE_CHANGE_STATUSES),
        AaScheduleChange.is_deleted.is_(False),
    ).order_by(AaScheduleChange.id)).all())
    repaired = 0
    for change in rows:
        existing = db.get(WorkflowInstance, int(change.workflow_instance_id or 0))
        if existing and not existing.is_deleted:
            continue
        current_node = "COLLEGE_REVIEW" if change.status == "SUBMITTED" else "ACADEMIC_REVIEW"
        applicant_id = int(change.applicant_id or 0)
        if applicant_id <= 0:
            raise RuntimeError(f"调停课 {change.id} 缺少真实申请人，拒绝伪造审批链")
        inst = WorkflowInstance(
            tenant_id=tenant_id,
            workflow_code="ACAD_SCHEDULE_CHANGE",
            source_module="academic-affairs",
            source_biz_type="AA_SCHEDULE_CHANGE",
            source_biz_id=int(change.id),
            applicant_id=applicant_id,
            title=f"{change.teacher_name or ''} 调停课：{change.course_name or ''}",
            status="RUNNING",
            current_node=current_node,
            remark="sandbox 关系闭包：依据既有单据状态补建缺失审批链",
        )
        db.add(inst)
        db.flush()

        # COLLEGE_REVIEW 状态表示学院步骤已经完成；保留一个已办任务作为可追溯证据，
        # 当前待办从 ACADEMIC_REVIEW 开始。SUBMITTED 则只创建学院待办。
        if current_node == "ACADEMIC_REVIEW":
            college_assignee = _approval_identity(db, tenant_id, change, "COLLEGE_REVIEW")
            db.add(WorkflowTask(
                tenant_id=tenant_id,
                instance_id=int(inst.id),
                node_code="COLLEGE_REVIEW",
                assignee_id=college_assignee,
                status="APPROVED",
                acted_at=change.updated_at or change.created_at or datetime.utcnow(),
                remark="依据既有 COLLEGE_REVIEW 单据状态重建已办节点",
            ))
        assignee_id = _approval_identity(db, tenant_id, change, current_node)
        db.add(WorkflowTask(
            tenant_id=tenant_id,
            instance_id=int(inst.id),
            node_code=current_node,
            assignee_id=assignee_id,
            status="PENDING",
            remark="sandbox 关系闭包重建的当前审批任务",
        ))
        db.add(UnifiedTodo(
            tenant_id=tenant_id,
            source_module="academic-affairs",
            source_biz_type="AA_SCHEDULE_CHANGE",
            source_biz_id=int(change.id),
            todo_type="AA_SCHEDULE_CHANGE_APPROVAL",
            assignee_id=assignee_id,
            title=f"调停课待审批：{change.course_name or ''}",
            status="PENDING",
            remark=current_node,
        ))
        change.workflow_instance_id = int(inst.id)
        change.current_node = current_node
        change.version = int(change.version or 0) + 1
        db.add(AffairsAuditTrail(
            tenant_id=tenant_id,
            biz_type="AA_SCHEDULE_CHANGE",
            biz_id=int(change.id),
            action="RECONCILE_WORKFLOW",
            operator="sandbox 关系闭包修复器",
            role_name="SYSTEM",
            detail=f"status={change.status}; currentNode={current_node}; assigneeId={assignee_id}",
            occurred_at=datetime.utcnow(),
        ))
        repaired += 1
    return {"repaired": repaired}


def preview_sandbox_relationship_reconcile(db, tenant_id: int) -> dict:
    attendance = db.execute(text("""
        SELECT COUNT(*) total,
               SUM(a.teaching_task_id IS NULL) missing_task,
               SUM(x.cnt=1 AND t.id IS NOT NULL) unambiguous,
               SUM(x.cnt IS NULL) no_snapshot,
               SUM(x.cnt>1) ambiguous
          FROM t_aa_attendance_session a
          LEFT JOIN (
              SELECT consumer_id,MIN(teaching_task_id) teaching_task_id,COUNT(*) cnt
                FROM t_aa_roster_consumer_snapshot
               WHERE tenant_id=:tenant_id AND is_deleted=0 AND consumer_type='ATTENDANCE_SESSION'
               GROUP BY consumer_id
          ) x ON x.consumer_id=a.id
          LEFT JOIN t_aa_teaching_task t ON t.id=x.teaching_task_id
           AND t.tenant_id=a.tenant_id AND t.is_deleted=0
         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0
    """), {"tenant_id": tenant_id}).mappings().one()
    missing_publish = int(db.execute(text("""
        SELECT COUNT(*) FROM t_aa_schedule_batch b
         WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 AND b.status='PUBLISHED'
           AND NOT EXISTS (
               SELECT 1 FROM t_aa_schedule_publish p
                WHERE p.tenant_id=b.tenant_id AND p.batch_id=b.id AND p.is_deleted=0
           )
    """), {"tenant_id": tenant_id}).scalar() or 0)
    missing_task = int(attendance["missing_task"] or 0)
    legacy_formal_source = int(db.execute(text("""
        SELECT COUNT(*) FROM t_aa_attendance_session
         WHERE tenant_id=:tenant_id AND is_deleted=0
           AND teaching_task_id IS NOT NULL
           AND occurrence_identity IS NOT NULL
           AND COALESCE(source_evidence,'')<>''
           AND source_type='PUBLISHED_SCHEDULE'
    """), {"tenant_id": tenant_id}).scalar() or 0)
    return {
        "tenantId": str(tenant_id),
        "attendance": {
            "total": int(attendance["total"] or 0),
            "missingTeachingTask": missing_task,
            "unambiguousSnapshot": int(attendance["unambiguous"] or 0),
            "noSnapshot": int(attendance["no_snapshot"] or 0),
            "ambiguous": int(attendance["ambiguous"] or 0),
            "safeToRepair": missing_task > 0
            and int(attendance["unambiguous"] or 0) == int(attendance["total"] or 0),
            "legacyFormalSourceEnum": legacy_formal_source,
        },
        "missingSchedulePublishLedgers": missing_publish,
        "scheduleChangeWorkflow": _schedule_change_workflow_preview(db, tenant_id),
        "scheduleChangeActiveScope": {
            "stale": int(db.execute(text("""
                SELECT COUNT(*) FROM t_aa_schedule_change c
                JOIN t_aa_schedule_batch b ON b.id=c.batch_id AND b.tenant_id=c.tenant_id AND b.is_deleted=0
                LEFT JOIN t_aa_schedule_scope_head h
                  ON h.tenant_id=c.tenant_id AND h.term_id=c.term_id AND h.is_deleted=0
                 AND h.scope_type=CASE WHEN b.college_id IS NULL THEN 'SCHOOL' ELSE 'COLLEGE' END
                 AND h.scope_id=COALESCE(b.college_id,0)
               WHERE c.tenant_id=:tenant_id AND c.is_deleted=0
                 AND c.status IN ('SUBMITTED','COLLEGE_REVIEW','ACADEMIC_REVIEW')
                 AND (b.status<>'PUBLISHED' OR h.id IS NULL OR h.active_batch_id<>c.batch_id)
            """), {"tenant_id": tenant_id}).scalar() or 0),
        },
    }


def reconcile_sandbox_relationships(db, tenant_id: int) -> dict:
    from app.models import AaScheduleBatch, AaSchedulePublish, Tenant

    tenant = db.get(Tenant, tenant_id)
    if tenant is None or str(tenant.tenant_code or "") != "sandbox-school":
        raise RuntimeError(f"只允许修复 sandbox-school，实际 tenant_id={tenant_id}")

    from app.services.sandbox_school_role_reconcile import ensure_school_approval_responsibilities
    from app.services.sandbox_school_role_scope_reconcile import (
        reconcile_sandbox_role_assignment_scopes,
    )

    approval_responsibilities = ensure_school_approval_responsibilities(db, tenant_id)
    role_assignment_scopes = reconcile_sandbox_role_assignment_scopes(db, tenant_id)
    preview = preview_sandbox_relationship_reconcile(db, tenant_id)
    attendance = preview["attendance"]
    if attendance["missingTeachingTask"] and not attendance["safeToRepair"]:
        raise RuntimeError(f"课堂考勤来源存在歧义，拒绝自动回填: {attendance}")

    attendance_updated = 0
    if attendance["missingTeachingTask"]:
        result = db.execute(text("""
            UPDATE t_aa_attendance_session a
            JOIN t_aa_roster_consumer_snapshot s
              ON s.tenant_id=a.tenant_id AND s.consumer_type='ATTENDANCE_SESSION'
             AND s.consumer_id=a.id AND s.is_deleted=0
            JOIN t_aa_teaching_task t
              ON t.id=s.teaching_task_id AND t.tenant_id=a.tenant_id AND t.is_deleted=0
               SET a.teaching_task_id=s.teaching_task_id,
                   a.occurrence_identity=CONCAT('TASK',CHAR(58),s.teaching_task_id,CHAR(58),
                                                a.session_date,CHAR(58),'S',COALESCE(a.slot_no,0)),
                   a.source_type='FORMAL_TEACHING',
                   a.source_reason='sandbox relationship closure backfill from roster snapshot',
                   a.source_evidence=CONCAT('{\"teachingTaskId\":\"',s.teaching_task_id,
                                            '\",\"rosterSnapshotId\":\"',s.id,'\"}')
             WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND a.teaching_task_id IS NULL
        """), {"tenant_id": tenant_id})
        attendance_updated = int(result.rowcount or 0)

    batches = list(db.scalars(select(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == tenant_id,
        AaScheduleBatch.status == "PUBLISHED",
        AaScheduleBatch.is_deleted.is_(False),
        ~AaScheduleBatch.id.in_(select(AaSchedulePublish.batch_id).where(
            AaSchedulePublish.tenant_id == tenant_id,
            AaSchedulePublish.is_deleted.is_(False),
        )),
    )).all())
    for batch in batches:
        teacher_count = int(db.execute(text("""
            SELECT COUNT(DISTINCT t.teacher_key)
              FROM t_aa_teaching_task t
              JOIN t_aa_teaching_task_batch b ON b.id=t.batch_id AND b.tenant_id=t.tenant_id AND b.is_deleted=0
             WHERE t.tenant_id=:tenant_id AND b.term_id=:term_id AND t.is_deleted=0
        """), {"tenant_id": tenant_id, "term_id": int(batch.term_id)}).scalar() or 0)
        db.add(AaSchedulePublish(
            tenant_id=tenant_id,
            batch_id=int(batch.id),
            term_id=int(batch.term_id) if batch.term_id is not None else None,
            action="PUBLISH",
            operator_name="sandbox 关系闭包修复器",
            notified_count=teacher_count,
            note="依据既有 PUBLISHED 批次与 publish_at 补录历史发布流水；未改写课位",
            created_at=batch.publish_at,
            updated_at=batch.publish_at,
        ))
    attendance_source_result = db.execute(text("""
        UPDATE t_aa_attendance_session a
        JOIN t_aa_teaching_task t
          ON t.id=a.teaching_task_id AND t.tenant_id=a.tenant_id AND t.is_deleted=0
           SET a.source_type='FORMAL_TEACHING',
               a.updated_at=:updated_at
         WHERE a.tenant_id=:tenant_id AND a.is_deleted=0
           AND a.teaching_task_id IS NOT NULL
           AND a.occurrence_identity IS NOT NULL
           AND COALESCE(a.source_evidence,'')<>''
           AND a.source_type='PUBLISHED_SCHEDULE'
    """), {"tenant_id": tenant_id, "updated_at": datetime.utcnow()})
    schedule_change_active_scope = _rebase_schedule_change_origins(db, tenant_id)
    residual_change_links = _normalize_partial_residual_change_links(db, tenant_id)
    db.flush()
    residual_duplicates = _dedupe_partial_residual_items(db, tenant_id)
    db.flush()
    schedule_change_partial_residuals = _repair_applied_partial_schedule_changes(db, tenant_id)
    schedule_change_workflow = _repair_schedule_change_workflows(db, tenant_id)
    db.commit()
    return {
        "preview": preview,
        "approvalResponsibilities": approval_responsibilities,
        "roleAssignmentScopes": role_assignment_scopes,
        "attendanceUpdated": attendance_updated,
        "attendanceSourceTypesNormalized": int(attendance_source_result.rowcount or 0),
        "schedulePublishLedgersInserted": len(batches),
        "scheduleChangeWorkflow": schedule_change_workflow,
        "scheduleChangeActiveScope": schedule_change_active_scope,
        "scheduleChangePartialResiduals": schedule_change_partial_residuals,
        "scheduleChangeResidualLinks": residual_change_links,
        "scheduleChangeResidualDuplicates": residual_duplicates,
    }
