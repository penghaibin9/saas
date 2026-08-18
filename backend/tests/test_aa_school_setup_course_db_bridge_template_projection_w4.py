"""A-W4 Course dry-run compares only facts expressible by course-catalog-v1."""
from __future__ import annotations


def test_bridge_strips_non_template_optional_fields_before_same_key_comparison():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_course_preflight_service as bridge

    item = {
        "rowNo": 2,
        "businessKey": "CS101@v1",
        "courseCode": "CS101",
        "version": 1,
        "payload": {
            "courseCode": "CS101",
            "courseName": "Python程序设计",
            "courseNameEn": "Python Programming",
            "description": "数据库里可能已有、但当前模板无法声明的简介",
            "category": "MAJOR_CORE",
        },
    }

    projected = bridge._template_asserted_item(item)
    assert projected is not item
    assert projected["payload"]["courseName"] == "Python程序设计"
    assert projected["payload"]["category"] == "MAJOR_CORE"
    assert "courseNameEn" not in projected["payload"]
    assert "description" not in projected["payload"]
    # Input is not mutated: later template expansion can explicitly opt these fields in.
    assert item["payload"]["courseNameEn"] == "Python Programming"
    assert item["payload"]["description"]
