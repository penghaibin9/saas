"""INT regression: an empty Program workbook is a zero-DB validation failure."""
from __future__ import annotations


def _preflight():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_preflight as preflight
    return preflight


def _pipeline():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preflight_pipeline as pipeline
    return pipeline


def _preview():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preview_adapter as preview
    return preview


def test_empty_program_source_is_one_explicit_workbook_blocker():
    result = _preflight().program_import_source_preflight([])
    assert result == {
        "totalRows": 0,
        "programCount": 0,
        "invalidRows": 1,
        "blockerCount": 1,
        "sourcePreflightSafe": False,
        "errors": [{
            "row": 0,
            "logicalGroup": "",
            "programKey": "",
            "businessCode": "PROGRAM_SOURCE_EMPTY",
            "message": "培养方案导入文件没有任何数据行，禁止以空工作簿进入数据库预检",
            "evidence": {"dataRows": 0},
            "howToResolve": "按 program-v2 六工作表模板至少填写一套 MAIN/COURSE/CREDIT_REQUIREMENT/GRADUATION 定义后重新预检",
        }],
    }


def test_empty_source_pipeline_opens_zero_snapshot_loaders():
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("empty source must not reach any snapshot loader")

    result = _pipeline().run_program_import_preflight(
        [],
        phase="DEFINITION",
        load_allowed_major_ids=forbidden,
        load_major_snapshots=forbidden,
        load_class_snapshots=forbidden,
        load_course_snapshots=forbidden,
        load_program_snapshots=forbidden,
        load_existing_definition_rows=forbidden,
        load_program_status_by_id=forbidden,
        load_active_binding_snapshots=forbidden,
    )
    assert calls == []
    assert result["stage"] == "SOURCE"
    assert result["programPreflightSafe"] is False
    assert result["errors"][0]["businessCode"] == "PROGRAM_SOURCE_EMPTY"


def test_empty_source_preview_cannot_look_like_zero_row_success():
    source = _preflight().program_import_source_preflight([])
    pipeline_result = {
        "stage": "SOURCE",
        "programPreflightSafe": False,
        "actions": [],
        "errors": source["errors"],
    }
    preview = _preview().program_preflight_to_file_exchange_preview([], pipeline_result)
    assert preview["totalRows"] == 0
    assert preview["validRows"] == 0
    assert preview["invalidRows"] == 1
    assert preview["programPreflightSafe"] is False
    assert preview["errors"][0]["field"] == "WORKBOOK:PROGRAM_SOURCE_EMPTY"
    assert preview["errors"][0]["evidence"] == {"dataRows": 0}
