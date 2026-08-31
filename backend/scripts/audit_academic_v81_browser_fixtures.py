"""Read-only preflight for the four Academic V8.1 browser identities.

Passwords are deliberately outside this artifact.  The probe proves that each
selected login is an active, canonical 20K-school identity with the required
role and enough real academic facts for Dashboard-driven object discovery.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.tenant_identity import SANDBOX_SCHOOL
from app.db.session import get_sessionmaker
from app.models import (
    Role,
    StudentAccountLink,
    StudentProfile,
    Tenant,
    User,
    UserRole,
)
from app.services.sandbox_school_profile import PROFILE_STANDARD, classify_sandbox_profile


TENANT_ID = int(SANDBOX_SCHOOL.tenant_id)
TENANT_CODE = SANDBOX_SCHOOL.tenant_code
ACTORS = {
    "staffPc": {"loginName": "admin2", "requiredRole": "SCHOOL_ADMIN"},
    "teacherMini": {"loginName": "sbx_t0257", "requiredRole": "ACADEMIC_TEACHER"},
    "studentPc": {"loginName": "2024S0002", "requiredRole": "STUDENT"},
    "studentMini": {"loginName": "2024S0002", "requiredRole": "STUDENT"},
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Academic V8.1 browser fixture preflight")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def _head() -> str:
    root = Path(__file__).resolve().parents[2]
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def _count(db, sql: str, **params: int | str) -> int:
    return int(db.scalar(text(sql), params) or 0)


def main() -> int:
    args = _args()
    db = get_sessionmaker()()
    try:
        db.execute(text("SET SESSION TRANSACTION READ ONLY"))
        db.execute(text("START TRANSACTION READ ONLY"))
        tenant = db.scalar(
            select(Tenant).where(
                Tenant.id == TENANT_ID,
                Tenant.tenant_code == TENANT_CODE,
                Tenant.is_deleted.is_(False),
            )
        )
        if tenant is None:
            raise SystemExit("refusing non-sandbox tenant")
        profile = classify_sandbox_profile(db, TENANT_ID)
        logins = sorted({item["loginName"] for item in ACTORS.values()})
        users = {
            row.login_name: row
            for row in db.scalars(
                select(User).where(User.tenant_id == TENANT_ID, User.login_name.in_(logins))
            ).all()
        }
        role_rows = db.execute(
            select(User.login_name, Role.role_code)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.tenant_id == TENANT_ID,
                User.login_name.in_(logins),
                User.is_deleted.is_(False),
                UserRole.tenant_id == TENANT_ID,
                UserRole.is_deleted.is_(False),
                Role.tenant_id == TENANT_ID,
                Role.is_deleted.is_(False),
            )
        ).all()
        roles: dict[str, list[str]] = {login: [] for login in logins}
        for login, role in role_rows:
            roles[str(login)].append(str(role))

        student_user = users.get("2024S0002")
        student_link = None
        student = None
        if student_user is not None:
            student_link = db.scalar(
                select(StudentAccountLink).where(
                    StudentAccountLink.tenant_id == TENANT_ID,
                    StudentAccountLink.user_id == student_user.id,
                    StudentAccountLink.link_status == "ACTIVE",
                    StudentAccountLink.is_deleted.is_(False),
                )
            )
            if student_link is not None:
                student = db.get(StudentProfile, student_link.student_id)

        actor_rows = []
        for surface, spec in ACTORS.items():
            login = spec["loginName"]
            user = users.get(login)
            active_roles = sorted(set(roles.get(login) or []))
            checks = {
                "exists": user is not None,
                "active": bool(user and user.status == "ACTIVE"),
                "notDeleted": bool(user and not user.is_deleted),
                "requiredRole": spec["requiredRole"] in active_roles,
            }
            if surface.startswith("student"):
                checks["stableStudentAccountLink"] = bool(
                    student_link and student and not student.is_deleted and student.student_no == login
                )
            actor_rows.append(
                {
                    "surface": surface,
                    "loginName": login,
                    "requiredRole": spec["requiredRole"],
                    "activeRoles": active_roles,
                    "userId": str(user.id) if user else None,
                    "checks": checks,
                    "verdict": "PASS" if all(checks.values()) else "FAIL",
                }
            )

        teacher_scopes = _count(
            db,
            """
            SELECT COUNT(*) FROM t_teacher_student_scope
            WHERE tenant_id=:tid AND is_deleted=0 AND status='ACTIVE'
              AND teacher_key=:teacher
            """,
            tid=TENANT_ID,
            teacher="sbx_t0257",
        )
        student_id = int(student.id) if student is not None else 0
        class_id = int(student.class_id) if student is not None and student.class_id else 0
        facts = {
            "staffPendingTodos": _count(
                db,
                """
                SELECT COUNT(*) FROM t_unified_todo t
                JOIN t_user u ON u.tenant_id=t.tenant_id AND u.id=t.assignee_id
                WHERE t.tenant_id=:tid AND t.is_deleted=0 AND t.status='PENDING'
                  AND u.login_name='admin2' AND u.is_deleted=0
                """,
                tid=TENANT_ID,
            ),
            "teacherActiveScopes": teacher_scopes,
            "teacherScheduleItems": _count(
                db,
                """
                SELECT COUNT(*) FROM t_aa_schedule_item
                WHERE tenant_id=:tid AND is_deleted=0 AND teacher_key=:teacher
                """,
                tid=TENANT_ID,
                teacher="sbx_t0257",
            ),
            "teacherTeachingTasks": _count(
                db,
                """
                SELECT COUNT(*) FROM t_aa_teaching_task
                WHERE tenant_id=:tid AND is_deleted=0 AND teacher_key=:teacher
                """,
                tid=TENANT_ID,
                teacher="sbx_t0257",
            ),
            "studentRegistrations": _count(
                db,
                "SELECT COUNT(*) FROM t_aa_registration WHERE tenant_id=:tid AND is_deleted=0 AND student_id=:sid",
                tid=TENANT_ID,
                sid=student_id,
            ),
            "studentGradeRecords": _count(
                db,
                "SELECT COUNT(*) FROM t_aa_grade_record WHERE tenant_id=:tid AND is_deleted=0 AND student_id=:sid",
                tid=TENANT_ID,
                sid=student_id,
            ),
            "studentSelections": _count(
                db,
                "SELECT COUNT(*) FROM t_aa_selection_record WHERE tenant_id=:tid AND is_deleted=0 AND student_id=:sid",
                tid=TENANT_ID,
                sid=student_id,
            ),
            "studentMakeups": _count(
                db,
                """
                SELECT COUNT(*) FROM t_acad_makeup m
                JOIN t_acad_student a
                  ON a.tenant_id=m.tenant_id AND a.id=m.acad_student_id AND a.is_deleted=0
                WHERE m.tenant_id=:tid AND m.is_deleted=0 AND a.student_id=:sid
                """,
                tid=TENANT_ID,
                sid=student_id,
            ),
            "studentRetakes": _count(
                db,
                """
                SELECT COUNT(*) FROM t_acad_retake r
                JOIN t_acad_student a
                  ON a.tenant_id=r.tenant_id AND a.id=r.acad_student_id AND a.is_deleted=0
                WHERE r.tenant_id=:tid AND r.is_deleted=0 AND a.student_id=:sid
                """,
                tid=TENANT_ID,
                sid=student_id,
            ),
            "studentExamSeats": _count(
                db,
                "SELECT COUNT(*) FROM t_aa_exam_room_student WHERE tenant_id=:tid AND is_deleted=0 AND student_id=:sid",
                tid=TENANT_ID,
                sid=student_id,
            ),
            "studentWarnings": _count(
                db,
                """
                SELECT COUNT(*) FROM t_acad_warning w
                JOIN t_acad_student a
                  ON a.tenant_id=w.tenant_id AND a.id=w.acad_student_id AND a.is_deleted=0
                WHERE w.tenant_id=:tid AND w.is_deleted=0 AND a.student_id=:sid
                """,
                tid=TENANT_ID,
                sid=student_id,
            ),
            "studentClassScheduleItems": _count(
                db,
                "SELECT COUNT(*) FROM t_aa_schedule_item WHERE tenant_id=:tid AND is_deleted=0 AND class_id=:cid",
                tid=TENANT_ID,
                cid=class_id,
            ),
            "studentGraduationRecords": _count(
                db,
                "SELECT COUNT(*) FROM t_gd_student WHERE tenant_id=:tid AND is_deleted=0 AND student_id=:sid",
                tid=TENANT_ID,
                sid=student_id,
            ),
        }
        discarded = db.scalar(
            select(User).where(User.tenant_id == TENANT_ID, User.login_name == "e2e_aa_admin")
        )
        checks = {
            "standard20KProfile": profile.get("profile") == PROFILE_STANDARD,
            "allFourSurfacesHaveCanonicalActors": all(row["verdict"] == "PASS" for row in actor_rows),
            "teacherHasRealAcademicObjects": facts["teacherScheduleItems"] > 0 and facts["teacherTeachingTasks"] > 0,
            "studentHasRealAcademicObjects": all(
                facts[key] > 0
                for key in (
                    "studentRegistrations",
                    "studentGradeRecords",
                    "studentSelections",
                    "studentMakeups",
                    "studentRetakes",
                    "studentExamSeats",
                    "studentWarnings",
                    "studentClassScheduleItems",
                    "studentGraduationRecords",
                )
            ),
            "pollutingFixtureAdminNotSelected": bool(
                discarded is None or discarded.is_deleted or discarded.status != "ACTIVE"
            ),
        }
        evidence = {
            "gate": "ACADEMIC_V81_FOUR_ROLE_FIXTURE_PREFLIGHT",
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "gitHead": _head(),
            "tenant": {"id": str(TENANT_ID), "code": TENANT_CODE, "profile": profile},
            "actors": actor_rows,
            "facts": facts,
            "excludedLogin": {
                "loginName": "e2e_aa_admin",
                "reason": "deleted/disabled E2E residue; canonical 20K staff actor is admin2",
            },
            "containsPasswords": False,
            "checks": checks,
            "verdict": "PASS" if all(checks.values()) else "FAIL",
        }
        db.rollback()
    finally:
        db.close()

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "gate": evidence["gate"],
                "actors": [
                    {"surface": row["surface"], "loginName": row["loginName"], "verdict": row["verdict"]}
                    for row in actor_rows
                ],
                "facts": facts,
                "containsPasswords": False,
                "verdict": evidence["verdict"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if evidence["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
