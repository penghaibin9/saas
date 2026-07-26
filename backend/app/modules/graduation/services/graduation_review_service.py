"""毕业设计中心 · 查重记录 + 教师评阅服务。

查重：对齐老系统 t_gd_plagiarism 检测中/完成/失败语义 + 复查申请闭环。
教师评阅：独立评阅角色，SoD——评阅人不得是该生指导教师（对齐 CLAUDE.md §权限矩阵 SoD 冻结）。

隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (GraduationAuditTrail, GraduationFinal, GraduationPlagiarismCheck,
                        GraduationReview, GraduationStudent)
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import (
    accessible_student_ids, assert_student_access, has_full_scope)
from app.modules.graduation.policies import review_policy

PLAG_STATUS_LABEL = {"CHECKING": "检测中", "DONE": "已完成", "FAILED": "失败"}
REVIEW_STATUS_LABEL = {"ASSIGNED": "待评阅", "REVIEWING": "评阅中", "COMPLETED": "已完成", "RETURNED": "已退回"}
REVIEW_STATUS_TONE = {"ASSIGNED": "warning", "REVIEWING": "warning", "COMPLETED": "success", "RETURNED": "danger"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, biz_type, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                                occurred_at=datetime.now(timezone.utc)))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "review")


# ═══════════ 查重记录 ═══════════

def _plag_row(p: GraduationPlagiarismCheck, stu=None) -> dict:
    return {"id": str(p.id), "gdStudentId": str(p.gd_student_id), "gdFinalId": str(p.gd_final_id or ""),
            "recheckOfId": str(p.recheck_of_id) if getattr(p, "recheck_of_id", None) else None,
            "isRecheck": bool(getattr(p, "recheck_of_id", None)),
            "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
            "submitAt": _iso(p.submit_at), "status": p.status,
            "statusLabel": PLAG_STATUS_LABEL.get(p.status, p.status),
            "rate": p.rate or "", "reportUrl": p.report_url or "", "threshold": p.threshold,
            "overThreshold": p.over_threshold, "disputeReason": p.dispute_reason or "",
            "disputeStatus": p.dispute_status or "", "disputeComment": p.dispute_comment or "",
            "updatedAt": _iso(p.updated_at)}


def list_plagiarism(page: int, page_size: int, gd_student_id=None, status=None, batch_id=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationPlagiarismCheck).where(GraduationPlagiarismCheck.tenant_id == _tid(),
                                                     GraduationPlagiarismCheck.is_deleted.is_(False),
                                                     GraduationPlagiarismCheck.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationPlagiarismCheck.gd_student_id == int(gd_student_id))
        if batch_id:
            q = q.where(GraduationPlagiarismCheck.gd_student_id.in_(select(GraduationStudent.id).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
                GraduationStudent.is_deleted.is_(False))))
        if status:
            q = q.where(GraduationPlagiarismCheck.status == status)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationPlagiarismCheck.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [_plag_row(p, db.get(GraduationStudent, p.gd_student_id)) for p in rows]
        return items, total


def submit_plagiarism(gd_student_id, gd_final_id=None, threshold: int = 30) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        final_query = select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.gd_student_id == stu.id,
            GraduationFinal.is_deleted.is_(False),
        )
        if gd_final_id:
            final_query = final_query.where(GraduationFinal.id == int(gd_final_id))
        final = db.scalars(final_query.order_by(GraduationFinal.id.desc()).with_for_update()).first()
        if not final:
            raise AppException("DATA_CONFLICT", "请先提交需要检测的论文成果")
        if not (final.attachments_json or []):
            raise AppException("DATA_CONFLICT", "该成果没有可检测的论文附件")
        active = db.scalars(select(GraduationPlagiarismCheck).where(
            GraduationPlagiarismCheck.tenant_id == _tid(),
            GraduationPlagiarismCheck.gd_final_id == final.id,
            GraduationPlagiarismCheck.status == "CHECKING",
            GraduationPlagiarismCheck.is_deleted.is_(False),
        ).with_for_update()).first()
        if active:
            return _plag_row(active, stu)
        p = GraduationPlagiarismCheck(tenant_id=_tid(), gd_student_id=stu.id,
                                      gd_final_id=final.id,
                                      submit_at=datetime.now(timezone.utc), status="CHECKING",
                                      active_key=f"checking:{final.id}", threshold=threshold)
        db.add(p)
        db.flush()
        _audit(db, "PLAGIARISM", p.id, "发起查重")
        db.commit()
        return _plag_row(p, stu)


def set_plagiarism_result(pid, rate: str, report_url: str = None) -> dict:
    with session() as db:
        probe = db.get(GraduationPlagiarismCheck, int(pid))
        if not probe or probe.is_deleted or probe.tenant_id != _tid():
            raise not_found("查重记录不存在")
        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.id == probe.gd_final_id,
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.is_deleted.is_(False),
        ).with_for_update()).first() if probe.gd_final_id else None
        p = db.scalars(select(GraduationPlagiarismCheck).where(
            GraduationPlagiarismCheck.id == int(pid),
            GraduationPlagiarismCheck.tenant_id == _tid(),
            GraduationPlagiarismCheck.is_deleted.is_(False),
        ).with_for_update()).first()
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("查重记录不存在")
        assert_student_access(db, db.get(GraduationStudent, p.gd_student_id), "plagiarism.result")
        if p.status != "CHECKING":
            raise AppException("DATA_CONFLICT", "仅「检测中」记录可回填结果")
        try:
            rate_val = float(str(rate).replace("%", ""))
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "重复率格式错误")
        if rate_val < 0 or rate_val > 100:
            raise AppException("VALIDATION_ERROR", "重复率必须在 0-100 之间")
        report_url = (report_url or "").strip() or None
        if report_url and not (report_url.startswith("https://") or report_url.startswith("/api/v1/")):
            raise AppException("VALIDATION_ERROR", "查重报告仅允许 HTTPS 或平台内部地址")
        p.rate = f"{rate_val}%"
        p.report_url = report_url
        p.status = "DONE"
        p.active_key = None
        p.over_threshold = rate_val > p.threshold
        if final:
            final.plagiarism_rate = p.rate
            final.plagiarism_status = "已检测"
        stu = db.scalars(select(GraduationStudent).where(
            GraduationStudent.id == p.gd_student_id,
            GraduationStudent.tenant_id == _tid(),
        ).with_for_update()).first()
        if stu:
            stu.plagiarism_rate = p.rate
            stu.version += 1
        _audit(db, "PLAGIARISM", p.id, "查重结果回填", detail=p.rate)
        db.commit()
        return _plag_row(p, stu)


def dispute_plagiarism(pid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "复查理由必填且不少于 5 字")
    with session() as db:
        p = db.scalars(select(GraduationPlagiarismCheck).where(
            GraduationPlagiarismCheck.id == int(pid),
            GraduationPlagiarismCheck.tenant_id == _tid(),
            GraduationPlagiarismCheck.is_deleted.is_(False),
        ).with_for_update()).first()
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("查重记录不存在")
        assert_student_access(db, db.get(GraduationStudent, p.gd_student_id), "plagiarism.dispute")
        if p.status != "DONE" or not p.over_threshold:
            raise AppException("DATA_CONFLICT", "仅超标记录可申请复查")
        p.dispute_reason = reason.strip()
        p.dispute_status = "PENDING"
        _audit(db, "PLAGIARISM", p.id, "申请复查", reason.strip())
        db.commit()
        return _plag_row(p, db.get(GraduationStudent, p.gd_student_id))


def review_dispute(pid, action: str, comment: str = None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    with session() as db:
        p = db.scalars(select(GraduationPlagiarismCheck).where(
            GraduationPlagiarismCheck.id == int(pid),
            GraduationPlagiarismCheck.tenant_id == _tid(),
            GraduationPlagiarismCheck.is_deleted.is_(False),
        ).with_for_update()).first()
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("查重记录不存在")
        assert_student_access(db, db.get(GraduationStudent, p.gd_student_id), "plagiarism.dispute.review")
        if p.dispute_status != "PENDING":
            raise AppException("DATA_CONFLICT", "无待处理的复查申请")
        p.dispute_status = "APPROVED" if action == "APPROVE" else "REJECTED"
        p.dispute_comment = (comment or "").strip()
        recheck = None
        if action == "APPROVE":
            if not p.gd_final_id:
                raise AppException("DATA_CONFLICT", "原查重任务未绑定成果，无法创建复查任务")
            final = db.scalars(select(GraduationFinal).where(
                GraduationFinal.id == p.gd_final_id,
                GraduationFinal.tenant_id == _tid(),
                GraduationFinal.is_deleted.is_(False),
            ).with_for_update()).first()
            if not final:
                raise AppException("DATA_CONFLICT", "原成果不存在，无法创建复查任务")
            active = db.scalars(select(GraduationPlagiarismCheck).where(
                GraduationPlagiarismCheck.tenant_id == _tid(),
                GraduationPlagiarismCheck.gd_final_id == final.id,
                GraduationPlagiarismCheck.status == "CHECKING",
                GraduationPlagiarismCheck.is_deleted.is_(False),
            ).with_for_update()).first()
            if active:
                raise AppException("DATA_CONFLICT", "该成果已有进行中的查重或复查任务")
            recheck = GraduationPlagiarismCheck(
                tenant_id=_tid(), gd_student_id=p.gd_student_id, gd_final_id=final.id,
                recheck_of_id=p.id, submit_at=datetime.now(timezone.utc),
                status="CHECKING", active_key=f"checking:{final.id}", threshold=p.threshold,
            )
            db.add(recheck)
            db.flush()
        _audit(db, "PLAGIARISM", p.id, "复查审核-" + ("通过" if action == "APPROVE" else "驳回"),
               f"{(comment or '').strip()};recheckTaskId={recheck.id if recheck else ''}")
        db.commit()
        result = _plag_row(p, db.get(GraduationStudent, p.gd_student_id))
        result["recheckTaskId"] = str(recheck.id) if recheck else None
        return result


def plagiarism_stats(batch_id=None) -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        base = [GraduationPlagiarismCheck.tenant_id == _tid(), GraduationPlagiarismCheck.is_deleted.is_(False),
                GraduationPlagiarismCheck.gd_student_id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationPlagiarismCheck).where(*base)) or 0)
        over = int(db.scalar(select(func.count()).select_from(GraduationPlagiarismCheck).where(
            *base, GraduationPlagiarismCheck.over_threshold.is_(True))) or 0)
        checking = int(db.scalar(select(func.count()).select_from(GraduationPlagiarismCheck).where(
            *base, GraduationPlagiarismCheck.status == "CHECKING")) or 0)
        return {"total": total, "overThresholdCount": over, "checkingCount": checking,
                "batchId": str(batch_id) if batch_id else None}


# ═══════════ 教师评阅 ═══════════

def _review_row(r: GraduationReview, stu=None) -> dict:
    return {"id": str(r.id), "gdStudentId": str(r.gd_student_id), "gdFinalId": str(r.gd_final_id or ""),
            "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
            "advisorName": stu.advisor_name if stu else "", "reviewerName": r.reviewer_name,
            "reviewerMentorId": str(r.reviewer_mentor_id) if getattr(r, "reviewer_mentor_id", None) else None,
            "status": r.status, "statusLabel": REVIEW_STATUS_LABEL.get(r.status, r.status),
            "statusTone": REVIEW_STATUS_TONE.get(r.status, "default"),
            "score": r.score, "opinion": r.opinion or "", "reviewedAt": _iso(r.reviewed_at),
            "assignedBy": r.assigned_by or "", "assignedAt": _iso(r.assigned_at)}


def list_reviews(page: int, page_size: int, gd_student_id=None, reviewer_name=None,
                 status=None, batch_id=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationReview).where(GraduationReview.tenant_id == _tid(),
                                           GraduationReview.is_deleted.is_(False),
                                           GraduationReview.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationReview.gd_student_id == int(gd_student_id))
        if batch_id:
            q = q.where(GraduationReview.gd_student_id.in_(select(GraduationStudent.id).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.batch_id == int(batch_id),
                GraduationStudent.is_deleted.is_(False))))
        if reviewer_name:
            q = q.where(GraduationReview.reviewer_name == reviewer_name)
        if status:
            q = q.where(GraduationReview.status == status)
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationReview.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = [_review_row(r, db.get(GraduationStudent, r.gd_student_id)) for r in rows]
        return items, total


def assign_review(gd_student_id, reviewer_name: str | None = None, gd_final_id=None,
                  reviewer_mentor_id=None) -> dict:
    with session() as db:
        from app.modules.graduation.services import graduation_identity as gid
        stu = _stu(db, gd_student_id)
        review_policy.authorize(db, stu, "assign")
        mid = None
        reviewer = (reviewer_name or "").strip()
        if reviewer_mentor_id not in (None, ""):
            m = gid.require_mentor(db, reviewer_mentor_id)
            mid = int(m.id)
            reviewer = (m.teacher_name or "").strip()
        if not reviewer or not mid:
            raise AppException("VALIDATION_ERROR", "评阅任务必须选择已绑定导师台账的评阅人")
        if gid.sod_conflict_with_advisor(db, stu, reviewer_mentor_id=mid, reviewer_name=reviewer):
            raise AppException("VALIDATION_ERROR", "评阅人不得是该生指导教师（SoD 冲突）")
        # 评阅任务必须绑定权威定稿；调用方不得通过传空或旧版本改变核算来源。
        final = db.scalars(select(GraduationFinal).where(
            GraduationFinal.tenant_id == _tid(),
            GraduationFinal.gd_student_id == stu.id,
            GraduationFinal.final_type == "定稿",
            GraduationFinal.status == "APPROVED",
            GraduationFinal.is_deleted.is_(False),
        ).order_by(GraduationFinal.id.desc()).with_for_update()).first()
        if not final:
            raise AppException("DATA_CONFLICT", "请先完成并通过正式定稿，再分配评阅任务")
        final_id = int(final.id)
        existing_q = select(GraduationReview).where(
            GraduationReview.tenant_id == _tid(),
            GraduationReview.gd_student_id == stu.id,
            GraduationReview.gd_final_id == final_id,
            GraduationReview.status.in_(("ASSIGNED", "REVIEWING", "RETURNED")),
            GraduationReview.is_deleted.is_(False),
        )
        if mid:
            existing_q = existing_q.where(GraduationReview.reviewer_mentor_id == mid)
        else:
            existing_q = existing_q.where(
                GraduationReview.reviewer_name == reviewer,
                GraduationReview.reviewer_mentor_id.is_(None),
            )
        existing = db.scalars(existing_q.with_for_update()).first()
        if existing:
            return _review_row(existing, stu)
        n, _ = _op()
        r = GraduationReview(tenant_id=_tid(), gd_student_id=stu.id,
                             gd_final_id=final_id,
                             reviewer_name=reviewer, reviewer_mentor_id=mid,
                             status="ASSIGNED",
                             assigned_by=n, assigned_at=datetime.now(timezone.utc))
        db.add(r)
        db.flush()
        _audit(db, "REVIEW", r.id, "分配评阅任务", detail=f"{stu.name}→{reviewer}")
        db.commit()
        return _review_row(r, stu)


def submit_review(rid, score: int, opinion: str) -> dict:
    with session() as db:
        from app.modules.graduation.services import graduation_identity as gid
        r = db.scalars(select(GraduationReview).where(
            GraduationReview.id == int(rid), GraduationReview.tenant_id == _tid(),
            GraduationReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("评阅任务不存在")
        review_policy.authorize(db, db.get(GraduationStudent, r.gd_student_id), "submit")
        # 评阅提交只认稳定 reviewer_mentor_id；历史缺 ID 的任务必须先治理。
        if not has_full_scope():
            me = gid.current_user_mentor(db)
            if not r.reviewer_mentor_id or not me or int(me.id) != int(r.reviewer_mentor_id):
                raise no_permission("仅稳定ID匹配的被指派评阅人可提交本任务")
        if r.status == "COMPLETED" and r.score == score and (r.opinion or "") == opinion:
            return _review_row(r, db.get(GraduationStudent, r.gd_student_id))
        if r.status not in ("ASSIGNED", "REVIEWING", "RETURNED"):
            raise AppException("DATA_CONFLICT", "当前状态不可提交评阅")
        r.score = score
        r.opinion = opinion
        r.status = "COMPLETED"
        r.reviewed_at = datetime.now(timezone.utc)
        r.version += 1
        _audit(db, "REVIEW", r.id, "提交评阅", detail=f"score={score}")
        db.commit()
        return _review_row(r, db.get(GraduationStudent, r.gd_student_id))


def return_review(rid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        r = db.scalars(select(GraduationReview).where(
            GraduationReview.id == int(rid), GraduationReview.tenant_id == _tid(),
            GraduationReview.is_deleted.is_(False),
        ).with_for_update()).first()
        if not r or r.is_deleted or r.tenant_id != _tid():
            raise not_found("评阅任务不存在")
        review_policy.authorize(db, db.get(GraduationStudent, r.gd_student_id), "return")
        if r.status == "RETURNED":
            return _review_row(r, db.get(GraduationStudent, r.gd_student_id))
        if r.status != "COMPLETED":
            raise AppException("DATA_CONFLICT", "仅「已完成」评阅可退回重评")
        history_snapshot = (
            f"reason={reason.strip()}; previousVersion={r.version}; "
            f"score={r.score}; opinion={r.opinion or ''}"
        )
        r.status = "RETURNED"
        r.version += 1
        _audit(db, "REVIEW", r.id, "退回重评", history_snapshot)
        db.commit()
        return _review_row(r, db.get(GraduationStudent, r.gd_student_id))


def review_stats(batch_id=None) -> dict:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid(), batch_id=batch_id)
        base = [GraduationReview.tenant_id == _tid(), GraduationReview.is_deleted.is_(False),
                GraduationReview.gd_student_id.in_(scope_ids or [-1])]
        total = int(db.scalar(select(func.count()).select_from(GraduationReview).where(*base)) or 0)
        by_status = [{"status": s, "label": REVIEW_STATUS_LABEL[s],
                      "count": int(db.scalar(select(func.count()).select_from(GraduationReview).where(
                          *base, GraduationReview.status == s)) or 0)} for s in REVIEW_STATUS_LABEL]
        return {"total": total, "byStatus": by_status,
                "batchId": str(batch_id) if batch_id else None}
