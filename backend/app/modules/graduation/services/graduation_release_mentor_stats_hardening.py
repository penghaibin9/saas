"""Graduation mentor scoped stats and conflict detection hardening."""
from __future__ import annotations

from sqlalchemy import func, select
from app.models import GraduationMentor, GraduationMentorAssignment, GraduationStudent
from app.services.db_service import _tid, session
from app.modules.graduation.services.graduation_release_hardening_common import _student_scope_select
from app.modules.graduation.services.graduation_release_mentor_common import _mentor_scope_select


def _install_mentor_stats_hardening() -> None:
    from app.modules.graduation.services import graduation_mentor_service as svc
    def mentor_stats(batch_id=None):
        with session() as db:
            scope_q = _mentor_scope_select(db)
            base = [
                GraduationMentor.tenant_id == _tid(),
                GraduationMentor.is_deleted.is_(False),
                GraduationMentor.id.in_(scope_q),
            ]
            total = int(db.scalar(select(func.count()).select_from(GraduationMentor).where(*base)) or 0)
            by_status = []
            for status_code, label in svc.QUAL_LABEL.items():
                count = int(db.scalar(select(func.count()).select_from(GraduationMentor).where(*base, GraduationMentor.qualification_status == status_code)) or 0)
                by_status.append({"status": status_code, "label": label, "count": count})
            qualified = list(db.execute(select(GraduationMentor.id, GraduationMentor.max_capacity).where(*base, GraduationMentor.qualification_status == "QUALIFIED")).all())
            qids = [int(mid) for mid, _ in qualified]
            loads = {int(mid): int(count or 0) for mid, count in db.execute(select(GraduationMentorAssignment.mentor_id, func.count()).where(
                GraduationMentorAssignment.tenant_id == _tid(), GraduationMentorAssignment.is_deleted.is_(False),
                GraduationMentorAssignment.status == "ACTIVE", GraduationMentorAssignment.mentor_id.in_(qids or [-1]),
            ).group_by(GraduationMentorAssignment.mentor_id)).all()}
            total_capacity = sum(int(cap or 0) for _, cap in qualified)
            total_assigned = sum(loads.get(int(mid), 0) for mid, _ in qualified)
            full_count = sum(1 for mid, cap in qualified if loads.get(int(mid), 0) >= int(cap or 0))
            student_scope = _student_scope_select(db, _tid(), batch_id=batch_id)
            unassigned = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE",
                GraduationStudent.id.in_(student_scope), GraduationStudent.mentor_id.is_(None),
            )) or 0)
            return {"total": total, "byStatus": by_status, "qualifiedCount": len(qualified), "fullCapacityCount": full_count,
                    "totalCapacity": total_capacity, "totalAssigned": total_assigned, "unassignedStudents": unassigned,
                    "batchId": str(batch_id) if batch_id else None}

    def detect_assignment_conflicts():
        with session() as db:
            mentor_ids = set(int(x) for x in db.scalars(_mentor_scope_select(db)).all())
            mentors = {int(m.id): m for m in db.scalars(select(GraduationMentor).where(
                GraduationMentor.tenant_id == _tid(), GraduationMentor.is_deleted.is_(False), GraduationMentor.id.in_(mentor_ids or [-1]),
            )).all()}
            loads = {int(mid): int(count or 0) for mid, count in db.execute(select(GraduationMentorAssignment.mentor_id, func.count()).where(
                GraduationMentorAssignment.tenant_id == _tid(), GraduationMentorAssignment.is_deleted.is_(False),
                GraduationMentorAssignment.status == "ACTIVE", GraduationMentorAssignment.mentor_id.in_(mentor_ids or [-1]),
            ).group_by(GraduationMentorAssignment.mentor_id)).all()}
            over = [{"mentorId": str(mid), "teacherName": m.teacher_name, "current": loads.get(mid, 0), "capacity": int(m.max_capacity or 0)}
                    for mid, m in mentors.items() if loads.get(mid, 0) > int(m.max_capacity or 0)]
            student_ids = _student_scope_select(db, _tid())
            students = db.scalars(select(GraduationStudent).where(
                GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
                GraduationStudent.record_status == "ACTIVE", GraduationStudent.id.in_(student_ids),
            )).all()
            no_mentor, bad_mentor = [], []
            for stu in students:
                advanced = stu.stage in ("GUIDING", "MIDTERM", "FINAL_CHECK", "DEFENSE", "COMPLETED")
                if advanced and not stu.mentor_id:
                    no_mentor.append({"gdStudentId": str(stu.id), "name": stu.name, "className": stu.class_name or "", "stage": stu.stage})
                    continue
                if stu.mentor_id:
                    mentor = db.get(GraduationMentor, int(stu.mentor_id))
                    if mentor and mentor.tenant_id == _tid() and not mentor.is_deleted and mentor.qualification_status != "QUALIFIED":
                        bad_mentor.append({"gdStudentId": str(stu.id), "name": stu.name, "mentorName": mentor.teacher_name,
                                           "mentorStatus": svc.QUAL_LABEL.get(mentor.qualification_status, mentor.qualification_status)})
            return {"overCapacity": over, "advancedNoMentor": no_mentor, "unqualifiedMentor": bad_mentor,
                    "total": len(over) + len(no_mentor) + len(bad_mentor)}

    svc.mentor_stats = mentor_stats
    svc.detect_assignment_conflicts = detect_assignment_conflicts
