"""20K 演示校导师工作量配置合同；纯单元测试，不连接数据库。"""
from app.services.sandbox_school_blueprint import MAJOR_CLASS_COUNTS_PER_GRADE
from app.services.sandbox_school_mentor_pool import (
    EXPECTED_GRADUATION_MENTORS,
    EXPECTED_INTERNSHIP_MENTORS,
    MAX_GRADUATION_STUDENTS_PER_MENTOR,
    MAX_INTERNSHIP_STUDENTS_PER_MENTOR,
    graduation_mentor_count_for_major,
    internship_mentor_count_for_major,
)


def test_internship_mentor_pool_matches_128_class_school():
    assert sum(internship_mentor_count_for_major(code) for code in MAJOR_CLASS_COUNTS_PER_GRADE) == 224
    assert EXPECTED_INTERNSHIP_MENTORS == 224
    assert MAX_INTERNSHIP_STUDENTS_PER_MENTOR == 36


def test_graduation_mentor_pool_matches_128_class_school():
    assert sum(graduation_mentor_count_for_major(code) for code in MAJOR_CLASS_COUNTS_PER_GRADE) == 384
    assert EXPECTED_GRADUATION_MENTORS == 384
    assert MAX_GRADUATION_STUDENTS_PER_MENTOR == 20


def test_every_major_has_professional_mentor_headroom():
    for code, class_count in MAJOR_CLASS_COUNTS_PER_GRADE.items():
        students = class_count * 50
        internship_mentors = internship_mentor_count_for_major(code)
        graduation_mentors = graduation_mentor_count_for_major(code)
        assert (students + internship_mentors - 1) // internship_mentors <= MAX_INTERNSHIP_STUDENTS_PER_MENTOR
        assert (students + graduation_mentors - 1) // graduation_mentors <= MAX_GRADUATION_STUDENTS_PER_MENTOR
