"""包 4 · 停止线「毕业学分仍直接累计原始成绩行」：总学分/选修/实践必须按课程身份去重。

事故路径：同一门课学生先补考通过、后重修又通过（真实教务里两条都是正式 ACTIVE PASSED
成绩，不是脏数据），三个学分检查项直接 SUM(credit_value)，同一门课的学分被计两遍。
学生凭重复学分被判「已达毕业总学分」，实际没修够。

不变量：任一学分项的分母都必须先经 resolve_effective_grade 按稳定课程身份收敛到
每门课一条，再累加。
"""
from __future__ import annotations

import pytest

from app.core.context import set_tenant

TID = 1000000000000000001


def _seed(db, *, total_credits, elective_credits=None, practice_credits=None,
          practice_course_names=()):
    """建学生（含专业）+ 培养方案 + 方案绑定 + 学业台账，返回 (student, acad, program)。

    方案必须经 AaProgramBinding 按「班级」或「专业+入学年级」解析得到，缺任一环
    _check_* 会直接返回 UNKNOWN——那样测的就不是学分去重了。
    """
    import json

    from app.models import (AaProgram, AaProgramBinding, AaProgramCourse, AcademicStudent,
                            College, Major, StudentProfile)

    college = College(tenant_id=TID, college_name="信息工程学院", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="软件技术", status="ACTIVE")
    db.add(major)
    db.flush()

    student = StudentProfile(
        tenant_id=TID, student_no="GRAD-DEDUP-001", real_name="学分去重生",
        college_id=college.id, major_id=major.id, grade="2026",
        current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE")
    db.add(student)
    db.flush()

    # 键名以服务端实际读取为准：_check_course_elective 读 "选修"/"ELECTIVE"，
    # _check_practice 读 "实践"/"PRACTICE"，值都是学分数。
    requirement = {}
    if elective_credits is not None:
        requirement["ELECTIVE"] = elective_credits
    if practice_credits is not None:
        requirement["PRACTICE"] = practice_credits

    program = AaProgram(
        tenant_id=TID, program_name="软件技术2026", major_id=major.id,
        total_credits=total_credits,
        requirement_json=json.dumps(requirement, ensure_ascii=False) if requirement else None,
        status="PUBLISHED")
    db.add(program)
    db.flush()
    # 绑定必须落在「班级」或「专业+入学年级」某个作用域上，只挂 major_id 解析不到。
    db.add(AaProgramBinding(tenant_id=TID, major_id=major.id, program_id=program.id,
                            grade_year="2026", class_id=None, status="ACTIVE"))
    # 实践环节课程名来自方案课程表里 module 含「实践」的行。
    for name in practice_course_names:
        db.add(AaProgramCourse(tenant_id=TID, program_id=program.id, course_name=name,
                               module="实践环节"))
    db.flush()

    acad = AcademicStudent(
        tenant_id=TID, student_id=student.id, student_no=student.student_no,
        name=student.real_name, obtained_credits=0, required_credits=total_credits)
    db.add(acad)
    db.flush()
    return student, acad, program


def _grade(acad_id, *, course_id, credit, nature="ELECTIVE", exam_type="FINAL",
           course_name="数据库原理"):
    """一条正式 ACTIVE PASSED 成绩。course_id 相同即代表同一门课。"""
    from app.models import AcademicGrade

    return AcademicGrade(
        tenant_id=TID, acad_student_id=acad_id, course_id=course_id,
        course_name=course_name, nature=nature, credit_value=credit,
        score=80, pass_status="PASSED", record_status="ACTIVE",
        exam_type=exam_type, term="2026-1")


# 要求值设成单门课学分的两倍：学生实际只修够一半，裸 SUM 会把补考+重修凑成刚好达标。
# 去重后必须回到 FAIL——这样才能把「假达标」和「真达标」区分开。
@pytest.mark.parametrize("item,seed_kwargs,grade_kwargs", [
    # 总学分：方案要求 12 学分；同一门 6 学分的课补考+重修各一条 → 裸 SUM 得 12（假达标）
    ("CREDIT", {"total_credits": 12}, {"nature": "REQUIRED"}),
    # 选修学分：要求 12 学分，同上
    ("COURSE_ELECTIVE", {"total_credits": 60, "elective_credits": 12}, {"nature": "ELECTIVE"}),
])
def test_same_course_retake_is_not_counted_twice(db_mode, item, seed_kwargs, grade_kwargs):
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as svc

    db = get_sessionmaker()()
    set_tenant({"tenantId": str(TID)})
    try:
        student, acad, _program = _seed(db, **seed_kwargs)
        # 同一门课（course_id 相同）两条正式有效成绩：一次补考通过、一次重修通过。
        db.add(_grade(acad.id, course_id=90001, credit=6, exam_type="MAKEUP", **grade_kwargs))
        db.add(_grade(acad.id, course_id=90001, credit=6, exam_type="RETAKE", **grade_kwargs))
        db.commit()

        checker = {"CREDIT": svc._check_credit,
                   "COURSE_ELECTIVE": svc._check_course_elective}[item]
        result = checker(db, student)

        assert result["result"] != "PASS", (
            f"{item}: 同一门课补考+重修被计了两遍学分，学生凭重复学分假达标；"
            f"evidence={result.get('evidence')}")
    finally:
        set_tenant(None)
        db.close()


def test_practice_credits_dedup_by_course_identity(db_mode):
    """实践学分同理；另外实践项以 course_name 匹配，同名不同课也不能混算。"""
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as svc

    db = get_sessionmaker()()
    set_tenant({"tenantId": str(TID)})
    try:
        student, acad, _program = _seed(
            db, total_credits=60, practice_credits=16, practice_course_names=("顶岗实习",))
        db.add(_grade(acad.id, course_id=90002, credit=8, exam_type="MAKEUP",
                      nature="PRACTICE", course_name="顶岗实习"))
        db.add(_grade(acad.id, course_id=90002, credit=8, exam_type="RETAKE",
                      nature="PRACTICE", course_name="顶岗实习"))
        db.commit()

        result = svc._check_practice(db, student)
        assert result["result"] != "PASS", (
            f"PRACTICE: 同一门实践课被计两遍；evidence={result.get('evidence')}")
    finally:
        set_tenant(None)
        db.close()


def test_distinct_courses_still_accumulate(db_mode):
    """反向：不同课程必须照常累加，去重不能把正常学分吃掉。"""
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as svc

    db = get_sessionmaker()()
    set_tenant({"tenantId": str(TID)})
    try:
        student, acad, _program = _seed(db, total_credits=6)
        db.add(_grade(acad.id, course_id=90003, credit=3, nature="REQUIRED",
                      course_name="课程甲"))
        db.add(_grade(acad.id, course_id=90004, credit=3, nature="REQUIRED",
                      course_name="课程乙"))
        db.commit()

        result = svc._check_credit(db, student)
        assert result["result"] == "PASS", (
            f"两门不同课程共 6 学分应当达标；evidence={result.get('evidence')}")
    finally:
        set_tenant(None)
        db.close()
