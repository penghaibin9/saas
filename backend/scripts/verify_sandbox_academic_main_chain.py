"""Verify one real sandbox path across schedule, attendance, exam, grade, warning and graduation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.context import set_current_user, set_tenant  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.models import StudentAccountLink, StudentProfile, User  # noqa: E402
from app.modules.academic_affairs.services import mobile_academic_affairs_service as mobile  # noqa: E402


def _pattern(item: dict) -> tuple:
    return (
        int(item.get("weekday") or 0), int(item.get("slotNo") or 0),
        int(item.get("startWeek") or 0), int(item.get("endWeek") or 0),
        str(item.get("weekParity") or "ALL"),
    )


def verify(tenant_id: int) -> dict:
    set_tenant({
        "tenantId": str(tenant_id), "tenantCode": "sandbox-school",
        "tenantName": "体验沙箱学校", "status": "ACTIVE",
    })
    with get_sessionmaker()() as db:
        change = db.execute(text("""
            SELECT c.id,c.batch_id,c.origin_item_id,c.new_item_id,c.task_id,c.class_id,c.teacher_key,
                   c.status,o.status origin_status,n.status new_status,h.active_batch_id
              FROM t_aa_schedule_change c
              JOIN t_aa_schedule_item o ON o.id=c.origin_item_id AND o.tenant_id=c.tenant_id
              JOIN t_aa_schedule_item n ON n.id=c.new_item_id AND n.change_id=c.id AND n.tenant_id=c.tenant_id
              JOIN t_aa_schedule_scope_head h ON h.tenant_id=c.tenant_id AND h.term_id=c.term_id
               AND h.scope_type='SCHOOL' AND h.scope_id=0 AND h.is_deleted=0
             WHERE c.tenant_id=:tenant_id AND c.status='APPLIED' AND c.is_deleted=0
             ORDER BY c.id DESC LIMIT 1
        """), {"tenant_id": tenant_id}).mappings().first()
        if not change:
            raise RuntimeError("没有可演示的已生效调停课")
        if int(change["batch_id"]) != int(change["active_batch_id"]):
            raise RuntimeError("调停课未落到当前 ScopeHead")
        if change["origin_status"] != "CHANGED" or change["new_status"] != "EFFECTIVE":
            raise RuntimeError("调停课新旧课位状态未闭合")

        teacher = db.query(User).filter(
            User.tenant_id == tenant_id,
            User.login_name == change["teacher_key"],
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        ).one()
        student = db.query(StudentProfile).filter(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.class_id == int(change["class_id"]),
            StudentProfile.is_deleted.is_(False),
        ).order_by(StudentProfile.id).first()
        link = db.query(StudentAccountLink).filter(
            StudentAccountLink.tenant_id == tenant_id,
            StudentAccountLink.student_id == int(student.id),
            StudentAccountLink.link_status == "ACTIVE",
            StudentAccountLink.is_deleted.is_(False),
        ).one()
        student_user = db.get(User, int(link.user_id))

        changed_attendance = db.execute(text("""
            SELECT a.id,a.status,a.source_type,a.total_count,a.teaching_task_id,
                   JSON_UNQUOTE(JSON_EXTRACT(a.source_evidence,'$.scheduleItemId')) schedule_item_id,
                   JSON_UNQUOTE(JSON_EXTRACT(a.source_evidence,'$.changeId')) change_id
              FROM t_aa_attendance_session a
             WHERE a.tenant_id=:tenant_id AND a.is_deleted=0 AND a.status='SUBMITTED'
               AND a.source_type='FORMAL_TEACHING' AND JSON_VALID(a.source_evidence)=1
               AND JSON_UNQUOTE(JSON_EXTRACT(a.source_evidence,'$.changeId'))=:change_id
             ORDER BY a.id DESC LIMIT 1
        """), {"tenant_id": tenant_id, "change_id": str(change["id"])}).mappings().first()
        if not changed_attendance:
            raise RuntimeError("调课新课位尚未形成正式已提交考勤")

        exam_grade_warning = db.execute(text("""
            SELECT eb.id exam_batch_id,eb.status exam_status,ec.id exam_course_id,
                   ec.teaching_task_id,ers.id candidate_id,ers.student_id,ers.student_no,
                   gt.id grade_task_id,gt.status grade_task_status,gr.id grade_record_id,
                   gr.total_score,gr.pass_status,ag.id formal_grade_id,ag.record_status,
                   w.id warning_id,w.status warning_status,a.failed_count,a.warning_count
              FROM t_aa_exam_batch eb
              JOIN t_aa_exam_course ec ON ec.batch_id=eb.id AND ec.tenant_id=eb.tenant_id AND ec.is_deleted=0
              JOIN t_aa_exam_room_student ers ON ers.exam_course_id=ec.id AND ers.tenant_id=ec.tenant_id AND ers.is_deleted=0
              JOIN t_aa_grade_task gt ON gt.teaching_task_id=ec.teaching_task_id AND gt.tenant_id=ec.tenant_id AND gt.is_deleted=0
              JOIN t_aa_grade_record gr ON gr.task_id=gt.id AND gr.student_id=ers.student_id
               AND gr.tenant_id=gt.tenant_id AND gr.is_deleted=0
              JOIN t_acad_grade ag ON ag.id=gr.acad_grade_id AND ag.grade_record_id=gr.id
               AND ag.tenant_id=gr.tenant_id AND ag.is_deleted=0 AND ag.record_status='ACTIVE'
              JOIN t_acad_student a ON a.student_id=ers.student_id AND a.tenant_id=ers.tenant_id AND a.is_deleted=0
              JOIN t_acad_warning w ON w.acad_student_id=a.id AND w.tenant_id=a.tenant_id
               AND w.is_deleted=0 AND w.source_code='EXAM_FAIL'
             WHERE eb.tenant_id=:tenant_id AND eb.status='FINISHED' AND eb.is_deleted=0
               AND gr.pass_status IN ('FAIL','FAILED') AND a.failed_count>=2
             ORDER BY gr.id LIMIT 1
        """), {"tenant_id": tenant_id}).mappings().first()
        if not exam_grade_warning:
            raise RuntimeError("没有考试名单→成绩→预警的同一学生演示链")

        graduation = db.execute(text("""
            SELECT b.id batch_id,b.status batch_status,r.id result_id,r.student_id,r.status result_status,
                   r.overall,r.conclusion,run.id run_id,run.overall run_overall,
                   d.id decision_id,d.conclusion decision_conclusion,d.evaluation_run_id,
                   s.student_no,a.id acad_student_id,a.obtained_credits,a.required_credits,
                   s.student_status,s.current_stage
              FROM t_aa_graduation_audit_batch b
              JOIN t_aa_graduation_audit_result r ON r.batch_id=b.id AND r.tenant_id=b.tenant_id AND r.is_deleted=0
              JOIN t_aa_graduation_evaluation_run run ON run.result_id=r.id AND run.batch_id=r.batch_id
               AND run.student_id=r.student_id AND run.tenant_id=r.tenant_id
              JOIN t_aa_graduation_decision_fact d ON d.result_id=r.id AND d.evaluation_run_id=run.id
               AND d.student_id=r.student_id AND d.tenant_id=r.tenant_id
              JOIN t_student_profile s ON s.id=r.student_id AND s.tenant_id=r.tenant_id AND s.is_deleted=0
              JOIN t_acad_student a ON a.student_id=s.id AND a.tenant_id=s.tenant_id AND a.is_deleted=0
             WHERE b.tenant_id=:tenant_id AND b.is_deleted=0 ORDER BY b.id DESC,r.id LIMIT 1
        """), {"tenant_id": tenant_id}).mappings().first()
        if not graduation:
            raise RuntimeError("毕业审核缺少结果→Run→决定→学生学业台账演示链")

    teacher_user = {
        "userId": f"db-{teacher.id}", "tenantId": str(tenant_id),
        "loginName": teacher.login_name, "realName": teacher.real_name,
        "userType": "TEACHER", "currentRoleCode": "ACADEMIC_TEACHER",
    }
    set_current_user(teacher_user)
    teacher_projection = mobile.teacher_schedule_my(teacher_user)
    student_ctx = {
        "userId": f"db-{student_user.id}", "tenantId": str(tenant_id),
        "loginName": student_user.login_name, "realName": student.real_name,
        "userType": "STUDENT", "currentRoleCode": "STUDENT",
        "studentId": str(student.id), "studentNo": student.student_no,
    }
    set_current_user(student_ctx)
    student_projection = mobile.schedule_my(student_ctx)
    teacher_patterns = {
        _pattern(item) for item in teacher_projection.get("items") or []
        if str(item.get("teacherKey") or "") == str(change["teacher_key"])
    }
    student_patterns = {
        _pattern(item) for item in student_projection.get("items") or []
        if str(item.get("teacherKey") or "") == str(change["teacher_key"])
    }
    if not teacher_patterns or teacher_patterns != student_patterns:
        raise RuntimeError("教师与学生共享课表投影不一致")
    if teacher_projection.get("issues"):
        raise RuntimeError(f"教师课表存在关系冲突: {teacher_projection['issues']}")

    return {
        "scheduleChangeToFourEnds": {
            "changeId": str(change["id"]), "activeBatchId": str(change["active_batch_id"]),
            "originItemId": str(change["origin_item_id"]), "newItemId": str(change["new_item_id"]),
            "teacherLogin": teacher.login_name, "studentNo": student.student_no,
            "sharedPatterns": [list(value) for value in sorted(teacher_patterns)],
        },
        "changeToAttendance": dict(changed_attendance),
        "examToGradeToWarning": dict(exam_grade_warning),
        "graduationAudit": dict(graduation),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int, default=1000000000000000007)
    args = parser.parse_args()
    print(json.dumps(verify(args.tenant_id), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
