"""sandbox-school · 20K 真实学校业务事实种子。

前置：必须先执行 sandbox_school_master_seed.rebuild_school_master_20k()。
本文件只基于真实主键关系生成业务事实，不写 DEMO marker、不伪造 FK、不直接写统计结果。

2026-08-13 业务时点：
- 2026 级 7,000 人：迎新/预报到准备，尚未虚构“已到校”；
- 2025 级 6,600 人：完成一年学业，进入二年级；
- 2024 级 6,400 人：进入三年级，5,600 人已上岗实习，其余处于实习准备；
- 毕设处于选题/前期指导，不虚构整届已经答辩毕业；
- 就业正式去向不在本期强行造数，待历史毕业届数据包单独生成。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import floor

from sqlalchemy import func, select

from app.services.sandbox_school_blueprint import (
    EXPECTED_STUDENT_COUNT,
    GRADE_STUDENT_COUNTS,
    REFERENCE_DATE,
)
from app.services.sandbox_school_master_seed import _bulk_insert, validate_school_master

REFERENCE_NOW = datetime(2026, 8, 13, 9, 0)
EXPECTED_ACADEMIC_STUDENTS = GRADE_STUDENT_COUNTS["2024"] + GRADE_STUDENT_COUNTS["2025"]
EXPECTED_GRADE_ROWS = GRADE_STUDENT_COUNTS["2024"] * 18 + GRADE_STUDENT_COUNTS["2025"] * 9
EXPECTED_CAMPUS_STUDENTS = EXPECTED_ACADEMIC_STUDENTS
EXPECTED_DORM_ROWS = EXPECTED_CAMPUS_STUDENTS // 20 * 17
EXPECTED_INTERNSHIP_RECORDS = GRADE_STUDENT_COUNTS["2024"]
EXPECTED_ONBOARD_INTERNS = 5600
EXPECTED_CHECKINS = EXPECTED_ONBOARD_INTERNS * 5
EXPECTED_WEEKLY_REPORTS = EXPECTED_ONBOARD_INTERNS - floor(EXPECTED_ONBOARD_INTERNS / 5)
EXPECTED_GRADUATION_STUDENTS = GRADE_STUDENT_COUNTS["2024"]
EXPECTED_MESSAGES = EXPECTED_STUDENT_COUNT
EXPECTED_STUDENT_TODOS = (
    GRADE_STUDENT_COUNTS["2026"] // 3
    + GRADE_STUDENT_COUNTS["2024"] // 4
    + GRADE_STUDENT_COUNTS["2025"] // 20
)

COMMON_YEAR1 = (
    "思想道德与法治", "大学英语", "高等数学", "信息技术", "体育与健康",
)
COMMON_YEAR2 = (
    "毛泽东思想和中国特色社会主义理论体系概论", "职业生涯规划", "创新创业基础", "劳动教育",
)
COURSE_CREDITS = (2.0, 2.0, 3.0, 2.0, 2.0, 3.0, 3.0, 3.0, 4.0)

COMPANY_STEMS = (
    "星澜智能", "云启数字", "湘锐制造", "澄海信息", "麓谷智联", "新程机电", "远望科技", "青禾电商",
    "启辰汽车", "瑞工自动化", "知行数据", "卓越网络", "华创物流", "云岚设计", "恒拓工程", "安健服务",
    "尚品文旅", "智造未来", "诚达商贸", "新翼传媒",
)
COMPANY_CITIES = ("长沙", "株洲", "湘潭", "岳阳", "衡阳", "常德", "郴州", "广州", "深圳", "杭州")
POSITION_TITLES = ("技术助理", "项目实习生", "运营专员", "设备维护实习生", "数据助理", "客户服务专员")


def _roster(db, tenant_id: int, grades: tuple[str, ...] | None = None) -> list[dict]:
    from app.models import College, Major, SchoolClass, StudentAccountLink, StudentContact, StudentProfile, User

    stmt = (
        select(
            StudentProfile.id,
            StudentProfile.student_no,
            StudentProfile.real_name,
            StudentProfile.gender,
            StudentProfile.grade,
            StudentProfile.current_stage,
            SchoolClass.id.label("class_id"),
            SchoolClass.class_name,
            SchoolClass.counselor_id,
            Major.id.label("major_id"),
            Major.major_name,
            College.id.label("college_id"),
            College.college_name,
        )
        .join(SchoolClass, SchoolClass.id == StudentProfile.class_id)
        .join(Major, Major.id == StudentProfile.major_id)
        .join(College, College.id == StudentProfile.college_id)
        .where(
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        )
        .order_by(StudentProfile.student_no)
    )
    if grades:
        stmt = stmt.where(StudentProfile.grade.in_(grades))
    raw = db.execute(stmt).all()

    counselor_ids = {int(x.counselor_id) for x in raw if x.counselor_id}
    counselor_names = {
        int(uid): name
        for uid, name in db.execute(select(User.id, User.real_name).where(
            User.tenant_id == tenant_id,
            User.id.in_(counselor_ids) if counselor_ids else User.id == -1,
        )).all()
    }
    phone_by_student = {
        int(sid): enc
        for sid, enc in db.execute(select(StudentContact.student_id, StudentContact.contact_value_encrypted).where(
            StudentContact.tenant_id == tenant_id,
            StudentContact.contact_type == "PHONE",
            StudentContact.is_primary.is_(True),
            StudentContact.is_deleted.is_(False),
        )).all()
    }
    user_by_student = {
        int(sid): int(uid)
        for sid, uid in db.execute(select(StudentAccountLink.student_id, StudentAccountLink.user_id).where(
            StudentAccountLink.tenant_id == tenant_id,
            StudentAccountLink.link_status == "ACTIVE",
            StudentAccountLink.is_deleted.is_(False),
        )).all()
    }

    out = []
    grade_seq = {"2024": 0, "2025": 0, "2026": 0}
    for row in raw:
        grade = str(row.grade)
        grade_seq[grade] = grade_seq.get(grade, 0) + 1
        out.append({
            "id": int(row.id),
            "student_no": row.student_no,
            "name": row.real_name,
            "gender": row.gender,
            "grade": grade,
            "grade_seq": grade_seq[grade],
            "stage": row.current_stage,
            "class_id": int(row.class_id),
            "class_name": row.class_name,
            "counselor_id": int(row.counselor_id) if row.counselor_id else None,
            "counselor": counselor_names.get(int(row.counselor_id)) if row.counselor_id else None,
            "major_id": int(row.major_id),
            "major_name": row.major_name,
            "college_id": int(row.college_id),
            "college_name": row.college_name,
            "phone_encrypted": phone_by_student.get(int(row.id)),
            "user_id": user_by_student.get(int(row.id)),
        })
    return out


def _seed_orientation(db, tenant_id: int, roster_2026: list[dict]) -> dict:
    from app.models import (
        GreenChannelApplication,
        OrientationBatch,
        OrientationException,
        OrientationExceptionFollowup,
        OrientationMaterial,
        OrientationStudent,
    )

    _bulk_insert(db, OrientationBatch, [{
        "tenant_id": tenant_id,
        "batch_name": "2026级新生迎新与报到",
        "batch_no": "ORI-2026-FALL",
        "year": "2026",
        "start_date": datetime(2026, 7, 20),
        "end_date": datetime(2026, 9, 20),
        "report_start_date": datetime(2026, 9, 5),
        "report_end_date": datetime(2026, 9, 7),
        "status": "ACTIVE",
        "planned_count": len(roster_2026),
        "remark": "当前处于线上预报到与到校准备阶段",
    }])

    rows = []
    for stu in roster_2026:
        seq = stu["grade_seq"]
        if seq <= 2100:
            report_status = "NOT_REPORTED"
            payment_status = "UNPAID"
            material_status = "NOT_UPLOADED"
            dorm_status = "UNASSIGNED"
            green = "NOT_APPLIED"
            steps = {
                "ACTIVATE": "TODO", "INFO": "TODO", "MATERIAL": "TODO", "PAYMENT": "TODO",
                "DORM": "TODO", "CHECKIN": "TODO", "CONFIRM": "TODO",
            }
            blocked_step = None
            blocked_reason = None
        elif seq <= 5250:
            is_green = seq % 8 == 0
            report_status = "PREPARED"
            payment_status = "UNPAID" if is_green else "PAID"
            material_status = "UPLOADED"
            dorm_status = "ASSIGNED" if seq % 10 != 0 else "UNASSIGNED"
            green = "REVIEWING" if is_green else "NOT_APPLIED"
            steps = {
                "ACTIVATE": "DONE", "INFO": "DONE", "MATERIAL": "DOING", "PAYMENT": "DOING" if is_green else "DONE",
                "DORM": "DONE" if dorm_status == "ASSIGNED" else "TODO", "CHECKIN": "TODO", "CONFIRM": "TODO",
            }
            blocked_step = "PAYMENT" if is_green else None
            blocked_reason = "绿色通道申请审核中" if is_green else None
        else:
            is_green = seq % 9 == 0
            report_status = "PREPARED"
            payment_status = "UNPAID" if is_green else "PAID"
            material_status = "APPROVED"
            dorm_status = "ASSIGNED"
            green = "APPROVED" if is_green else "NOT_APPLIED"
            steps = {
                "ACTIVATE": "DONE", "INFO": "DONE", "MATERIAL": "DONE", "PAYMENT": "DONE",
                "DORM": "DONE", "CHECKIN": "TODO", "CONFIRM": "TODO",
            }
            blocked_step = None
            blocked_reason = None
        risk = "HIGH" if seq % 250 == 0 else ("MEDIUM" if seq % 50 == 0 else "LOW")
        rows.append({
            "tenant_id": tenant_id,
            "student_id": stu["id"],
            "name": stu["name"],
            "admission_no": f"LQ2026{seq:06d}",
            "gender": stu["gender"],
            "college_name": stu["college_name"],
            "major_name": stu["major_name"],
            "class_id": str(stu["class_id"]),
            "class_name": stu["class_name"],
            "grade": "2026级",
            "phone_encrypted": stu["phone_encrypted"],
            "origin": ("湖南长沙", "湖南衡阳", "湖南邵阳", "湖南岳阳", "湖南常德")[seq % 5],
            "stage": stu["stage"],
            "report_status": report_status,
            "payment_status": payment_status,
            "green_channel_status": green,
            "material_status": material_status,
            "dorm_status": dorm_status,
            "building": f"博雅苑{(seq % 10) + 1}栋" if dorm_status == "ASSIGNED" else None,
            "room": f"{(seq % 6) + 1}{(seq % 30) + 1:02d}" if dorm_status == "ASSIGNED" else None,
            "risk_level": risk,
            "record_status": "ACTIVE",
            "counselor": stu["counselor"],
            "steps_json": steps,
            "blocked_step": blocked_step,
            "blocked_reason": blocked_reason,
            "payable_amount": 8800,
            "paid_amount": 0 if payment_status == "UNPAID" else 8800,
        })
    _bulk_insert(db, OrientationStudent, rows, chunk_size=1000)
    db.flush()

    ori_by_sid = {
        int(sid): int(oid)
        for oid, sid in db.execute(select(OrientationStudent.id, OrientationStudent.student_id).where(
            OrientationStudent.tenant_id == tenant_id,
            OrientationStudent.is_deleted.is_(False),
        )).all()
    }
    green_rows = []
    material_rows = []
    exception_rows = []
    exception_students = []
    for stu in roster_2026:
        seq = stu["grade_seq"]
        oid = ori_by_sid[stu["id"]]
        if seq > 2100 and seq % 8 == 0:
            green_rows.append({
                "tenant_id": tenant_id,
                "ori_student_id": oid,
                "apply_type": "生源地助学贷款" if seq % 16 else "学费缓缴",
                "apply_amount": 8800,
                "submit_time": REFERENCE_NOW - timedelta(days=seq % 12 + 1),
                "status": "APPROVED" if seq > 5250 else ("REVIEWING" if seq % 3 else "SUBMITTED"),
                "remark": "线上申请材料已按迎新流程提交",
            })
        if seq > 2100 and seq % 4 == 0:
            material_rows.append({
                "tenant_id": tenant_id,
                "ori_student_id": oid,
                "material_type": ("PHOTO", "ID_CARD", "ADMISSION_LETTER", "ARCHIVE")[seq % 4],
                "file_name": f"{stu['student_no']}-报到材料.pdf",
                "submit_time": REFERENCE_NOW - timedelta(days=seq % 10 + 1),
                "status": "APPROVED" if seq > 5250 else "UPLOADED",
                "reviewer": "学院迎新工作组" if seq > 5250 else None,
                "review_time": REFERENCE_NOW - timedelta(days=1) if seq > 5250 else None,
            })
        if seq % 50 == 0:
            etype = ("PAYMENT", "MATERIAL", "IDENTITY", "DORM")[(seq // 50) % 4]
            exception_rows.append({
                "tenant_id": tenant_id,
                "ori_student_id": oid,
                "exception_type": etype,
                "description": {
                    "PAYMENT": "线上缴费流水待核对",
                    "MATERIAL": "报到材料存在缺项，已通知补充",
                    "IDENTITY": "身份信息需要人工复核",
                    "DORM": "住宿申请与床位分配待协调",
                }[etype],
                "risk_level": "HIGH" if seq % 250 == 0 else "MEDIUM",
                "status": "PROCESSING" if seq % 100 == 0 else "OPEN",
                "handler": stu["counselor"],
                "last_follow_time": REFERENCE_NOW - timedelta(hours=6) if seq % 100 == 0 else None,
            })
            exception_students.append((oid, stu["counselor"], seq))
    _bulk_insert(db, GreenChannelApplication, green_rows, chunk_size=500)
    _bulk_insert(db, OrientationMaterial, material_rows, chunk_size=1000)
    _bulk_insert(db, OrientationException, exception_rows, chunk_size=500)
    db.flush()

    # 对“处理中”的异常补一条真实跟进链。
    open_exceptions = list(db.execute(select(
        OrientationException.id, OrientationException.ori_student_id, OrientationException.handler,
    ).where(
        OrientationException.tenant_id == tenant_id,
        OrientationException.status == "PROCESSING",
        OrientationException.is_deleted.is_(False),
    )).all())
    follow_rows = [{
        "tenant_id": tenant_id,
        "exception_id": int(eid),
        "follow_time": REFERENCE_NOW - timedelta(hours=6),
        "way": "PHONE",
        "content": "已联系学生并核对情况，等待补充材料后继续处理",
        "operator": handler,
        "status": "ACTIVE",
    } for eid, _oid, handler in open_exceptions]
    _bulk_insert(db, OrientationExceptionFollowup, follow_rows)
    db.commit()
    return {
        "students": len(rows),
        "greenChannels": len(green_rows),
        "materials": len(material_rows),
        "exceptions": len(exception_rows),
        "followups": len(follow_rows),
    }


def _course_catalog(major_name: str, grade: str) -> list[tuple[str, str, float]]:
    year1_major = (
        f"{major_name}专业导论", f"{major_name}基础实训", f"{major_name}核心技能", f"{major_name}项目实践",
    )
    first = [
        (name, "2025-2026-1" if idx < 5 else "2025-2026-2", COURSE_CREDITS[idx])
        for idx, name in enumerate((*COMMON_YEAR1, *year1_major))
    ]
    if grade == "2025":
        return first
    year2_major = (
        f"{major_name}综合实训", f"{major_name}岗位技能", f"{major_name}综合项目", f"{major_name}生产性实训", f"{major_name}专业拓展",
    )
    second_names = (*COMMON_YEAR2, *year2_major)
    second = [
        (name, "2025-2026-1" if idx < 5 else "2025-2026-2", COURSE_CREDITS[idx])
        for idx, name in enumerate(second_names)
    ]
    # 2024 级第一学年实际发生在 2024-2025；把 first 的学期回拨一年。
    first_2024 = [(name, term.replace("2025-2026", "2024-2025"), credit) for name, term, credit in first]
    return first_2024 + second


def _score(student_seq: int, course_index: int) -> int:
    marker = (student_seq * 7 + course_index * 11) % 100
    if marker < 3:  # 约 3% 单科不及格，形成真实但不过度夸张的补考/预警背景。
        return 55 + marker
    return 60 + ((marker * 3 + course_index) % 41)


def _seed_academic(db, tenant_id: int, roster: list[dict]) -> dict:
    from app.models import AcademicGrade, AcademicIntervention, AcademicStudent, AcademicWarning

    student_rows = []
    calc_by_sid: dict[int, dict] = {}
    for stu in roster:
        catalog = _course_catalog(stu["major_name"], stu["grade"])
        scores = [_score(stu["grade_seq"], idx) for idx in range(len(catalog))]
        failed = sum(1 for s in scores if s < 60)
        credits = sum(catalog[idx][2] for idx, score in enumerate(scores) if score >= 60)
        avg = round(sum(scores) / len(scores))
        gpa = round(sum(min(4.0, max(0.0, (s - 50) / 10)) for s in scores) / len(scores), 2)
        warning_level = "HIGH" if failed >= 3 else ("MEDIUM" if failed >= 2 else ("LOW" if failed == 1 else "NONE"))
        calc_by_sid[stu["id"]] = {"catalog": catalog, "scores": scores, "failed": failed}
        student_rows.append({
            "tenant_id": tenant_id,
            "student_no": stu["student_no"],
            "student_id": stu["id"],
            "name": stu["name"],
            "class_id": str(stu["class_id"]),
            "class_name": stu["class_name"],
            "college_name": stu["college_name"],
            "major_name": stu["major_name"],
            "grade": stu["grade"],
            "phone_encrypted": stu["phone_encrypted"],
            "counselor": stu["counselor"],
            "gpa": gpa,
            "avg_score": avg,
            "failed_count": failed,
            "obtained_credits": credits,
            "required_credits": 120 if stu["grade"] == "2024" else 60,
            "makeup_count": failed,
            "retake_count": max(0, failed - 1),
            "warning_level": warning_level,
            "warning_count": 1 if failed >= 2 else 0,
            "academic_status": "WARNING" if failed >= 2 else "NORMAL",
            "record_status": "ACTIVE",
        })
    _bulk_insert(db, AcademicStudent, student_rows, chunk_size=1000)
    db.flush()

    acad_by_sid = {
        int(sid): int(aid)
        for aid, sid in db.execute(select(AcademicStudent.id, AcademicStudent.student_id).where(
            AcademicStudent.tenant_id == tenant_id,
            AcademicStudent.is_deleted.is_(False),
        )).all()
    }
    grade_written = 0
    warning_rows = []
    for start in range(0, len(roster), 500):
        grade_rows = []
        for stu in roster[start:start + 500]:
            calc = calc_by_sid[stu["id"]]
            for idx, ((course_name, term, credit), score) in enumerate(zip(calc["catalog"], calc["scores"])):
                grade_rows.append({
                    "tenant_id": tenant_id,
                    "acad_student_id": acad_by_sid[stu["id"]],
                    "course_name": course_name,
                    "term": term,
                    "nature": "REQUIRED",
                    "credit_value": credit,
                    "score": score,
                    "pass_status": "PASSED" if score >= 60 else "FAILED",
                    "exam_type": "FINAL",
                    "record_status": "ACTIVE",
                    "source": "PUBLISH",
                })
        grade_written += _bulk_insert(db, AcademicGrade, grade_rows, chunk_size=2000)

    for stu in roster:
        failed = calc_by_sid[stu["id"]]["failed"]
        if failed < 2:
            continue
        closed = stu["grade_seq"] % 3 == 0
        warning_rows.append({
            "tenant_id": tenant_id,
            "code": f"AW-{stu['grade']}-{stu['grade_seq']:04d}",
            "acad_student_id": acad_by_sid[stu["id"]],
            "warn_type": "MULTI_FAIL",
            "level": "HIGH" if failed >= 3 else "MEDIUM",
            "reason": f"最近已发布成绩中有 {failed} 门课程未达到及格线",
            "source_rule": "已发布成绩不及格门数规则",
            "source_code": "EXAM_FAIL",
            "rule_code": "FAIL_2_PLUS",
            "owner": stu["counselor"],
            "status": "CLOSED" if closed else "PENDING_HANDLE",
            "trigger_time": datetime(2026, 7, 10, 9, 0),
            "deadline": "2026-09-15",
            "close_result": "已完成谈话并制定补考复习计划" if closed else None,
            "record_status": "ACTIVE",
        })
    _bulk_insert(db, AcademicWarning, warning_rows, chunk_size=1000)
    db.flush()

    closed_warnings = list(db.execute(select(
        AcademicWarning.id, AcademicWarning.owner,
    ).where(
        AcademicWarning.tenant_id == tenant_id,
        AcademicWarning.status == "CLOSED",
        AcademicWarning.is_deleted.is_(False),
    )).all())
    intervention_rows = [{
        "tenant_id": tenant_id,
        "warning_id": int(wid),
        "way": "TALK",
        "content": "辅导员已完成学业谈话，逐门确认未通过课程与补考安排",
        "result": "学生已确认复习计划并知晓补考时间",
        "next_plan": "开学后第一周复核补考准备情况",
        "operator": owner,
        "status": "CLOSED",
        "follow_time": datetime(2026, 7, 20, 15, 0),
    } for wid, owner in closed_warnings]
    _bulk_insert(db, AcademicIntervention, intervention_rows, chunk_size=1000)
    db.commit()
    return {
        "students": len(student_rows),
        "grades": grade_written,
        "warnings": len(warning_rows),
        "interventions": len(intervention_rows),
    }


def _is_boarder(seq: int) -> bool:
    return (seq - 1) % 20 < 17


def _seed_campus(db, tenant_id: int, roster: list[dict]) -> dict:
    from app.models import CsDormException, CsDormRecord, CsGrant, CsLeave, CsMentalRecord, CsServiceStudent, CsWorkOrder

    student_rows = []
    for idx, stu in enumerate(roster, 1):
        boarder = _is_boarder(idx)
        high_risk = idx % 250 == 0
        medium_risk = idx % 50 == 0 and not high_risk
        student_rows.append({
            "tenant_id": tenant_id,
            "student_no": stu["student_no"],
            "student_id": stu["id"],
            "name": stu["name"],
            "gender": stu["gender"],
            "college_name": stu["college_name"],
            "major_name": stu["major_name"],
            "class_id": str(stu["class_id"]),
            "class_name": stu["class_name"],
            "grade": stu["grade"],
            "phone_encrypted": stu["phone_encrypted"],
            "counselor": stu["counselor"],
            "building": f"博雅苑{(idx % 10) + 1}栋" if boarder else None,
            "room": f"{(idx % 6) + 1}{(idx % 30) + 1:02d}" if boarder else None,
            "care_level": "KEY_CARE" if high_risk else ("FOCUS" if medium_risk else "NORMAL"),
            "risk_level": "HIGH" if high_risk else ("MEDIUM" if medium_risk else "LOW"),
            "mental_flag": idx % 200 == 0,
            "record_status": "ACTIVE",
        })
    _bulk_insert(db, CsServiceStudent, student_rows, chunk_size=1000)
    db.flush()
    cs_by_sid = {
        int(sid): int(cid)
        for cid, sid in db.execute(select(CsServiceStudent.id, CsServiceStudent.student_id).where(
            CsServiceStudent.tenant_id == tenant_id,
            CsServiceStudent.is_deleted.is_(False),
        )).all()
    }

    dorm_rows = []
    leave_rows = []
    grant_rows = []
    exception_rows = []
    mental_rows = []
    work_order_rows = []
    for idx, stu in enumerate(roster, 1):
        csid = cs_by_sid[stu["id"]]
        boarder = _is_boarder(idx)
        building = f"博雅苑{(idx % 10) + 1}栋"
        room = f"{(idx % 6) + 1}{(idx % 30) + 1:02d}"
        if boarder:
            dorm_rows.append({
                "tenant_id": tenant_id,
                "cs_student_id": csid,
                "building": building,
                "room": room,
                "bed": str((idx % 6) + 1),
                "checkin_date": datetime(int(stu["grade"]), 9, 1),
                "status": "IN",
                "record_status": "ACTIVE",
            })
        if idx % 8 == 0:
            pending = idx % 5 == 0
            leave_rows.append({
                "tenant_id": tenant_id,
                "code": f"LV-2026-{idx:05d}",
                "cs_student_id": csid,
                "student_id": stu["id"],
                "leave_type": "SICK" if idx % 3 == 0 else "PERSONAL",
                "start_time": datetime(2026, 6, (idx % 20) + 1, 8, 0),
                "end_time": datetime(2026, 6, (idx % 20) + 2, 18, 0),
                "duration": "1 天",
                "reason": "身体不适就医" if idx % 3 == 0 else "家庭事务需短期离校",
                "status": "PENDING_REVIEW" if pending else "APPROVED",
                "apply_time": datetime(2026, 6, (idx % 20) + 1, 7, 30),
                "reviewer": None if pending else stu["counselor"],
                "review_time": None if pending else datetime(2026, 6, (idx % 20) + 1, 9, 0),
            })
        if idx % 7 == 0:
            reviewing = idx % 4 == 0
            grant_rows.append({
                "tenant_id": tenant_id,
                "code": f"GR-2026-{idx:05d}",
                "cs_student_id": csid,
                "grant_type": "NATIONAL_GRANT" if idx % 2 else "HARDSHIP",
                "amount": 3300 if idx % 2 else 1500,
                "apply_reason": "家庭经济情况符合学校资助项目申请条件",
                "material_sensitive": True,
                "status": "REVIEWING" if reviewing else "APPROVED",
                "apply_time": datetime(2026, 4, (idx % 20) + 1),
                "reviewer": None if reviewing else "学生资助中心",
                "review_time": None if reviewing else datetime(2026, 5, 20),
                "current_node": "资助老师审核" if reviewing else "已办结",
            })
        if boarder and idx % 50 == 0:
            exception_rows.append({
                "tenant_id": tenant_id,
                "code": f"DE-2026-{idx:05d}",
                "cs_student_id": csid,
                "exc_type": "NIGHT_OUT" if idx % 100 else "NO_RETURN",
                "happen_time": datetime(2026, 6, 18, 23, 10),
                "detail": "超过宿舍归寝时间，系统记录异常并通知辅导员",
                "status": "PROCESSING" if idx % 100 == 0 else "PENDING_HANDLE",
                "handler": stu["counselor"],
                "handle_note": "已联系学生核实情况" if idx % 100 == 0 else None,
                "handle_time": datetime(2026, 6, 19, 9, 0) if idx % 100 == 0 else None,
            })
        if idx % 200 == 0:
            mental_rows.append({
                "tenant_id": tenant_id,
                "cs_student_id": csid,
                "level": "FOCUS",
                "last_follow_time": datetime(2026, 6, 25, 15, 0),
                "next_follow_time": datetime(2026, 9, 10, 15, 0),
                "summary": "学期末适应性支持跟进，开学后继续关注",
                "counselor_note": "[涉密] 已完成常规支持访谈，未在普通列表暴露具体内容",
                "operator": "心理健康中心",
                "status": "PROCESSING",
            })
        if idx % 40 == 0:
            work_order_rows.append({
                "tenant_id": tenant_id,
                "code": f"WO-2026-{idx:05d}",
                "cs_student_id": csid,
                "title": "申请在读证明" if idx % 80 else "校园卡业务咨询",
                "wo_type": "CERT" if idx % 80 else "CONSULT",
                "priority": "MEDIUM",
                "handler": "学生事务服务中心" if idx % 3 else None,
                "status": "PROCESSING" if idx % 3 else "PENDING_HANDLE",
                "detail": "学生通过线上服务大厅提交的常规事务申请",
            })
    _bulk_insert(db, CsDormRecord, dorm_rows, chunk_size=1000)
    _bulk_insert(db, CsLeave, leave_rows, chunk_size=1000)
    _bulk_insert(db, CsGrant, grant_rows, chunk_size=1000)
    _bulk_insert(db, CsDormException, exception_rows, chunk_size=500)
    _bulk_insert(db, CsMentalRecord, mental_rows, chunk_size=500)
    _bulk_insert(db, CsWorkOrder, work_order_rows, chunk_size=500)
    db.commit()
    return {
        "students": len(student_rows),
        "dormRecords": len(dorm_rows),
        "leaves": len(leave_rows),
        "grants": len(grant_rows),
        "dormExceptions": len(exception_rows),
        "mentalCare": len(mental_rows),
        "workOrders": len(work_order_rows),
    }


def _seed_internship(db, tenant_id: int, roster_2024: list[dict]) -> dict:
    from app.models import (
        AttendanceException,
        EmpCompany,
        InternshipBatch,
        InternshipCheckin,
        InternshipPosition,
        InternshipRecord,
        RiskRecord,
        User,
        WeeklyReport,
    )

    _bulk_insert(db, InternshipBatch, [{
        "tenant_id": tenant_id,
        "batch_name": "2024级岗位实习",
        "batch_no": "INT-2024-2026FALL",
        "academic_year": "2026-2027",
        "term": "1",
        "start_date": datetime(2026, 7, 20),
        "end_date": datetime(2027, 1, 15),
        "signup_start_date": datetime(2026, 5, 10),
        "signup_end_date": datetime(2026, 6, 20),
        "planned_count": len(roster_2024),
        "status": "RUNNING",
        "rules_config": {"checkin": True, "weeklyReport": True, "guidance": True, "evaluation": True, "score": True},
        "stage_config": [
            {"code": "PREPARE", "name": "岗前准备", "startDate": "2026-05-10", "endDate": "2026-07-19"},
            {"code": "ONBOARD", "name": "在岗实习", "startDate": "2026-07-20", "endDate": "2027-01-15"},
        ],
    }])
    db.flush()
    batch_id = int(db.scalar(select(InternshipBatch.id).where(
        InternshipBatch.tenant_id == tenant_id,
        InternshipBatch.batch_no == "INT-2024-2026FALL",
    )))

    company_rows = []
    for idx in range(1, 81):
        stem = COMPANY_STEMS[(idx - 1) % len(COMPANY_STEMS)]
        city = COMPANY_CITIES[(idx - 1) % len(COMPANY_CITIES)]
        company_rows.append({
            "tenant_id": tenant_id,
            "name": f"湖南{stem}{idx:02d}有限公司",
            "industry": ("软件与信息服务", "智能制造", "现代服务", "商贸物流")[idx % 4],
            "nature": "民营企业" if idx % 5 else "国有企业",
            "city": city,
            "cooperation_level": "A" if idx % 4 == 0 else "B",
            "status": "ACTIVE",
            "region": city,
            "address": f"{city}市职业教育产教融合园区{idx}号",
            "scale": ("中型", "大型", "小型")[idx % 3],
            "source": "SCHOOL_ENTERPRISE",
            "coop_status": "ACTIVE",
            "qualification_status": "PASSED",
            "blacklist": False,
            "review_by": "校企合作中心",
            "review_at": datetime(2026, 4, 20),
            "access_valid_until": datetime(2027, 7, 31),
        })
    _bulk_insert(db, EmpCompany, company_rows, chunk_size=500)
    db.flush()
    companies = list(db.execute(select(EmpCompany.id, EmpCompany.name, EmpCompany.city).where(
        EmpCompany.tenant_id == tenant_id,
        EmpCompany.is_deleted.is_(False),
    ).order_by(EmpCompany.id)).all())

    position_rows = []
    for idx, company in enumerate(companies, 1):
        for offset in range(2):
            title = POSITION_TITLES[(idx * 2 + offset) % len(POSITION_TITLES)]
            position_rows.append({
                "tenant_id": tenant_id,
                "company_id": int(company.id),
                "company_name": company.name,
                "batch_id": batch_id,
                "title": title,
                "category": "专业实践",
                "grade_requirement": "2024级",
                "work_location": company.city,
                "salary_range": "2500-4000元/月",
                "subsidy": "餐补+交通补贴",
                "headcount": 45,
                "allocated_count": 40,
                "daily_hours": 8,
                "weekly_hours": 40,
                "shift_type": "DAY",
                "night_shift": False,
                "overtime_allowed": False,
                "rest_days_per_week": 2,
                "remuneration_type": "MONTHLY",
                "remuneration_amount": 3000,
                "remuneration_cycle": "MONTH",
                "hazardous_flag": False,
                "rights_status": "PASSED",
                "rights_checked_at": datetime(2026, 6, 15),
                "status": "PUBLISHED",
                "publish_at": datetime(2026, 6, 20),
            })
    _bulk_insert(db, InternshipPosition, position_rows, chunk_size=500)
    db.flush()
    positions = list(db.execute(select(
        InternshipPosition.id, InternshipPosition.company_id, InternshipPosition.company_name, InternshipPosition.title,
    ).where(
        InternshipPosition.tenant_id == tenant_id,
        InternshipPosition.batch_id == batch_id,
        InternshipPosition.is_deleted.is_(False),
    ).order_by(InternshipPosition.id)).all())

    mentors = list(db.execute(select(User.id, User.real_name).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_im%"),
        User.is_deleted.is_(False),
    ).order_by(User.login_name)).all())
    record_rows = []
    for idx, stu in enumerate(roster_2024, 1):
        if idx <= 5600:
            status, eligibility, destination = "ONBOARD", "QUALIFIED", "ASSIGNED"
        elif idx <= 6100:
            status, eligibility, destination = "READY", "QUALIFIED", "ASSIGNED"
        else:
            status, eligibility, destination = "PREPARING", "PENDING", "NONE"
        pos = positions[(idx - 1) % len(positions)] if destination == "ASSIGNED" else None
        mentor = mentors[(idx - 1) % len(mentors)]
        risk = "MEDIUM" if idx % 50 == 0 else ("LOW" if idx % 10 == 0 else "NONE")
        record_rows.append({
            "tenant_id": tenant_id,
            "student_id": stu["id"],
            "batch_id": batch_id,
            "enterprise_name": pos.company_name if pos else None,
            "position_name": pos.title if pos else None,
            "advisor_name": mentor.real_name,
            "advisor_user_id": int(mentor.id),
            "enterprise_id": int(pos.company_id) if pos else None,
            "position_id": int(pos.id) if pos else None,
            "eligibility_status": eligibility,
            "destination_type": destination,
            "status": status,
            "risk_level": risk,
            "intern_start_date": datetime(2026, 7, 20) if status in {"ONBOARD", "READY"} else None,
            "intern_end_date": datetime(2027, 1, 15),
            "insurance_info": "已核验" if status in {"ONBOARD", "READY"} else "待提交",
            "agreement_info": "已签署" if idx % 10 != 0 and status in {"ONBOARD", "READY"} else "待补签",
        })
    _bulk_insert(db, InternshipRecord, record_rows, chunk_size=1000)
    db.flush()
    internships = {
        int(sid): (int(iid), status, advisor)
        for iid, sid, status, advisor in db.execute(select(
            InternshipRecord.id, InternshipRecord.student_id, InternshipRecord.status, InternshipRecord.advisor_name,
        ).where(
            InternshipRecord.tenant_id == tenant_id,
            InternshipRecord.batch_id == batch_id,
            InternshipRecord.is_deleted.is_(False),
        )).all()
    }

    report_rows = []
    checkin_rows = []
    exception_rows = []
    risk_rows = []
    checkin_days = ("2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11", "2026-08-12")
    for idx, stu in enumerate(roster_2024, 1):
        iid, status, advisor = internships[stu["id"]]
        if idx <= EXPECTED_ONBOARD_INTERNS:
            if idx % 5 != 0:
                report_status = "APPROVED" if idx % 10 < 7 else ("PENDING_REVIEW" if idx % 10 < 9 else "RETURNED")
                report_rows.append({
                    "tenant_id": tenant_id,
                    "internship_id": iid,
                    "week_number": 1,
                    "work_content": "完成岗位入职培训，熟悉企业制度、安全要求与本周工作任务。",
                    "harvest_content": "掌握岗位基础流程，并能在企业导师指导下完成基础任务。",
                    "plan_content": "下周继续完成岗位任务并按要求记录实践过程。",
                    "word_count": 180,
                    "report_version": 1,
                    "submitted_at": datetime(2026, 8, 9, 20, 0),
                    "status": report_status,
                    "review_action": "APPROVE" if report_status == "APPROVED" else ("RETURN" if report_status == "RETURNED" else None),
                    "review_comment": "内容完整，继续保持过程记录。" if report_status == "APPROVED" else ("请补充本周具体工作成果。" if report_status == "RETURNED" else None),
                    "reviewed_by_name": advisor if report_status != "PENDING_REVIEW" else None,
                    "reviewed_at": datetime(2026, 8, 10, 10, 0) if report_status != "PENDING_REVIEW" else None,
                })
            for day_idx, day in enumerate(checkin_days):
                abnormal = idx % 100 == 0 and day_idx == 4
                no_location = idx % 250 == 0 and day_idx == 3
                result = "OUT_OF_RANGE" if abnormal else ("NO_LOCATION" if no_location else "NORMAL")
                checkin_rows.append({
                    "tenant_id": tenant_id,
                    "internship_id": iid,
                    "checkin_date": day,
                    "checkin_at": datetime.fromisoformat(day + "T08:25:00"),
                    "lat": 28.2282 if result != "NO_LOCATION" else None,
                    "lng": 112.9388 if result != "NO_LOCATION" else None,
                    "address": "企业实习岗位签到点" if result == "NORMAL" else "定位信息需复核",
                    "result": result,
                    "gps_accuracy": 18 if result == "NORMAL" else 120,
                    "device_risk_flag": "normal",
                    "distance_m": 35 if result == "NORMAL" else (1600 if result == "OUT_OF_RANGE" else None),
                })
            if idx % 50 == 0:
                exception_rows.append({
                    "tenant_id": tenant_id,
                    "internship_id": iid,
                    "exception_type": "OUT_OF_RANGE" if idx % 100 == 0 else "MISSING",
                    "exception_date": datetime(2026, 8, 12, 8, 30),
                    "distance_km": 1.6 if idx % 100 == 0 else None,
                    "gps_accuracy": 120,
                    "device_risk_flag": "normal",
                    "address": "实习单位周边定位异常点",
                    "streak_days": 1,
                    "status": "PENDING_HANDLE" if idx % 100 else "COMPLETED",
                    "handle_action": None if idx % 100 else "REASONABLE",
                    "handle_comment": None if idx % 100 else "已核实为企业安排的外出任务",
                    "handled_by_name": None if idx % 100 else advisor,
                    "handled_at": None if idx % 100 else datetime(2026, 8, 12, 14, 0),
                })
            if idx % 100 == 0:
                risk_rows.append({
                    "tenant_id": tenant_id,
                    "internship_id": iid,
                    "risk_code": "INT-R07",
                    "risk_title": "近期打卡存在定位异常",
                    "risk_level": "MEDIUM",
                    "source_module": "system",
                    "source_type": "CHECKIN",
                    "source_id": iid,
                    "owner_name": advisor,
                    "deadline_at": datetime(2026, 8, 17, 18, 0),
                    "status": "PROCESSING" if idx % 200 == 0 else "PENDING_HANDLE",
                    "last_follow_at": datetime(2026, 8, 13, 8, 30) if idx % 200 == 0 else None,
                    "last_follow_note": "已联系学生与企业导师核实定位异常原因" if idx % 200 == 0 else None,
                })
    _bulk_insert(db, WeeklyReport, report_rows, chunk_size=1000)
    _bulk_insert(db, InternshipCheckin, checkin_rows, chunk_size=2000)
    _bulk_insert(db, AttendanceException, exception_rows, chunk_size=500)
    _bulk_insert(db, RiskRecord, risk_rows, chunk_size=500)
    db.commit()
    return {
        "batch": 1,
        "companies": len(company_rows),
        "positions": len(position_rows),
        "records": len(record_rows),
        "weeklyReports": len(report_rows),
        "checkins": len(checkin_rows),
        "exceptions": len(exception_rows),
        "risks": len(risk_rows),
    }


def _seed_graduation(db, tenant_id: int, roster_2024: list[dict]) -> dict:
    from app.models import GraduationBatch, GraduationMentor, GraduationStudent, GraduationTopic, User

    _bulk_insert(db, GraduationBatch, [{
        "tenant_id": tenant_id,
        "batch_name": "2027届毕业设计（论文）",
        "batch_no": "GD-2027",
        "academic_year": "2026-2027",
        "grade_year": "2027届",
        "college_scope": "全校2024级三年制高职专业",
        "start_date": datetime(2026, 8, 1),
        "end_date": datetime(2027, 6, 20),
        "planned_count": len(roster_2024),
        "status": "RUNNING",
        "stage_config": [
            {"code": "TOPIC_SELECTING", "name": "选题", "startDate": "2026-08-01", "endDate": "2026-09-20"},
            {"code": "GUIDING", "name": "前期指导", "startDate": "2026-09-21", "endDate": "2027-03-31"},
        ],
        "rules_config": {"plagiarism": 30, "review": True, "defense": True, "score": True},
    }])
    db.flush()
    batch_id = int(db.scalar(select(GraduationBatch.id).where(
        GraduationBatch.tenant_id == tenant_id,
        GraduationBatch.batch_no == "GD-2027",
    )))

    mentor_users = list(db.execute(select(User.id, User.login_name, User.real_name).where(
        User.tenant_id == tenant_id,
        User.login_name.like("sbx_gm%"),
        User.is_deleted.is_(False),
    ).order_by(User.login_name)).all())
    mentor_rows = []
    for idx, user in enumerate(mentor_users, 1):
        mentor_rows.append({
            "tenant_id": tenant_id,
            "teacher_no": user.login_name,
            "teacher_name": user.real_name,
            "mentor_type": "INTERNAL",
            "title": "讲师" if idx % 3 else "副教授",
            "research_direction": "专业实践与产教融合项目",
            "max_capacity": 220,
            "current_count": 200,
            "qualification_status": "QUALIFIED",
        })
    _bulk_insert(db, GraduationMentor, mentor_rows, chunk_size=500)
    db.flush()
    mentors = list(db.execute(select(GraduationMentor.id, GraduationMentor.teacher_name).where(
        GraduationMentor.tenant_id == tenant_id,
        GraduationMentor.is_deleted.is_(False),
    ).order_by(GraduationMentor.id)).all())

    # 2026-08 中旬仍以选题为主；约 35% 学生已提前进入前期指导。
    guiding_count = 2240
    topic_count = guiding_count // 2
    topic_rows = []
    for idx in range(1, topic_count + 1):
        sample = roster_2024[(idx * 2 - 2) % len(roster_2024)]
        mentor = mentors[(idx - 1) % len(mentors)]
        topic_rows.append({
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "topic_no": f"GD2027-{idx:04d}",
            "title": f"{sample['major_name']}专业真实业务场景综合实践项目{idx:04d}",
            "source": "教师申报",
            "source_type": "TEACHER",
            "advisor_name": mentor.teacher_name,
            "advisor_mentor_id": int(mentor.id),
            "college_id": str(sample["college_id"]),
            "major_id": str(sample["major_id"]),
            "major_name": sample["major_name"],
            "category": "综合实践",
            "difficulty": "MEDIUM",
            "requirements": "基于真实岗位任务完成需求分析、方案设计、实现验证与成果总结。",
            "outcome": "形成可验收的实践成果、过程材料和毕业设计文档。",
            "capacity": 2,
            "selected": 2,
            "review_status": "APPROVED",
            "status": "CONFIRMED",
        })
    _bulk_insert(db, GraduationTopic, topic_rows, chunk_size=500)
    db.flush()
    topics = list(db.execute(select(GraduationTopic.id, GraduationTopic.title, GraduationTopic.advisor_mentor_id,
                                    GraduationTopic.advisor_name).where(
        GraduationTopic.tenant_id == tenant_id,
        GraduationTopic.batch_id == batch_id,
        GraduationTopic.is_deleted.is_(False),
    ).order_by(GraduationTopic.id)).all())

    student_rows = []
    for idx, stu in enumerate(roster_2024, 1):
        if idx <= len(roster_2024) - guiding_count:
            stage = "TOPIC_SELECTING"
            topic = None
            mentor = mentors[(idx - 1) % len(mentors)]
        else:
            stage = "GUIDING"
            topic = topics[((idx - (len(roster_2024) - guiding_count) - 1) // 2) % len(topics)]
            mentor = next((m for m in mentors if int(m.id) == int(topic.advisor_mentor_id)), mentors[0])
        student_rows.append({
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "topic_id": int(topic.id) if topic else None,
            "student_no": stu["student_no"],
            "student_id": stu["id"],
            "name": stu["name"],
            "class_id": str(stu["class_id"]),
            "class_name": stu["class_name"],
            "college_id": str(stu["college_id"]),
            "major_id": str(stu["major_id"]),
            "topic_title": topic.title if topic else None,
            "topic_source": "教师申报" if topic else None,
            "advisor_name": mentor.teacher_name,
            "stage": stage,
            "risk_level": "MEDIUM" if idx % 100 == 0 else "NONE",
            "phone_encrypted": stu["phone_encrypted"],
            "eligibility_status": "QUALIFIED",
            "mentor_id": int(mentor.id),
            "student_group": f"{stu['major_name']}过程组{(idx % 8) + 1}",
            "grad_qual_status": "PENDING",
            "record_status": "ACTIVE",
        })
    _bulk_insert(db, GraduationStudent, student_rows, chunk_size=1000)
    db.commit()
    return {
        "batch": 1,
        "mentors": len(mentor_rows),
        "topics": len(topic_rows),
        "students": len(student_rows),
        "topicSelecting": len(student_rows) - guiding_count,
        "guiding": guiding_count,
    }


def _seed_messages_and_todos(db, tenant_id: int, all_roster: list[dict]) -> dict:
    from app.models import UnifiedMessage, UnifiedTodo

    message_rows = []
    todo_rows = []
    for stu in all_roster:
        if stu["grade"] == "2026":
            title = "2026级新生报到准备提醒"
            content = "请在到校前完成个人信息核对、材料上传、缴费或绿色通道申请，并关注后续报到通知。"
            module = "orientation"
        elif stu["grade"] == "2025":
            title = "2026-2027学年第一学期开学提醒"
            content = "请按学校安排完成返校注册，关注课程安排、补考通知和学业预警信息。"
            module = "academic"
        else:
            title = "岗位实习安全与过程任务提醒"
            content = "请按实习计划完成打卡和周报，遇到岗位变更、安全风险或异常情况及时联系指导教师。"
            module = "internship"
        message_rows.append({
            "tenant_id": tenant_id,
            "receiver_id": stu["user_id"],
            "receiver_user_id": stu["user_id"],
            "receiver_type": "STUDENT",
            "receiver_context_key": "GLOBAL",
            "source_module": module,
            "source_biz_id": stu["id"],
            "title": title,
            "content": content,
            "message_type": "ANNOUNCEMENT",
            "status": "UNREAD" if stu["grade_seq"] % 10 < 3 else "READ",
            "read_at": None if stu["grade_seq"] % 10 < 3 else datetime(2026, 8, 12, 20, 0),
            "priority": "NORMAL",
            "category": "ANNOUNCEMENT",
            "delivered_at": datetime(2026, 8, 12, 18, 0),
            "delivery_status": "DELIVERED",
            "rendered_title": title,
            "rendered_content_plain": content,
            "sender_org_name_snapshot": "学生工作与教务协同中心",
        })

        needs_todo = False
        if stu["grade"] == "2026" and stu["grade_seq"] % 3 == 0:
            todo_type, todo_title, due = "ORIENTATION_PREP", "完成报到前材料与缴费检查", datetime(2026, 9, 3, 18, 0)
            module = "orientation"
            needs_todo = True
        elif stu["grade"] == "2024" and stu["grade_seq"] % 4 == 0:
            todo_type, todo_title, due = "INTERNSHIP_WEEKLY", "提交本周岗位实习周报", datetime(2026, 8, 16, 22, 0)
            module = "internship"
            needs_todo = True
        elif stu["grade"] == "2025" and stu["grade_seq"] % 20 == 0:
            todo_type, todo_title, due = "ACADEMIC_REVIEW", "查看学期成绩并确认补考安排", datetime(2026, 9, 10, 18, 0)
            module = "academic"
            needs_todo = True
        if needs_todo:
            todo_rows.append({
                "tenant_id": tenant_id,
                "source_module": module,
                "source_biz_type": "STUDENT_TASK",
                "source_biz_id": stu["id"],
                "todo_type": todo_type,
                "assignee_id": stu["user_id"],
                "student_id": stu["id"],
                "title": todo_title,
                "status": "PENDING",
                "due_at": due,
            })
    _bulk_insert(db, UnifiedMessage, message_rows, chunk_size=1000)
    _bulk_insert(db, UnifiedTodo, todo_rows, chunk_size=1000)
    db.commit()
    return {"messages": len(message_rows), "studentTodos": len(todo_rows)}


def validate_domain_facts(db, tenant_id: int) -> dict:
    from app.models import (
        AcademicGrade, AcademicStudent, CsDormRecord, CsServiceStudent, GraduationStudent,
        InternshipCheckin, InternshipRecord, OrientationStudent, UnifiedMessage, UnifiedTodo, WeeklyReport,
    )

    def count(model, *where):
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            *where,
        )) or 0)

    report = {
        "orientationStudents": count(OrientationStudent, OrientationStudent.is_deleted.is_(False)),
        "academicStudents": count(AcademicStudent, AcademicStudent.is_deleted.is_(False)),
        "academicGrades": count(AcademicGrade, AcademicGrade.is_deleted.is_(False)),
        "campusStudents": count(CsServiceStudent, CsServiceStudent.is_deleted.is_(False)),
        "dormRecords": count(CsDormRecord, CsDormRecord.is_deleted.is_(False)),
        "internshipRecords": count(InternshipRecord, InternshipRecord.is_deleted.is_(False)),
        "internshipCheckins": count(InternshipCheckin, InternshipCheckin.is_deleted.is_(False)),
        "weeklyReports": count(WeeklyReport, WeeklyReport.is_deleted.is_(False)),
        "graduationStudents": count(GraduationStudent, GraduationStudent.is_deleted.is_(False)),
        "messages": count(UnifiedMessage, UnifiedMessage.is_deleted.is_(False)),
        "pendingStudentTodos": count(UnifiedTodo, UnifiedTodo.status == "PENDING", UnifiedTodo.is_deleted.is_(False)),
    }
    expected = {
        "orientationStudents": GRADE_STUDENT_COUNTS["2026"],
        "academicStudents": EXPECTED_ACADEMIC_STUDENTS,
        "academicGrades": EXPECTED_GRADE_ROWS,
        "campusStudents": EXPECTED_CAMPUS_STUDENTS,
        "dormRecords": EXPECTED_DORM_ROWS,
        "internshipRecords": EXPECTED_INTERNSHIP_RECORDS,
        "internshipCheckins": EXPECTED_CHECKINS,
        "weeklyReports": EXPECTED_WEEKLY_REPORTS,
        "graduationStudents": EXPECTED_GRADUATION_STUDENTS,
        "messages": EXPECTED_MESSAGES,
        "pendingStudentTodos": EXPECTED_STUDENT_TODOS,
    }
    mismatches = {k: {"expected": expected[k], "actual": report[k]} for k in expected if report[k] != expected[k]}
    if mismatches:
        raise RuntimeError(f"20K 沙箱业务事实验收失败: {mismatches}")
    report["passed"] = True
    return report


def seed_school_domains_20k(db, tenant_id: int) -> dict:
    """在 20K 主数据之上生成业务事实，并以真实行数合同验收。"""
    validate_school_master(db, tenant_id)
    all_roster = _roster(db, tenant_id)
    if len(all_roster) != EXPECTED_STUDENT_COUNT:
        raise RuntimeError(f"20K roster 不完整: {len(all_roster)}")
    roster_2024 = [x for x in all_roster if x["grade"] == "2024"]
    roster_2025 = [x for x in all_roster if x["grade"] == "2025"]
    roster_2026 = [x for x in all_roster if x["grade"] == "2026"]

    result = {
        "referenceDate": REFERENCE_DATE,
        "orientation": _seed_orientation(db, tenant_id, roster_2026),
        "academic": _seed_academic(db, tenant_id, roster_2024 + roster_2025),
        "campus": _seed_campus(db, tenant_id, roster_2024 + roster_2025),
        "internship": _seed_internship(db, tenant_id, roster_2024),
        "graduation": _seed_graduation(db, tenant_id, roster_2024),
        "communication": _seed_messages_and_todos(db, tenant_id, all_roster),
    }
    result["validation"] = validate_domain_facts(db, tenant_id)
    return result
