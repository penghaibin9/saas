"""20K 演示校 32 专业课程/实习/毕设语义合同；纯单元测试，不连接数据库。"""
from app.services.sandbox_school_blueprint import COLLEGE_MAJOR_BLUEPRINT
from app.services.sandbox_school_professional_catalog import (
    MAJOR_PROFESSIONAL_PROFILES,
    professional_profile,
)


def _blueprint_major_names() -> set[str]:
    return {
        major_name
        for _college_code, _college_name, majors in COLLEGE_MAJOR_BLUEPRINT
        for major_name in majors
    }


def test_every_blueprint_major_has_one_professional_profile():
    expected = _blueprint_major_names()
    assert len(expected) == 32
    assert set(MAJOR_PROFESSIONAL_PROFILES) == expected


def test_each_major_has_real_course_position_and_graduation_semantics():
    for major_name in sorted(_blueprint_major_names()):
        profile = professional_profile(major_name)
        assert profile.industry
        assert len(profile.core_courses) == 6
        assert len(profile.internship_positions) == 4
        assert len(profile.graduation_topics) == 4
        assert len(set(profile.core_courses)) == 6
        assert len(set(profile.internship_positions)) == 4
        assert len(set(profile.graduation_topics)) == 4
        assert all("核心技能" not in name for name in profile.core_courses)
        assert all("技术助理" not in name for name in profile.internship_positions)
        assert all("真实业务场景综合实践项目" not in name for name in profile.graduation_topics)


def test_representative_majors_are_domain_specific_not_generic_templates():
    software = professional_profile("软件技术")
    nursing = professional_profile("护理")
    ecommerce = professional_profile("电子商务")
    new_energy = professional_profile("新能源汽车技术")

    assert "数据库应用技术" in software.core_courses
    assert "临床护理实习生" in nursing.internship_positions
    assert "直播间运营数据分析" in ecommerce.graduation_topics
    assert "动力电池技术" in new_energy.core_courses
    assert software.industry != nursing.industry != ecommerce.industry
