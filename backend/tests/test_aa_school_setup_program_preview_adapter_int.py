"""INT contract for Program preflight -> File Exchange preview adaptation."""
from __future__ import annotations

import inspect


def _adapter():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preview_adapter as adapter
    return adapter


def test_preview_keeps_program_actions_separate_from_row_counts():
    rows = [
        {"rowNo": 2, "logicalGroup": "MAIN", "programKey": "SERIES:A:v1"},
        {"rowNo": 2, "logicalGroup": "COURSE", "programKey": "SERIES:A:v1"},
        {"rowNo": 2, "logicalGroup": "MAIN", "programKey": "SERIES:B:v1"},
        {"rowNo": 2, "logicalGroup": "COURSE", "programKey": "SERIES:B:v1"},
    ]
    preview = _adapter().program_preflight_to_file_exchange_preview(rows, {
        "stage": "READY",
        "programPreflightSafe": True,
        "binding": {"phase": "DEFINITION"},
        "actions": [
            {"programKey": "SERIES:A:v1", "action": "CREATE"},
            {"programKey": "SERIES:B:v1", "action": "REUSE"},
        ],
        "quality": {},
        "errors": [],
    })
    assert preview == {
        "totalRows": 4,
        "validRows": 4,
        "invalidRows": 0,
        "programCount": 2,
        "createPrograms": 1,
        "reusePrograms": 1,
        "conflictPrograms": 0,
        "rejectPrograms": 0,
        "phase": "DEFINITION",
        "stage": "READY",
        "programPreflightSafe": True,
        "warningCount": 0,
        "warnings": [],
        "qualityMetrics": [],
        "errors": [],
    }


def test_preview_preserves_sheet_location_evidence_and_resolution_for_shared_error_snapshot():
    rows = [
        {"rowNo": 2, "logicalGroup": "MAIN", "programKey": "SERIES:A:v1"},
        {"rowNo": 2, "logicalGroup": "COURSE", "programKey": "SERIES:A:v1"},
        {"rowNo": 3, "logicalGroup": "COURSE", "programKey": "SERIES:A:v1"},
    ]
    preview = _adapter().program_preflight_to_file_exchange_preview(rows, {
        "stage": "REFERENCE",
        "programPreflightSafe": False,
        "actions": [{"programKey": "SERIES:A:v1", "action": "CONFLICT"}],
        "errors": [
            {
                "row": 2,
                "logicalGroup": "COURSE",
                "programKey": "SERIES:A:v1",
                "businessCode": "PROGRAM_COURSE_VERSION_NOT_FOUND",
                "message": "方案课程引用的 exact Course version 不存在",
                "evidence": {"courseKey": "CS404@v1"},
                "howToResolve": "先建立并启用 exact Course version",
            },
            {
                "row": 2,
                "logicalGroup": "COURSE",
                "programKey": "SERIES:A:v1",
                "businessCode": "PROGRAM_COURSE_CREDIT_ASSERTION_MISMATCH",
                "message": "学分断言不一致",
                "evidence": {"courseKey": "CS101@v1"},
                "howToResolve": "修正学分断言",
            },
        ],
    })
    assert preview["totalRows"] == 3
    assert preview["invalidRows"] == 1
    assert preview["validRows"] == 2
    assert preview["conflictPrograms"] == 1
    assert preview["warningCount"] == 0
    assert preview["errors"][0] == {
        "row": 2,
        "logicalGroup": "COURSE",
        "field": "COURSE:PROGRAM_COURSE_VERSION_NOT_FOUND",
        "code": "PROGRAM_COURSE_VERSION_NOT_FOUND",
        "message": "方案课程引用的 exact Course version 不存在",
        "evidence": {"courseKey": "CS404@v1", "programKey": "SERIES:A:v1"},
        "howToResolve": "先建立并启用 exact Course version",
    }


def test_non_blocking_quality_warning_and_metrics_survive_preview_without_marking_rows_invalid():
    rows = [
        {"rowNo": 2, "logicalGroup": "MAIN", "programKey": "SERIES:A:v1"},
        {"rowNo": 2, "logicalGroup": "COURSE", "programKey": "SERIES:A:v1"},
    ]
    preview = _adapter().program_preflight_to_file_exchange_preview(rows, {
        "stage": "READY",
        "programPreflightSafe": True,
        "binding": {"phase": "DEFINITION"},
        "actions": [{"programKey": "SERIES:A:v1", "action": "CREATE"}],
        "quality": {
            "warnings": [{
                "programKey": "SERIES:A:v1",
                "businessCode": "PROGRAM_ACTUAL_CREDIT_EXCEEDED",
                "message": "课程与实践学分合计超过培养方案毕业总学分",
                "evidence": {"actualCreditSum": "141", "totalCredits": "140"},
                "howToResolve": "确认是否为选修冗余",
            }],
            "programMetrics": [{
                "programKey": "SERIES:A:v1",
                "actualCreditSum": "141",
                "totalCredits": "140",
            }],
        },
        "errors": [],
    })
    assert preview["invalidRows"] == 0
    assert preview["validRows"] == 2
    assert preview["programPreflightSafe"] is True
    assert preview["warningCount"] == 1
    assert preview["warnings"] == [{
        "row": 0,
        "logicalGroup": "",
        "field": "WORKBOOK:PROGRAM_ACTUAL_CREDIT_EXCEEDED",
        "code": "PROGRAM_ACTUAL_CREDIT_EXCEEDED",
        "message": "课程与实践学分合计超过培养方案毕业总学分",
        "evidence": {
            "actualCreditSum": "141",
            "totalCredits": "140",
            "programKey": "SERIES:A:v1",
        },
        "howToResolve": "确认是否为选修冗余",
    }]
    assert preview["qualityMetrics"] == [{
        "programKey": "SERIES:A:v1",
        "actualCreditSum": "141",
        "totalCredits": "140",
    }]


def test_preview_rejects_unknown_program_action_instead_of_silently_counting_it():
    try:
        _adapter().program_preflight_to_file_exchange_preview([], {
            "actions": [{"programKey": "SERIES:A:v1", "action": "OVERWRITE"}],
            "errors": [],
        })
    except ValueError as exc:
        assert "OVERWRITE" in str(exc)
    else:
        raise AssertionError("unknown action must fail closed")


def test_preview_adapter_has_no_file_db_or_dispatcher_owner():
    source = inspect.getsource(_adapter())
    assert "openpyxl" not in source
    assert "xlsx_util" not in source
    assert "get_sessionmaker" not in source
    assert "ImportJob(" not in source
    assert "FileObject(" not in source
    assert "data_exchange_confirm_service" not in source
    assert "db.commit" not in source
