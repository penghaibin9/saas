"""Graduation grade appeal exact-evidence binding and SQL paging hardening."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, or_, select
from app.core.exceptions import AppException, not_found
from app.models import GraduationAuditTrail, GraduationGrade, GraduationGradeAppeal, GraduationStudent
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_release_hardening_common import _student_scope_select


def _install_grade_appeal_hardening() -> None:
    from app.modules.graduation.services import graduation_more_service as more
    from app.modules.graduation.services import graduation_grade_appeal_consistency as appeal_consistency
    def create_appeal(gd_student_id, reason):
        reason = str(reason or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "申诉理由必填且不少于 5 字")
        with session() as db:
            student = db.scalars(select(GraduationStudent).where(
                GraduationStudent.id == int(gd_student_id), GraduationStudent.tenant_id == _tid(),
                GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
            ).with_for_update()).first()
            if not student:
                raise not_found("毕设学生不存在")
            grade_row = db.scalars(select(GraduationGrade).where(
                GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == student.id,
                GraduationGrade.is_deleted.is_(False),
            ).with_for_update()).first()
            if not grade_row or grade_row.status != "PUBLISHED":
                raise AppException("DATA_CONFLICT", "成绩未发布，暂不可申诉")
            pending = int(db.scalar(select(func.count()).select_from(GraduationGradeAppeal).where(
                GraduationGradeAppeal.tenant_id == _tid(), GraduationGradeAppeal.gd_student_id == student.id,
                GraduationGradeAppeal.status == "PENDING", GraduationGradeAppeal.is_deleted.is_(False),
            )) or 0)
            if pending:
                raise AppException("DATA_CONFLICT", "已有待复核的申诉，请等待处理")
            appeal = GraduationGradeAppeal(tenant_id=_tid(), gd_student_id=student.id, reason=reason,
                                            status="PENDING", active_key=f"pending:{student.id}")
            db.add(appeal); db.flush()
            snapshot = {
                "gradeId": int(grade_row.id), "gradeVersion": int(grade_row.version or 0),
                "sourceSnapshotHash": grade_row.source_snapshot_hash or "",
                "totalScore": float(grade_row.total_score or 0), "publishedAt": _iso(grade_row.published_at),
            }
            db.add(GraduationAuditTrail(
                tenant_id=_tid(), biz_type="GRADE_APPEAL_SNAPSHOT", biz_id=str(appeal.id),
                action="BIND_GRADE_VERSION", detail="成绩申诉绑定已发布成绩版本",
                after_json=snapshot, occurred_at=datetime.now(timezone.utc),
            ))
            more._audit(db, "GRADE_APPEAL", appeal.id, "提交成绩申诉", student.name)
            db.commit()
            return more._appeal_row(db, appeal)

    def review_appeal(appeal_id, action, comment=None):
        action = str(action or "").upper(); note = str(comment or "").strip()
        if action not in {"APPROVE", "REJECT"}: raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
        if action == "REJECT" and len(note) < 5: raise AppException("VALIDATION_ERROR", "驳回申诉理由必填且不少于 5 字")
        with session() as db:
            appeal = db.scalars(select(GraduationGradeAppeal).where(GraduationGradeAppeal.id == int(appeal_id), GraduationGradeAppeal.tenant_id == _tid(), GraduationGradeAppeal.is_deleted.is_(False)).with_for_update()).first()
            if not appeal: raise not_found("申诉不存在")
            if appeal.status != "PENDING": raise AppException("DATA_CONFLICT", "该申诉已复核，请刷新")
            student = db.scalars(select(GraduationStudent).where(GraduationStudent.id == appeal.gd_student_id, GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE").with_for_update()).first()
            if not student: raise not_found("申诉对应的毕业设计学生不存在")
            from app.modules.graduation.services import graduation_scope_service as scope
            scope.assert_student_access(db, student, "grade.appeal.review")
            snap_row = db.scalars(select(GraduationAuditTrail).where(GraduationAuditTrail.tenant_id == _tid(), GraduationAuditTrail.biz_type == "GRADE_APPEAL_SNAPSHOT", GraduationAuditTrail.biz_id == str(appeal.id), GraduationAuditTrail.action == "BIND_GRADE_VERSION").order_by(GraduationAuditTrail.id.desc()).limit(1)).first()
            snap = (snap_row.after_json if snap_row else None) or {}
            if not snap: raise AppException("DATA_CONFLICT", "历史申诉缺少成绩版本快照，请重新发起申诉")
            grade_row = db.scalars(select(GraduationGrade).where(GraduationGrade.tenant_id == _tid(), GraduationGrade.gd_student_id == student.id, GraduationGrade.is_deleted.is_(False)).with_for_update()).first()
            current = {"gradeId": int(grade_row.id) if grade_row else None, "gradeVersion": int(grade_row.version or 0) if grade_row else None, "sourceSnapshotHash": grade_row.source_snapshot_hash or "" if grade_row else "", "totalScore": float(grade_row.total_score or 0) if grade_row else None, "publishedAt": _iso(grade_row.published_at) if grade_row else None}
            expected = {k: snap.get(k) for k in current}
            if not grade_row or grade_row.status != "PUBLISHED" or current != expected:
                raise AppException("DATA_CONFLICT", "成绩版本已变化，原申诉不得作用于新成绩，请重新申诉")
            operator, _ = more._op(); now = datetime.now(timezone.utc)
            appeal.status = "APPROVED" if action == "APPROVE" else "REJECTED"; appeal.active_key = None; appeal.review_comment = note or None; appeal.reviewed_by = operator; appeal.reviewed_at = now
            if action == "APPROVE":
                before = grade_row.status; grade_row.status = "WITHDRAWN"; grade_row.withdraw_reason = f"成绩申诉受理：{note or appeal.reason}"[:500]; grade_row.reviewed_at = None; grade_row.version = int(grade_row.version or 0) + 1
                if student.stage == "COMPLETED": student.stage = "DEFENSE"; student.version = int(student.version or 0) + 1
                more._audit(db, "GRADE", grade_row.id, "申诉受理后撤回成绩", grade_row.withdraw_reason)
                from app.modules.graduation.services.graduation_risk_service import notify_risk_rescan
                notify_risk_rescan(db, student.id)
                result_text = "成绩申诉已受理，原成绩已撤回并进入重新核算流程"
                transition = f"{before}->WITHDRAWN"
            else:
                result_text = f"成绩申诉未通过：{note}"
                transition = "UNCHANGED"
            outbox_id = None
            if student.student_id:
                from app.services import message_event_outbox_service as message_outbox
                event_code = appeal_consistency.GRADE_APPEAL_REVIEWED_EVENT
                outbox = message_outbox.emit_message_event(
                    db, event_code=event_code, source_module="graduation",
                    source_biz_type="grade_appeal", source_biz_id=int(appeal.id),
                    recipient_refs=[{"studentId": int(student.student_id)}],
                    title="毕业设计成绩申诉处理结果", content=result_text,
                    action_key="graduation.grade.view",
                    action_params={"gdStudentId": str(student.id), "batchId": str(student.batch_id)},
                    dedup_key=f"{event_code}:{appeal.id}:{appeal.status}",
                )
                outbox_id = str(outbox.id)
            more._audit(db, "GRADE_APPEAL", appeal.id, "复核申诉-" + ("受理" if action == "APPROVE" else "驳回"), f"{note};grade={transition};outbox={outbox_id or 'SKIPPED_NO_STUDENT_LINK'}")
            db.commit(); result = more._appeal_row(db, appeal); result.update({"gradeStatus": grade_row.status, "studentStage": student.stage, "notificationQueued": bool(outbox_id), "outboxId": outbox_id}); return result

    def list_appeals(page=1, page_size=20, status=None, keyword=None, batch_id=None):
        with session() as db:
            scope_q = _student_scope_select(db, _tid(), batch_id=batch_id)
            filters = [GraduationGradeAppeal.tenant_id == _tid(), GraduationGradeAppeal.is_deleted.is_(False), GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE", GraduationStudent.id.in_(scope_q)]
            if status: filters.append(GraduationGradeAppeal.status == status)
            if batch_id not in (None, ""): filters.append(GraduationStudent.batch_id == int(batch_id))
            if keyword:
                value = f"%{str(keyword).strip()}%"
                filters.append(or_(GraduationStudent.name.like(value), GraduationStudent.student_no.like(value), GraduationGradeAppeal.reason.like(value)))
            base = select(GraduationGradeAppeal, GraduationStudent).join(GraduationStudent, GraduationStudent.id == GraduationGradeAppeal.gd_student_id).where(*filters)
            total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)
            size = min(200, max(1, int(page_size)))
            rows = db.execute(base.order_by(GraduationGradeAppeal.id.desc()).offset((max(1, int(page)) - 1) * size).limit(size)).all()
            return [{"id": str(a.id), "gdStudentId": str(a.gd_student_id), "studentName": stu.name, "studentNo": stu.student_no or "", "reason": a.reason, "status": a.status, "statusLabel": more.APPEAL_LABEL.get(a.status, a.status), "reviewComment": a.review_comment or "", "reviewedBy": a.reviewed_by or "", "reviewedAt": _iso(a.reviewed_at), "createdAt": _iso(a.created_at)} for a, stu in rows], total

    more.create_appeal = create_appeal
    more.review_appeal = review_appeal
    appeal_consistency.review_appeal = review_appeal
    more.list_appeals = list_appeals
