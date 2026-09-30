"""007 学工第二课堂、社团、学生组织与归档的可演示过程事实。"""
from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import func, select

REFERENCE_NOW = datetime(2026, 8, 28, 10, 30)
MARKER = "007-AFFAIRS-OP-2026"


def _one(db, model, tenant_id, **where):
    clauses = [model.tenant_id == tenant_id]
    if hasattr(model, "is_deleted"):
        clauses.append(model.is_deleted.is_(False))
    clauses += [getattr(model, k) == v for k, v in where.items()]
    return db.scalars(select(model).where(*clauses)).first()


def _put(db, model, tenant_id, key, values):
    row = _one(db, model, tenant_id, **key)
    if row is None:
        row = model(tenant_id=tenant_id, **key, **values)
        db.add(row); db.flush()
    return row


def seed_affairs_operational_coverage(db, tenant_id: int) -> dict:
    from app.models import College, CsLeave, SchoolClass, StudentProfile, User
    from app.models.affairs import AffairsAuditTrail, AffairsLeaveCancelRecord, AffairsLeaveExtension
    from app.models.affairs_operations import AffairsBatchJob, AffairsBatchJobItem, AffairsMaterialRequirement, AffairsMaterialSubmission
    from app.models.affairs_activity import (AffairsActivity, AffairsActivityCredit, AffairsActivitySignup,
                                             AffairsCreditAppeal, AffairsCreditCategory, AffairsVolunteerRecord)
    from app.models.affairs_archive import ArchiveBatch, ArchivePackage
    from app.models.affairs_attachment import AffairsAttachment
    from app.models.affairs_club import AffairsClub, AffairsClubAnnualReview, AffairsClubMember
    from app.models.affairs_counselor_assignment import AffairsCounselorAssignment
    from app.models.affairs_counselor_eval import CounselorEval, CounselorEvalIndicator
    from app.models.affairs_league import AffairsLeagueDev, AffairsLeagueDevStage
    from app.models.affairs_org import AffairsOrgPosition, AffairsStudentOrg
    from app.models.file import ArchiveManifest, FileAsset, FileObject, FileVersion
    from app.models.orientation import OrientationArchive, OrientationAuditTrail, OrientationCheckinPoint, OrientationFlowConfig, OrientationNoticeTask

    admin = _one(db, User, tenant_id, login_name="admin2")
    teacher = _one(db, User, tenant_id, login_name="teacher2")
    students = list(db.scalars(select(StudentProfile).where(StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False)).order_by(StudentProfile.id).limit(6)).all())
    college = db.scalars(select(College).where(College.tenant_id == tenant_id, College.is_deleted.is_(False)).order_by(College.id)).first()
    clazz = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id, SchoolClass.is_deleted.is_(False)).order_by(SchoolClass.id)).first()
    evidence = _one(db, FileObject, tenant_id, file_key="007-GOV-2026/leave-approval-evidence.md")
    if not all((admin, teacher, college, clazz, evidence)) or len(students) < 6:
        raise RuntimeError("007 affairs operational seed requires master users, organization, students and governance evidence file")
    asset = _one(db, FileAsset, tenant_id, asset_code="007-GOV-2026-LEAVE-EVIDENCE")
    version = _one(db, FileVersion, tenant_id, asset_id=asset.id, version_no=1) if asset else None
    if not asset or not version:
        raise RuntimeError("007 governance evidence asset/version unavailable")

    for code, name, kind, sort in (("VOLUNTEER", "志愿公益", "VOLUNTEER_HOUR", 10), ("PRACTICE", "社会实践", "SECOND_CLASS", 20), ("INNOVATION", "创新创业", "MORAL", 30)):
        _put(db, AffairsCreditCategory, tenant_id, {"category_code": code}, {"category_name": name, "credit_type": kind, "weight": 1, "description": "007 第二课堂成绩单分类。", "sort_order": sort, "status": "ENABLED"})
    activity = _put(db, AffairsActivity, tenant_id, {"activity_name": f"{MARKER}-社区数字助老志愿服务"}, {"activity_type": "VOLUNTEER", "scope_type": "COLLEGE", "scope_ref": str(college.id), "location": "跃科社区服务中心", "description": "学生开展数字设备使用辅导，活动签到与志愿时长可追溯。", "start_at": REFERENCE_NOW - timedelta(days=7), "end_at": REFERENCE_NOW - timedelta(days=7, hours=-3), "enroll_deadline": REFERENCE_NOW - timedelta(days=9), "quota": 60, "credit_type": "VOLUNTEER_HOUR", "credit_value": 3, "category_code": "VOLUNTEER", "status": "CONFIRMED", "publisher_id": teacher.id, "publisher_name": teacher.real_name, "confirm_at": REFERENCE_NOW - timedelta(days=6)})
    for index, student in enumerate(students[:4]):
        signup_status = ("CONFIRMED", "CHECKED_IN", "ENROLLED", "CANCELLED")[index]
        _put(db, AffairsActivitySignup, tenant_id, {"activity_id": activity.id, "student_id": student.id}, {"signup_status": signup_status, "enrolled_at": REFERENCE_NOW - timedelta(days=10), "checkin_at": REFERENCE_NOW - timedelta(days=7) if signup_status in {"CONFIRMED", "CHECKED_IN"} else None, "checkin_method": "QR" if signup_status in {"CONFIRMED", "CHECKED_IN"} else None})
    credit = _put(db, AffairsActivityCredit, tenant_id, {"student_id": students[0].id, "activity_id": activity.id, "credit_type": "VOLUNTEER_HOUR"}, {"credit_value": 3, "category_code": "VOLUNTEER", "source": "ACTIVITY", "remark": "签到确认后生成的志愿时长。", "granted_at": REFERENCE_NOW - timedelta(days=6)})
    _put(db, AffairsVolunteerRecord, tenant_id, {"student_id": students[1].id, "service_name": "社区无障碍出行引导"}, {"activity_id": activity.id, "org_name": "跃科社区服务中心", "hours": 2.5, "service_date": REFERENCE_NOW - timedelta(days=8), "status": "CONFIRMED", "credit_id": credit.id, "remark": "线下补录经校团委确认。"})
    _put(db, AffairsCreditAppeal, tenant_id, {"student_id": students[2].id, "activity_id": activity.id}, {"appeal_type": "MISSING", "claim_credit_type": "VOLUNTEER_HOUR", "claim_value": 3, "reason": "已签到但志愿时长尚未进入成绩单，申请核验。", "status": "APPROVED", "result_credit_id": credit.id, "review_opinion": "签到二维码与现场名单一致，补记学时。", "reviewer": teacher.real_name, "reviewed_at": REFERENCE_NOW - timedelta(days=5)})

    club = _put(db, AffairsClub, tenant_id, {"club_name": f"{MARKER}-智能制造创新社"}, {"club_type": "ACADEMIC", "college_id": college.id, "advisor_name": teacher.real_name, "president_student_id": students[0].id, "founder_student_id": students[1].id, "charter_file_id": evidence.id, "member_count": 3, "established_at": REFERENCE_NOW - timedelta(days=100), "status": "ACTIVE"})
    for student, role in ((students[0], "PRESIDENT"), (students[1], "VICE_PRESIDENT"), (students[2], "MEMBER")):
        _put(db, AffairsClubMember, tenant_id, {"club_id": club.id, "student_id": student.id, "status": "ACTIVE"}, {"role": role, "joined_at": REFERENCE_NOW - timedelta(days=100), "quit_at": None})
    _put(db, AffairsClubAnnualReview, tenant_id, {"club_id": club.id, "review_year": "2025-2026"}, {"result": "PASS", "activity_count": 8, "material_file_id": evidence.id, "comment": "活动、成员和指导教师材料齐全，通过年审。", "reviewer_name": admin.real_name, "reviewed_at": REFERENCE_NOW - timedelta(days=12)})
    org = _put(db, AffairsStudentOrg, tenant_id, {"org_name": f"{MARKER}-学生创新实践中心"}, {"org_type": "STUDENT_UNION", "level": "COLLEGE", "college_id": college.id, "advisor_name": teacher.real_name, "status": "ACTIVE"})
    _put(db, AffairsOrgPosition, tenant_id, {"org_id": org.id, "student_id": students[0].id, "position": "主席", "status": "ACTIVE"}, {"term_code": "2025-2026", "appointed_at": REFERENCE_NOW - timedelta(days=120), "removed_at": None})
    dev = _put(db, AffairsLeagueDev, tenant_id, {"student_id": students[3].id, "dev_type": "PARTY"}, {"current_stage": "ACTIVIST", "branch_name": "智能制造学院学生第一党支部", "status": "ONGOING", "started_at": REFERENCE_NOW - timedelta(days=240), "completed_at": None})
    _put(db, AffairsLeagueDevStage, tenant_id, {"dev_id": dev.id, "to_stage": "ACTIVIST"}, {"from_stage": "APPLICANT", "material_file_id": evidence.id, "operator": teacher.real_name, "remark": "培养考察材料齐备，进入积极分子阶段。", "occurred_at": REFERENCE_NOW - timedelta(days=30)})
    _put(db, AffairsCounselorAssignment, tenant_id, {"class_id": clazz.id, "user_id": teacher.id, "duty_type": "PRIMARY", "status": "ACTIVE"}, {"effective_from": REFERENCE_NOW - timedelta(days=180), "effective_to": None, "reason": "与行政班主数据辅导员关系对账。", "handover_from_user_id": None, "version": 1})
    indicator = _put(db, CounselorEvalIndicator, tenant_id, {"name": f"{MARKER}-学生风险闭环率"}, {"category": "学生工作", "weight": 40, "max_score": 100, "sort_order": 1, "status": "ENABLED"})
    _put(db, CounselorEval, tenant_id, {"period_code": "2025-2026-2", "counselor_key": str(teacher.id)}, {"counselor_name": teacher.real_name, "scores_json": {str(indicator.id): 96}, "total_score": 96, "weighted_total_score": 96, "remark": "风险、谈心和班级服务闭环完成。", "status": "PUBLISHED", "published_at": REFERENCE_NOW - timedelta(days=20), "appeal_status": "REVIEWED", "appeal_reason": "复核风险结案统计口径。", "appeal_result": "UPHELD", "appeal_opinion": "明细与统计源一致，维持原成绩。"})
    batch = _put(db, ArchiveBatch, tenant_id, {"batch_name": f"{MARKER}-2025学年学生成长档案"}, {"year_code": "2025-2026", "scope_json": '{"college":"智能制造学院","sample":true}', "confirm_by": admin.real_name, "confirm_at": REFERENCE_NOW - timedelta(days=5), "workflow_instance_id": None, "status": "ARCHIVED"})
    manifest = _put(db, ArchiveManifest, tenant_id, {"module_code": "studentAffairs", "archive_type": "GROWTH_RECORD", "target_type": "StudentProfile", "target_id": str(students[0].id), "revision": 1}, {"status": "PACKAGED", "rule_version": "2026.1", "manifest_sha256": "007affairsgrowthmanifest", "package_file_id": evidence.id, "created_by_name": admin.real_name, "frozen_at": REFERENCE_NOW - timedelta(days=5)})
    _put(db, ArchivePackage, tenant_id, {"batch_id": batch.id, "student_id": students[0].id}, {"missing_items_json": "[]", "package_file_id": evidence.id, "export_task_id": None, "status": "ARCHIVED", "generation_attempts": 1, "generation_error": None, "package_asset_id": asset.id, "package_version_id": version.id, "manifest_id": manifest.id, "manifest_revision": 1, "manifest_sha256": "007affairsgrowthmanifest"})
    attachment = _put(db, AffairsAttachment, tenant_id, {"biz_type": "CLUB", "biz_id": club.id, "file_id": evidence.id}, {"file_name": evidence.file_name, "note": "社团年审和章程材料。", "asset_id": asset.id, "file_version_id": version.id, "binding_id": None, "sensitivity_level": "NORMAL", "source_channel": "BACKFILL"})
    leave = db.scalars(select(CsLeave).where(CsLeave.tenant_id == tenant_id, CsLeave.is_deleted.is_(False)).order_by(CsLeave.id)).first()
    if not leave:
        raise RuntimeError("007 affairs operational seed requires an existing leave request")
    _put(db, AffairsLeaveCancelRecord, tenant_id, {"leave_id": leave.id}, {"student_id": leave.student_id, "actual_return_at": REFERENCE_NOW - timedelta(days=2), "proof_note": "学生返校后在移动端提交返校说明，辅导员核验。", "confirm_by": teacher.real_name, "confirm_at": REFERENCE_NOW - timedelta(days=2), "confirm_note": "返校时间与宿舍晚归记录一致。", "workflow_instance_id": None, "status": "CONFIRMED"})
    _put(db, AffairsLeaveExtension, tenant_id, {"leave_id": leave.id, "student_id": leave.student_id}, {"old_end_time": REFERENCE_NOW - timedelta(days=3), "new_end_time": REFERENCE_NOW - timedelta(days=2), "extend_days": 1, "reason": "返程交通临时调整，已向辅导员说明。", "workflow_instance_id": None, "status": "APPROVED"})
    requirement = _put(db, AffairsMaterialRequirement, tenant_id, {"biz_type": "LEAVE", "biz_id": leave.id, "item_code": "RETURN_EVIDENCE"}, {"student_id": leave.student_id, "item_name": "返校佐证材料", "requirement_reason": "请假销假需补充返校佐证。", "status": "ACCEPTED", "return_round": 2, "due_at": REFERENCE_NOW - timedelta(days=1), "review_owner_id": teacher.id, "current_submission_id": None, "accepted_at": REFERENCE_NOW - timedelta(days=2), "asset_id": asset.id, "sensitivity_level": "PERSONAL", "material_scope": "STUDENT_SELF"})
    submission = _put(db, AffairsMaterialSubmission, tenant_id, {"requirement_id": requirement.id, "version_no": 2}, {"student_id": leave.student_id, "affairs_attachment_id": attachment.id, "file_id": evidence.id, "file_name": evidence.file_name, "status": "ACCEPTED", "submitted_by": str(leave.student_id), "submitted_at": REFERENCE_NOW - timedelta(days=2), "reviewed_by": str(teacher.id), "reviewed_at": REFERENCE_NOW - timedelta(days=2), "review_note": "材料与返校时间一致，接受第 2 版。", "supersedes_id": None, "asset_id": asset.id, "file_version_id": version.id, "binding_id": None, "sensitivity_level": "PERSONAL"})
    requirement.current_submission_id = submission.id
    job = _put(db, AffairsBatchJob, tenant_id, {"batch_no": f"{MARKER}-LEAVE-RECONCILE"}, {"job_type": "LEAVE_RECONCILE", "idempotency_key": f"{MARKER}-LEAVE-RECONCILE", "status": "PARTIAL_SUCCESS", "requested_by": str(admin.id), "retry_of_id": None, "request_json": {"scope": "completedLeave", "asOf": "2026-08-28"}, "total_count": 2, "success_count": 1, "failure_count": 1, "pending_count": 0, "started_at": REFERENCE_NOW - timedelta(days=2), "completed_at": REFERENCE_NOW - timedelta(days=2), "last_error": "一条历史请假缺少返校材料，已生成补交待办。"})
    _put(db, AffairsBatchJobItem, tenant_id, {"batch_job_id": job.id, "item_key": f"LEAVE:{leave.id}"}, {"todo_type": "LEAVE_RETURN", "biz_type": "LEAVE", "biz_id": leave.id, "action": "CONFIRM_RETURN", "expected_version": leave.version, "payload_json": {"cancelRecordId": str(_one(db, AffairsLeaveCancelRecord, tenant_id, leave_id=leave.id).id)}, "status": "SUCCESS", "attempt_count": 1, "error_code": None, "error_message": None, "result_json": {"status": "CONFIRMED"}, "started_at": REFERENCE_NOW - timedelta(days=2), "completed_at": REFERENCE_NOW - timedelta(days=2)})
    db.add(AffairsAuditTrail(tenant_id=tenant_id, biz_type="LEAVE", biz_id=leave.id, action="RETURN_CONFIRMED", operator=teacher.real_name, role_name="辅导员", detail="销假、材料补交和批量对账完成。", before_val="SUBMITTED", after_val="CONFIRMED", occurred_at=REFERENCE_NOW - timedelta(days=2)))
    for key, name, required, order in (("IDENTITY", "身份核验", True, 10), ("DORM", "宿舍办理", True, 20), ("FINANCE", "绿色通道", False, 30)):
        _put(db, OrientationFlowConfig, tenant_id, {"step_key": key}, {"step_name": name, "enabled": True, "required": required, "sort_order": order, "remark": "2026 级迎新现场流程配置。"})
    _put(db, OrientationCheckinPoint, tenant_id, {"name": "南门综合报到点"}, {"location": "行政楼南广场", "capacity": 800, "in_charge": teacher.real_name, "status": "ENABLED", "remark": "2026 级迎新高峰期分流点。"})
    notice = _put(db, OrientationNoticeTask, tenant_id, {"title": f"{MARKER}-迎新归档提醒"}, {"content": "2026 级迎新材料已完成归档，异常学生请在工作台查看处置记录。", "channel": "INAPP", "target_scope": "2026级新生与辅导员", "status": "SENT", "fail_reason": None, "sent_count": 7000})
    _put(db, OrientationArchive, tenant_id, {"archive_name": "2025级迎新历史归档"}, {"batch_no": "ORI-2025", "scope": "2025级新生报到、材料和异常处置记录", "status": "DONE", "item_count": 6500, "archived_by": admin.real_name, "archived_at": datetime(2025,9,20), "remark": "用于演示已完成迎新批次的归档证据。"})
    db.add(OrientationAuditTrail(tenant_id=tenant_id, biz_type="NOTICE", biz_id=str(notice.id), action="SEND_COMPLETED", operator=admin.real_name, role_name="学校管理员", detail="迎新归档提醒已向目标范围发送。", before_val="PENDING", after_val="SENT", occurred_at=REFERENCE_NOW - timedelta(days=1)))
    db.commit()
    return validate_affairs_operational_coverage(db, tenant_id)


def validate_affairs_operational_coverage(db, tenant_id: int) -> dict:
    from app.models.affairs_activity import AffairsActivity
    from app.models.affairs_archive import ArchiveBatch
    from app.models.affairs_club import AffairsClub
    from app.models.affairs_org import AffairsStudentOrg
    rows = {"activity": bool(_one(db, AffairsActivity, tenant_id, activity_name=f"{MARKER}-社区数字助老志愿服务")), "club": bool(_one(db, AffairsClub, tenant_id, club_name=f"{MARKER}-智能制造创新社")), "studentOrg": bool(_one(db, AffairsStudentOrg, tenant_id, org_name=f"{MARKER}-学生创新实践中心")), "archive": bool(_one(db, ArchiveBatch, tenant_id, batch_name=f"{MARKER}-2025学年学生成长档案"))}
    rows["passed"] = all(rows.values())
    if not rows["passed"]:
        raise RuntimeError(f"007 affairs operational coverage invalid: {rows}")
    return rows
