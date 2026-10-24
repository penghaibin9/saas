from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_schedule_teacher_relation_guard as service


def test_teacher_note_preserves_estimate_limit_without_internal_fields(monkeypatch):
    @contextmanager
    def session():
        yield object()

    row = {"weekday": 1, "slotNo": 1, "startWeek": 1, "endWeek": 16,
           "scheduleItemId": "123", "teacherName": "测试教师"}
    monkeypatch.setattr(service.schedule, "session", session)
    monkeypatch.setattr(service, "_check_query_scope", lambda user, key: None)
    monkeypatch.setattr(service.schedule, "_current_published_batches", lambda db, term: [SimpleNamespace(id=12)])
    monkeypatch.setattr(service, "_teacher_items", lambda db, batch, key: [row])
    result = service.teacher_schedule({}, "teacher-1")
    assert result["items"] == [row]
    assert result["weeklyHours"] == 1
    assert result["batchIds"] == ["12"]
    assert result["teacherAuthorityPolicy"] == "TEACHING_CLASS_TEACHER_BY_WEEK"
    assert "估算" in result["note"] and "不能用于薪酬核算" in result["note"]
    assert "weeklyHours" not in result["note"]
    assert len(result["note"]) <= 40


def test_invalid_teacher_or_relation_keeps_error_code_and_details():
    with pytest.raises(AppException) as missing:
        service.teacher_schedule({}, "")
    assert missing.value.code == "VALIDATION_ERROR"
    assert missing.value.message == "请选择教师"
    with pytest.raises(AppException) as conflict:
        service._merge_windows([SimpleNamespace(id=32, start_week=8, end_week=2)], 16)
    assert conflict.value.code == "DATA_CONFLICT"
    assert conflict.value.http_status == 409
    assert conflict.value.details == {"teacherRelationId": "32", "startWeek": 8, "endWeek": 2}
    assert "任课周次有误" in conflict.value.message


@pytest.mark.parametrize("scope,identifier,purpose,message", [
    ("UNKNOWN", "1", "教务存档使用", "请选择班级、教师或教室课表"),
    ("CLASS", "", "教务存档使用", "请选择要导出的班级、教师或教室"),
    ("CLASS", "1", "", "请填写至少5字的导出用途"),
])
def test_export_validation_keeps_rejection_with_chinese_message(scope, identifier, purpose, message):
    with pytest.raises(AppException) as error:
        service.schedule.export_schedule({}, scope, identifier, purpose=purpose)
    assert error.value.code == "VALIDATION_ERROR"
    assert error.value.message == message


def test_adjustment_filter_error_preserves_code_without_raw_enum(monkeypatch):
    @contextmanager
    def session():
        yield object()
    read_records = service.schedule.list_schedule_adjustments
    monkeypatch.setitem(read_records.__globals__, "session", session)
    monkeypatch.setitem(read_records.__globals__, "_tid", lambda: 1)
    with pytest.raises(AppException) as error:
        read_records({}, biz_type="UNKNOWN")
    assert error.value.code == "VALIDATION_ERROR"
    assert error.value.message == "请选择课程安排或批次变更记录"
