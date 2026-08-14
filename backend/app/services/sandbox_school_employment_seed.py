"""sandbox-school · 20K 真实学校就业域数据。

2026-08-13 时点：2024级刚进入三年级/岗位实习约三周，就业台账应以求职准备为主，
仅少量订单班、实习转录用等已有明确去向。企业/岗位复用已经专业化的实习企业主档，
不建立第二套公司真值；学生严格回链同一批 2024 级 StudentProfile。
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.services.sandbox_school_domain_seed import _roster
from app.services.sandbox_school_master_seed import _bulk_insert

EXPECTED_EMPLOYMENT_STUDENTS = 6400
EXPECTED_EMPLOYMENT_COMPANIES = 80
EXPECTED_EMPLOYMENT_JOBS = 160
EXPECTED_EMPLOYMENT_MATERIALS = 6400
EXPECTED_EMPLOYMENT_FOLLOWUPS = 800
EXPECTED_EMPLOYMENT_TODOS = 320
EXPECTED_KEY_HELP = 320
EXPECTED_FROM_INTERNSHIP_SIGNED = 640

DESTINATION_COUNTS = {
    "SIGNED": 768,          # 12.0%：订单班/提前录用/实习转录用
    "FURTHER_STUDY": 128,  # 2.0%：已明确的贯通培养/升学去向
    "FLEXIBLE": 64,        # 1.0%
    "ENLISTED": 32,        # 0.5%
    "STARTUP": 32,         # 0.5%
    "FREELANCE": 32,       # 0.5%
    "UNEMPLOYED": 5344,    # 83.5%：此时点仍处于求职准备，非毕业后失业结论
}

REFERENCE_NOW = datetime(2026, 8, 13, 10, 0)


def _stable_order(items: list[dict], salt: str) -> list[dict]:
    return sorted(
        items,
        key=lambda item: hashlib.sha256(
            f"{salt}:{item['student_no']}".encode("utf-8")
        ).digest(),
    )


def _employment_teachers_by_college(db, tenant_id: int) -> dict[str, list]:
    from app.models import TeacherStudentScope, User

    scopes = list(db.execute(select(
        TeacherStudentScope.teacher_key,
        TeacherStudentScope.teacher_name,
        TeacherStudentScope.ref_value,
    ).where(
        TeacherStudentScope.tenant_id == tenant_id,
        TeacherStudentScope.role_code == "EMPLOYMENT_TEACHER",
        TeacherStudentScope.scope_type == "COLLEGE",
        TeacherStudentScope.status == "ACTIVE",
        TeacherStudentScope.is_deleted.is_(False),
    ).order_by(TeacherStudentScope.ref_value, TeacherStudentScope.teacher_key)).all())
    user_by_login = {
        login: (int(uid), real_name)
        for uid, login, real_name in db.execute(select(
            User.id, User.login_name, User.real_name,
        ).where(
            User.tenant_id == tenant_id,
            User.login_name.in_([row.teacher_key for row in scopes]),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        )).all()
    }
    grouped: dict[str, list] = defaultdict(list)
    for row in scopes:
        user = user_by_login.get(row.teacher_key)
        if user:
            grouped[str(row.ref_value)].append({
                "user_id": user[0],
                "login": row.teacher_key,
                "name": row.teacher_name or user[1],
            })
    bad = {college: len(rows) for college, rows in grouped.items() if len(rows) != 4}
    if len(grouped) != 8 or bad:
        raise RuntimeError(f"就业老师学院配置异常 colleges={len(grouped)} bad={bad}")
    return dict(grouped)


def _destination_plan(roster: list[dict], assigned_ids: set[int]) -> dict[int, str]:
    eligible = [item for item in roster if int(item["id"]) in assigned_ids]
    ordered = _stable_order(eligible, "employment-destination")
    story = next((item for item in ordered if item["student_no"] == "2024S0001"), None)
    if story is not None:
        ordered.remove(story)
        ordered.insert(0, story)

    cursor = 0
    result: dict[int, str] = {}
    for destination in ("SIGNED", "FURTHER_STUDY", "FLEXIBLE", "ENLISTED", "STARTUP", "FREELANCE"):
        count = DESTINATION_COUNTS[destination]
        for item in ordered[cursor:cursor + count]:
            result[int(item["id"])] = destination
        cursor += count
    for item in roster:
        result.setdefault(int(item["id"]), "UNEMPLOYED")
    counts = Counter(result.values())
    if counts != Counter(DESTINATION_COUNTS):
        raise RuntimeError(f"就业去向分布异常 expected={DESTINATION_COUNTS} actual={dict(counts)}")
    return result


def seed_school_employment_20k(db, tenant_id: int) -> dict:
    from app.models import (
        EmpAuditTrail,
        EmpCompany,
        EmpFollowup,
        EmpJob,
        EmpMaterial,
        EmpStudent,
        InternshipPosition,
        InternshipRecord,
        UnifiedTodo,
    )

    existing = int(db.scalar(select(func.count()).select_from(EmpStudent).where(
        EmpStudent.tenant_id == tenant_id,
        EmpStudent.is_deleted.is_(False),
    )) or 0)
    if existing:
        raise RuntimeError(f"就业 20K 种子要求空台账，当前已有 {existing} 条")

    roster = [item for item in _roster(db, tenant_id) if item["grade"] == "2024"]
    if len(roster) != EXPECTED_EMPLOYMENT_STUDENTS:
        raise RuntimeError(f"2024级就业 cohort 异常: {len(roster)}")

    companies = list(db.scalars(select(EmpCompany).where(
        EmpCompany.tenant_id == tenant_id,
        EmpCompany.is_deleted.is_(False),
    ).order_by(EmpCompany.id)).all())
    positions = list(db.scalars(select(InternshipPosition).where(
        InternshipPosition.tenant_id == tenant_id,
        InternshipPosition.is_deleted.is_(False),
    ).order_by(InternshipPosition.id)).all())
    if len(companies) != EXPECTED_EMPLOYMENT_COMPANIES or len(positions) != EXPECTED_EMPLOYMENT_JOBS:
        raise RuntimeError(
            f"就业复用企业/岗位基数异常 companies={len(companies)} positions={len(positions)}"
        )
    company_by_id = {int(row.id): row for row in companies}

    internship_by_student = {
        int(row.student_id): row
        for row in db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.is_deleted.is_(False),
        )).all()
    }
    assigned_ids = {
        sid for sid, row in internship_by_student.items()
        if row.destination_type == "ASSIGNED" and row.position_id and row.enterprise_id
    }
    if len(assigned_ids) != 6100:
        raise RuntimeError(f"就业 seed 依赖的实习去向异常: assigned={len(assigned_ids)}")

    # 就业岗位直接投影现有专业化实习岗位，企业主档不重复插入。
    job_rows = [{
        "tenant_id": tenant_id,
        "company_id": int(position.company_id),
        "company_name": position.company_name,
        "title": position.title,
        "category": position.category or "专业对口岗位",
        "salary_range": "4500-7000元/月",
        "headcount": 20,
        "signed_count": 0,
        "status": "OPEN",
        "publish_time": "2026-07-15",
    } for position in positions]
    _bulk_insert(db, EmpJob, job_rows, chunk_size=500)
    db.flush()
    jobs = list(db.scalars(select(EmpJob).where(
        EmpJob.tenant_id == tenant_id,
        EmpJob.is_deleted.is_(False),
    ).order_by(EmpJob.id)).all())
    job_by_pair = {(int(job.company_id), job.title): job for job in jobs}
    if len(jobs) != 160 or len(job_by_pair) != 160:
        raise RuntimeError(f"就业岗位投影异常 jobs={len(jobs)} uniquePairs={len(job_by_pair)}")

    teachers_by_college = _employment_teachers_by_college(db, tenant_id)
    teacher_cursor: Counter[str] = Counter()
    destination_by_student = _destination_plan(roster, assigned_ids)
    pending = [item for item in roster if destination_by_student[int(item["id"])] == "UNEMPLOYED"]
    key_help_ids = {int(item["id"]) for item in _stable_order(pending, "employment-help")[:EXPECTED_KEY_HELP]}
    normal_follow_ids = {
        int(item["id"])
        for item in _stable_order(
            [item for item in pending if int(item["id"]) not in key_help_ids],
            "employment-follow-normal",
        )[:160]
    }

    positions_by_major: dict[str, list] = defaultdict(list)
    for position in positions:
        positions_by_major[str(position.major_requirement)].append(position)

    signed_order = [
        item for item in _stable_order(roster, "employment-signed-from-intern")
        if destination_by_student[int(item["id"])] == "SIGNED"
    ]
    from_internship_ids = {int(item["id"]) for item in signed_order[:EXPECTED_FROM_INTERNSHIP_SIGNED]}

    student_rows = []
    signed_company_count: Counter[int] = Counter()
    signed_job_count: Counter[tuple[int, str]] = Counter()
    teacher_by_student: dict[int, dict] = {}
    proof_type_by_student: dict[int, str] = {}
    material_status_by_student: dict[int, str] = {}

    for item in roster:
        sid = int(item["id"])
        destination = destination_by_student[sid]
        teacher_pool = teachers_by_college[item["college_name"]]
        teacher = teacher_pool[teacher_cursor[item["college_name"]] % len(teacher_pool)]
        teacher_cursor[item["college_name"]] += 1
        teacher_by_student[sid] = teacher

        company_name = job_title = salary_range = sign_date = None
        is_match_major = False
        from_internship = False
        if destination == "SIGNED":
            intern = internship_by_student[sid]
            if sid in from_internship_ids:
                position = next(row for row in positions if int(row.id) == int(intern.position_id))
                from_internship = True
            else:
                pool = positions_by_major[item["major_name"]]
                current_id = int(intern.position_id)
                alternatives = [row for row in pool if int(row.id) != current_id] or pool
                position = alternatives[item["grade_seq"] % len(alternatives)]
            company = company_by_id[int(position.company_id)]
            company_name = company.name
            job_title = position.title
            salary_range = "4500-7000元/月"
            sign_date = f"2026-08-{(item['grade_seq'] % 12) + 1:02d}"
            is_match_major = str(position.major_requirement) == item["major_name"]
            signed_company_count[int(company.id)] += 1
            signed_job_count[(int(company.id), position.title)] += 1

        key_help = sid in key_help_ids
        risk_level = "HIGH" if key_help else ("MEDIUM" if destination == "UNEMPLOYED" and item["grade_seq"] % 10 == 0 else "LOW")
        material_status = "SUBMITTED" if item["grade_seq"] % 5 == 0 else "APPROVED"
        material_status_by_student[sid] = material_status
        verify_status = (
            "VERIFIED"
            if destination != "UNEMPLOYED" and material_status == "APPROVED"
            else "PENDING_VERIFY"
        )
        if destination == "SIGNED":
            proof_type = ("AGREEMENT", "CONTRACT", "OFFER")[item["grade_seq"] % 3]
        elif destination == "FURTHER_STUDY":
            proof_type = "STUDY_PROOF"
        elif destination == "ENLISTED":
            proof_type = "ENLIST_PROOF"
        elif destination == "STARTUP":
            proof_type = "STARTUP_PROOF"
        else:
            proof_type = "OTHER"
        proof_type_by_student[sid] = proof_type

        follow_count = 2 if key_help else (1 if sid in normal_follow_ids else 0)
        last_follow = REFERENCE_NOW - timedelta(days=3) if follow_count else None
        student_rows.append({
            "tenant_id": tenant_id,
            "student_no": item["student_no"],
            "student_id": sid,
            "name": item["name"],
            "gender": item["gender"],
            "grade": "2027届",
            "college_name": item["college_name"],
            "major_name": item["major_name"],
            "class_id": str(item["class_id"]),
            "class_name": item["class_name"],
            "phone_encrypted": item["phone_encrypted"],
            "destination_type": destination,
            "company_name": company_name,
            "job_title": job_title,
            "salary_range": salary_range,
            "sign_date": sign_date,
            "is_match_major": is_match_major,
            "from_internship": from_internship,
            "verify_status": verify_status,
            "material_status": material_status,
            "help_level": "KEY_HELP" if key_help else "NORMAL",
            "risk_level": risk_level,
            "record_status": "ACTIVE",
            "counselor": item["counselor"],
            "employment_teacher": teacher["name"],
            "unemployed_reason": (
                "求职方向与期望地区仍在确认，已纳入重点帮扶"
                if key_help else
                "当前处于毕业前求职准备期，持续跟进岗位匹配"
                if destination == "UNEMPLOYED" else None
            ),
            "last_follow_up_time": last_follow,
            "follow_up_count": follow_count,
        })

    _bulk_insert(db, EmpStudent, student_rows, chunk_size=1000)
    db.flush()
    emp_by_profile = {
        int(profile_id): int(emp_id)
        for emp_id, profile_id in db.execute(select(EmpStudent.id, EmpStudent.student_id).where(
            EmpStudent.tenant_id == tenant_id,
            EmpStudent.is_deleted.is_(False),
        )).all()
    }

    material_rows = []
    followup_rows = []
    todo_rows = []
    audit_rows = []
    for item in roster:
        sid = int(item["id"])
        emp_id = emp_by_profile[sid]
        destination = destination_by_student[sid]
        teacher = teacher_by_student[sid]
        mat_status = material_status_by_student[sid]
        proof_type = proof_type_by_student[sid]
        if destination == "UNEMPLOYED":
            file_name = f"{item['student_no']}-就业意向登记表.pdf"
        else:
            file_name = f"{item['student_no']}-{proof_type.lower()}-去向证明.pdf"
        material_rows.append({
            "tenant_id": tenant_id,
            "emp_student_id": emp_id,
            "material_type": proof_type,
            "file_name": file_name,
            "submit_time": REFERENCE_NOW - timedelta(days=(item["grade_seq"] % 10) + 1),
            "status": mat_status,
            "reviewer": teacher["name"] if mat_status == "APPROVED" else None,
            "review_time": REFERENCE_NOW - timedelta(days=1) if mat_status == "APPROVED" else None,
            "remark": "就业中心毕业年级阶段性材料",
        })

        if sid in key_help_ids:
            followup_rows.extend([
                {
                    "tenant_id": tenant_id,
                    "emp_student_id": emp_id,
                    "follow_time": REFERENCE_NOW - timedelta(days=14),
                    "way": "PHONE",
                    "content": "确认求职方向、地区偏好与当前实习岗位适配情况",
                    "result": "已形成第一版求职方向清单",
                    "next_plan": "推荐专业对口岗位并跟进简历投递",
                    "operator": teacher["name"],
                    "status": "OPEN",
                },
                {
                    "tenant_id": tenant_id,
                    "emp_student_id": emp_id,
                    "follow_time": REFERENCE_NOW - timedelta(days=3),
                    "way": "RECOMMEND",
                    "content": "结合专业和实习表现推荐 2 个校企合作岗位",
                    "result": "学生已确认至少 1 个意向岗位",
                    "next_plan": "一周内回访投递与面试进展",
                    "operator": teacher["name"],
                    "status": "OPEN",
                },
            ])
            todo_rows.append({
                "tenant_id": tenant_id,
                "source_module": "employment",
                "source_biz_type": "EMP_FOLLOWUP",
                "source_biz_id": emp_id,
                "todo_type": "EMPLOYMENT_FOLLOWUP",
                "assignee_id": teacher["user_id"],
                "student_id": sid,
                "title": f"就业重点帮扶：{item['name']}",
                "status": "PENDING",
                "due_at": REFERENCE_NOW + timedelta(days=7),
            })
            audit_rows.append({
                "tenant_id": tenant_id,
                "biz_type": "RECORD",
                "biz_id": str(emp_id),
                "action": "纳入重点就业帮扶",
                "operator": teacher["name"],
                "role_name": "就业老师",
                "detail": "根据当前求职准备与岗位匹配情况纳入重点跟进",
                "occurred_at": REFERENCE_NOW - timedelta(days=15),
            })
        elif sid in normal_follow_ids:
            followup_rows.append({
                "tenant_id": tenant_id,
                "emp_student_id": emp_id,
                "follow_time": REFERENCE_NOW - timedelta(days=3),
                "way": "PHONE",
                "content": "常规回访求职准备与实习转就业意向",
                "result": "继续关注校招岗位",
                "next_plan": "后续按招聘批次推送岗位",
                "operator": teacher["name"],
                "status": "OPEN",
            })

        if destination != "UNEMPLOYED":
            audit_rows.append({
                "tenant_id": tenant_id,
                "biz_type": "RECORD",
                "biz_id": str(emp_id),
                "action": "登记阶段性就业去向",
                "operator": teacher["name"],
                "role_name": "就业老师",
                "detail": f"2026-08-13 时点去向：{destination}",
                "occurred_at": REFERENCE_NOW - timedelta(days=2),
            })

    _bulk_insert(db, EmpMaterial, material_rows, chunk_size=1000)
    _bulk_insert(db, EmpFollowup, followup_rows, chunk_size=1000)
    _bulk_insert(db, UnifiedTodo, todo_rows, chunk_size=500)
    _bulk_insert(db, EmpAuditTrail, audit_rows, chunk_size=1000)

    for company in companies:
        company.hired_count = signed_company_count[int(company.id)]
    for pair, job in job_by_pair.items():
        job.signed_count = signed_job_count[pair]
    db.commit()

    result = {
        "students": len(student_rows),
        "destinations": dict(Counter(destination_by_student.values())),
        "companiesReused": len(companies),
        "jobs": len(jobs),
        "materials": len(material_rows),
        "followups": len(followup_rows),
        "keyHelp": len(key_help_ids),
        "teacherTodos": len(todo_rows),
        "fromInternshipSigned": len(from_internship_ids),
        "employmentTeachers": len({teacher["user_id"] for teacher in teacher_by_student.values()}),
    }
    result["validation"] = validate_employment_facts_20k(db, tenant_id)
    return result


def validate_employment_facts_20k(db, tenant_id: int) -> dict:
    from app.models import (
        EmpCompany,
        EmpFollowup,
        EmpJob,
        EmpMaterial,
        EmpStudent,
        InternshipPosition,
        InternshipRecord,
        StudentProfile,
        UnifiedTodo,
    )

    emp_rows = list(db.scalars(select(EmpStudent).where(
        EmpStudent.tenant_id == tenant_id,
        EmpStudent.is_deleted.is_(False),
        EmpStudent.record_status == "ACTIVE",
    )).all())
    profile_ids = {
        int(sid) for (sid,) in db.execute(select(StudentProfile.id).where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.grade == "2024",
            StudentProfile.is_deleted.is_(False),
        )).all()
    }
    emp_profile_ids = {int(row.student_id) for row in emp_rows if row.student_id}
    destinations = Counter(row.destination_type for row in emp_rows)

    materials = int(db.scalar(select(func.count()).select_from(EmpMaterial).where(
        EmpMaterial.tenant_id == tenant_id,
        EmpMaterial.is_deleted.is_(False),
    )) or 0)
    followups = int(db.scalar(select(func.count()).select_from(EmpFollowup).where(
        EmpFollowup.tenant_id == tenant_id,
        EmpFollowup.is_deleted.is_(False),
    )) or 0)
    todos = int(db.scalar(select(func.count()).select_from(UnifiedTodo).where(
        UnifiedTodo.tenant_id == tenant_id,
        UnifiedTodo.source_module == "employment",
        UnifiedTodo.todo_type == "EMPLOYMENT_FOLLOWUP",
        UnifiedTodo.status == "PENDING",
        UnifiedTodo.is_deleted.is_(False),
    )) or 0)
    companies = list(db.scalars(select(EmpCompany).where(
        EmpCompany.tenant_id == tenant_id,
        EmpCompany.is_deleted.is_(False),
    )).all())
    jobs = list(db.scalars(select(EmpJob).where(
        EmpJob.tenant_id == tenant_id,
        EmpJob.is_deleted.is_(False),
    )).all())
    positions = list(db.scalars(select(InternshipPosition).where(
        InternshipPosition.tenant_id == tenant_id,
        InternshipPosition.is_deleted.is_(False),
    )).all())
    job_pairs = {(int(row.company_id), row.title) for row in jobs}
    position_pairs = {(int(row.company_id), row.title) for row in positions}

    company_by_name = {row.name: int(row.id) for row in companies}
    signed_rows = [row for row in emp_rows if row.destination_type == "SIGNED"]
    bad_signed_pairs = sum(
        1 for row in signed_rows
        if (company_by_name.get(row.company_name or "", -1), row.job_title) not in position_pairs
    )
    non_major_match_signed = sum(1 for row in signed_rows if not row.is_match_major)
    from_internship = sum(1 for row in signed_rows if row.from_internship)
    key_help = sum(1 for row in emp_rows if row.help_level == "KEY_HELP")
    blank_signed = sum(1 for row in signed_rows if not row.company_name or not row.job_title)

    internship_by_student = {
        int(row.student_id): row
        for row in db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.is_deleted.is_(False),
        )).all()
    }
    from_internship_mismatch = 0
    position_by_id = {int(row.id): row for row in positions}
    for row in signed_rows:
        if not row.from_internship:
            continue
        intern = internship_by_student[int(row.student_id)]
        position = position_by_id[int(intern.position_id)]
        if row.company_name != position.company_name or row.job_title != position.title:
            from_internship_mismatch += 1

    assigned_teachers = {row.employment_teacher for row in emp_rows if row.employment_teacher}
    company_hired = sum(int(row.hired_count or 0) for row in companies)
    job_signed = sum(int(row.signed_count or 0) for row in jobs)

    report = {
        "students": len(emp_rows),
        "uniqueProfiles": len(emp_profile_ids),
        "profileSetMatches2024": emp_profile_ids == profile_ids,
        "destinations": dict(destinations),
        "companies": len(companies),
        "jobs": len(jobs),
        "jobPairsMatchProfessionalPositions": job_pairs == position_pairs,
        "materials": materials,
        "followups": followups,
        "teacherTodos": todos,
        "employmentTeachers": len(assigned_teachers),
        "keyHelp": key_help,
        "fromInternshipSigned": from_internship,
        "badSignedPositionPairs": bad_signed_pairs,
        "nonMajorMatchSigned": non_major_match_signed,
        "fromInternshipMismatches": from_internship_mismatch,
        "blankSignedCompanyOrJob": blank_signed,
        "companyHiredCount": company_hired,
        "jobSignedCount": job_signed,
    }
    expected = {
        "students": EXPECTED_EMPLOYMENT_STUDENTS,
        "uniqueProfiles": EXPECTED_EMPLOYMENT_STUDENTS,
        "profileSetMatches2024": True,
        "destinations": DESTINATION_COUNTS,
        "companies": EXPECTED_EMPLOYMENT_COMPANIES,
        "jobs": EXPECTED_EMPLOYMENT_JOBS,
        "jobPairsMatchProfessionalPositions": True,
        "materials": EXPECTED_EMPLOYMENT_MATERIALS,
        "followups": EXPECTED_EMPLOYMENT_FOLLOWUPS,
        "teacherTodos": EXPECTED_EMPLOYMENT_TODOS,
        "employmentTeachers": 32,
        "keyHelp": EXPECTED_KEY_HELP,
        "fromInternshipSigned": EXPECTED_FROM_INTERNSHIP_SIGNED,
        "badSignedPositionPairs": 0,
        "nonMajorMatchSigned": 0,
        "fromInternshipMismatches": 0,
        "blankSignedCompanyOrJob": 0,
        "companyHiredCount": DESTINATION_COUNTS["SIGNED"],
        "jobSignedCount": DESTINATION_COUNTS["SIGNED"],
    }
    mismatches = {
        key: {"expected": value, "actual": report[key]}
        for key, value in expected.items()
        if report[key] != value
    }
    if mismatches:
        raise RuntimeError(f"20K 就业域验收失败: {mismatches}")
    report["passed"] = True
    return report
