"""Targeted INT contract for the local Program preflight pipeline."""
from __future__ import annotations

import inspect
from decimal import Decimal


def _pipeline():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preflight_pipeline as pipeline
    return pipeline


def _rows(*, include_binding=False, class_binding=False):
    program_key = "SERIES:SER-A:v1"
    rows = [
        {
            "rowNo": 2,
            "logicalGroup": "MAIN",
            "programKey": program_key,
            "definitionKey": program_key,
            "payload": {
                "programSeriesKey": "SER-A",
                "programVersion": 1,
                "programName": "软件技术 2026 培养方案",
                "majorId": 1,
                "gradeYear": "2026",
                "totalCredits": Decimal("3.0"),
                "educationYearsAssertion": 3,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "COURSE",
            "programKey": program_key,
            "definitionKey": f"{program_key}|COURSE|CS101@v1",
            "payload": {
                "programKey": program_key,
                "courseKey": "CS101@v1",
                "module": "专业核心",
                "formationMode": "ADMIN_FIXED",
                "openTermNo": 1,
                "creditSnapshot": None,
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "programKey": program_key,
            "definitionKey": f"{program_key}|CREDIT|专业核心",
            "payload": {
                "programKey": program_key,
                "module": "专业核心",
                "creditTarget": Decimal("3.0"),
            },
        },
        {
            "rowNo": 2,
            "logicalGroup": "GRADUATION",
            "programKey": program_key,
            "definitionKey": f"{program_key}|GRADUATION|KNOWLEDGE|掌握程序设计基础",
            "payload": {
                "programKey": program_key,
                "category": "KNOWLEDGE",
                "content": "掌握程序设计基础",
                "sortOrder": 0,
            },
        },
    ]
    if include_binding:
        payload = {
            "programKey": program_key,
            "majorId": 1,
            "gradeYear": "2026",
            "bindingScope": "CLASS" if class_binding else "MAJOR_GRADE",
            "classId": 77 if class_binding else None,
        }
        scope_key = "CLASS:77" if class_binding else "MAJOR_GRADE"
        rows.append({
            "rowNo": 2,
            "logicalGroup": "BINDING",
            "programKey": program_key,
            "definitionKey": f"{program_key}|BINDING|{scope_key}",
            "payload": payload,
        })
    return rows


def _course_snapshots():
    return [{
        "courseId": 101,
        "courseCode": "CS101",
        "version": 1,
        "status": "ENABLED",
        "credit": Decimal("3.0"),
    }]


def _program_snapshots():
    return [{
        "programId": 501,
        "seriesKey": "SER-A",
        "version": 1,
        "prevVersionId": None,
        "programName": "软件技术 2026 培养方案",
        "majorId": 1,
        "gradeYear": "2026",
        "totalCredits": Decimal("3.0"),
        "status": "PUBLISHED",
    }]


def _existing_definitions():
    return [
        {
            "programId": 501,
            "logicalGroup": "COURSE",
            "payload": {
                "courseKey": "CS101@v1",
                "module": "专业核心",
                "formationMode": "ADMIN_FIXED",
                "openTermNo": 1,
                "creditSnapshot": Decimal("3.0"),
            },
        },
        {
            "programId": 501,
            "logicalGroup": "CREDIT_REQUIREMENT",
            "payload": {"module": "专业核心", "creditTarget": Decimal("3.0")},
        },
        {
            "programId": 501,
            "logicalGroup": "GRADUATION",
            "payload": {
                "category": "KNOWLEDGE",
                "content": "掌握程序设计基础",
                "sortOrder": 0,
            },
        },
    ]


def _loaders(calls, *, programs=(), definitions=(), class_rows=(), status=None, active=()):
    def loader(name, value):
        def _load():
            calls.append(name)
            return value
        return _load

    return {
        "load_allowed_major_ids": loader("scope", None),
        "load_major_snapshots": loader(
            "major", [{"majorId": 1, "educationYears": 3, "status": "ACTIVE"}]
        ),
        "load_class_snapshots": loader("class", list(class_rows)),
        "load_course_snapshots": loader("course", _course_snapshots()),
        "load_program_snapshots": loader("program", list(programs)),
        "load_existing_definition_rows": loader("definitions", list(definitions)),
        "load_program_status_by_id": loader("status", dict(status or {})),
        "load_active_binding_snapshots": loader("active_binding", list(active)),
    }


def test_source_blocker_short_circuits_every_snapshot_loader():
    calls = []
    rows = [_rows()[0]]
    result = _pipeline().run_program_import_preflight(
        rows,
        phase="DEFINITION",
        **_loaders(calls),
    )
    assert result["stage"] == "SOURCE"
    assert result["programPreflightSafe"] is False
    assert calls == []
    assert {item["businessCode"] for item in result["errors"]} >= {
        "PROGRAM_COURSE_EMPTY",
        "PROGRAM_CREDIT_REQUIREMENT_EMPTY",
        "PROGRAM_GRADUATION_REQUIREMENT_EMPTY",
    }


def test_new_v1_definition_phase_is_ready_without_loading_reuse_or_binding_state():
    calls = []
    result = _pipeline().run_program_import_preflight(
        _rows(include_binding=True),
        phase="DEFINITION",
        **_loaders(calls),
    )
    assert result["stage"] == "READY"
    assert result["programPreflightSafe"] is True
    assert calls == ["scope", "major", "course", "program"]
    assert result["actions"] == [{
        "programKey": "SERIES:SER-A:v1",
        "action": "CREATE",
        "programId": "",
        "createStatus": "DRAFT",
        "predecessorProgramId": "",
        "requiresDefinitionReconciliation": False,
    }]
    assert result["binding"]["bindingWriteAllowed"] is False
    assert result["binding"]["deferredCount"] == 1
    assert result["binding"]["intents"][0]["decision"] == "DEFER_UNTIL_PUBLISHED"


def test_reuse_loads_full_definition_only_after_reference_is_green():
    calls = []
    result = _pipeline().run_program_import_preflight(
        _rows(),
        phase="DEFINITION",
        **_loaders(
            calls,
            programs=_program_snapshots(),
            definitions=_existing_definitions(),
        ),
    )
    assert result["stage"] == "READY"
    assert result["programPreflightSafe"] is True
    assert calls == ["scope", "major", "course", "program", "definitions"]
    assert result["actions"][0]["action"] == "REUSE"
    assert result["actions"][0]["definitionReconciled"] is True


def test_binding_phase_defers_binding_reads_until_definition_is_proven():
    calls = []
    result = _pipeline().run_program_import_preflight(
        _rows(include_binding=True),
        phase="BINDING",
        **_loaders(
            calls,
            programs=_program_snapshots(),
            definitions=_existing_definitions(),
            status={"501": "PUBLISHED"},
        ),
    )
    assert result["stage"] == "READY"
    assert result["programPreflightSafe"] is True
    assert calls == [
        "scope", "major", "course", "program", "definitions", "status", "active_binding",
    ]
    assert result["binding"]["bindingWriteAllowed"] is True
    assert result["binding"]["intents"] == [{
        "row": 2,
        "programKey": "SERIES:SER-A:v1",
        "programId": "501",
        "scopeKey": "MAJOR:1:GRADE:2026:MAJOR_GRADE",
        "action": "CREATE",
        "supersedeProgramId": "",
    }]


def test_class_lookup_is_conditional_and_occurs_before_course_lookup():
    calls = []
    result = _pipeline().run_program_import_preflight(
        _rows(include_binding=True, class_binding=True),
        phase="DEFINITION",
        **_loaders(
            calls,
            class_rows=[{
                "classId": 77,
                "majorId": 1,
                "gradeYear": "2026",
                "classStatus": "NORMAL",
            }],
        ),
    )
    assert result["stage"] == "READY"
    assert calls == ["scope", "major", "class", "course", "program"]


def test_pipeline_has_no_session_or_shared_dispatcher_owner():
    source = inspect.getsource(_pipeline())
    assert "get_sessionmaker" not in source
    assert "session()" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
    assert "db.commit" not in source
    assert "db.flush" not in source
